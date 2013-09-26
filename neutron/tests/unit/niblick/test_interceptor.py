# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import mock
from oslo.config import cfg

from neutron import context
from neutron.db import api as db_api
from neutron.openstack.common import uuidutils
from neutron.plugins.niblick import exceptions
from neutron.plugins.niblick import interceptor_plugin
from neutron.plugins.niblick import policy
from neutron.tests import base

CONF = cfg.CONF


class FakeL2Plugin(object):
    def create_port(self):
        return True


class FakeL3Plugin(object):
    i = 0

    def create_router(self, context, router):
        self.__class__.i += 1
        router.update({'id': 'fake-object-%d' % self.__class__.i})
        return router

    def get_routers(self, *args, **kwargs):
        return [{'id': 'fake-router-1'}, {'id': 'fake-router-2'}]

    def delete_router(self, *args, **kwargs):
        pass

    def get_router(self, *args, **kwargs):
        return True

    def update_router(self, context, id, router):
        return router

    def add_router_interface(self, *args, **kwargs):
        return True

    def remove_router_interface(self, *args, **kwargs):
        pass


class FakePolicyDriver(policy.SimplePolicyDriver):
    def __init__(self):
        self._resources = {}
        for descriptor in ('fake-l3-1', 'fake-l3-2'):
            uuid = uuidutils.generate_uuid()
            resource = {'resource_id': uuid,
                        'resource_type': 'router',
                        'resource_metadata': {},
                        'allocated': False,
                        'resource_descriptor': descriptor}
            self._resources[uuid] = resource


class FakePluginManager(dict):
    def __init__(self):
        super(FakePluginManager, self).__init__(self)
        self.l2_descriptor = 'fake-l2'
        self['fake-l2'] = FakeL2Plugin()
        self['fake-l3-1'] = FakeL3Plugin()
        self['fake-l3-2'] = FakeL3Plugin()


class InterceptorTestCase(base.BaseTestCase):
    def setUp(self):
        super(InterceptorTestCase, self).setUp()
        db_api.configure_db()
        self.addCleanup(db_api.clear_db)
        CONF.set_override('policy_driver', 'neutron.tests.unit.niblick.'
                                           'test_interceptor.FakePolicyDriver',
                          'niblick')
        m = mock.patch('neutron.plugins.niblick.plugin_manager.PluginManager',
                       return_value=FakePluginManager())
        m.start()
        self.addCleanup(m.stop)
        self.context = context.get_admin_context()
        self.interceptor = interceptor_plugin.Interceptor()

    def test_init_policy(self):
        pd = self.interceptor._resource_manager._pm.policy_driver
        self.assertIsInstance(pd, FakePolicyDriver)

    def test_init_plugin_manager(self):
        pm = self.interceptor._plugin_manager
        self.assertIsInstance(pm, FakePluginManager)

    def test_get_all_plugins(self):
        for plugin in self.interceptor._get_all_plugins(self.context,
                                                        'router'):
            self.assertIsInstance(plugin, FakeL3Plugin)

    def test_l2_create_port(self):
        self.assertTrue(self.interceptor.create_port())

    def test_l3_create_router(self):
        router = self.interceptor.create_router(self.context, {})
        self.assertIn('id', router)

    def test_get_plugin(self):
        router = self.interceptor.create_router(self.context, {})
        plugin = self.interceptor._get_plugin(self.context, router['id'])
        self.assertIsInstance(plugin, FakeL3Plugin)

    def test_l3_delete_router(self):
        router = self.interceptor.create_router(self.context, {})
        self.interceptor.delete_router(self.context, router['id'])
        self.assertRaises(exceptions.WrongObjectId,
                          self.interceptor.delete_router, self.context,
                          router['id'])

    def test_l3_create_router_error_no_more_resources(self):
        self.interceptor.create_router(self.context, {})
        self.interceptor.create_router(self.context, {})
        self.assertRaises(exceptions.NoMoreResources,
                          self.interceptor.create_router, self.context, {})

    def test_l3_create_two_routers(self):
        router1 = self.interceptor.create_router(self.context, {})
        router2 = self.interceptor.create_router(self.context, {})
        self.assertNotEqual(router1['id'], router2['id'])

    def test_l3_get_routers(self):
        self.interceptor.create_router(self.context, {})
        self.interceptor.create_router(self.context, {})
        list1 = [{'id': 'fake-router-1'}, {'id': 'fake-router-2'}]
        list2 = self.interceptor.get_routers(self.context)
        self.assertListEqual(list1, list2)

    def test_l3_get_routers_count(self):
        self.interceptor.create_router(self.context, {})
        self.interceptor.create_router(self.context, {})
        count = self.interceptor.get_routers_count(self.context)
        self.assertEqual(2, count)

    def test_l3_get_router(self):
        router = self.interceptor.create_router(self.context, {})
        res = self.interceptor.get_router(self.context, router['id'])
        self.assertTrue(res)

    def test_l3_update_router(self):
        router = self.interceptor.create_router(self.context, {})
        res = self.interceptor.update_router(self.context, router['id'],
                                             router)
        self.assertDictEqual(router, res)

    def test_add_router_interface(self):
        router = self.interceptor.create_router(self.context, {})
        res = self.interceptor.add_router_interface(self.context, router['id'],
                                                    {})
        self.assertTrue(res)

    def test_remove_router_interface(self):
        router = self.interceptor.create_router(self.context, {})
        res = self.interceptor.remove_router_interface(self.context,
                                                       router['id'], {})
        self.assertIsNone(res)

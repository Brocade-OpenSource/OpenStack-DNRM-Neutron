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
import copy

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


class FakeL2Plugin(mock.Mock):
    pass


class FakeL3Plugin(mock.Mock):
    pass


class FakePolicyDriver(policy.SimplePolicyDriver):
    def __init__(self):
        self._resources = {}
        for descriptor in ('fake-l3-1', 'fake-l3-2'):
            uuid = uuidutils.generate_uuid()
            resource = {'resource_id': uuid,
                        'resource_type': 'L3',
                        'resource_metadata': {},
                        'allocated': False,
                        'resource_descriptor': descriptor}
            self._resources[uuid] = resource


class FakePluginManager(dict):
    def __init__(self):
        super(FakePluginManager, self).__init__(self)
        self.l2_descriptor = 'fake-l2'
        self['fake-l2'] = FakeL2Plugin()
        l3 = FakeL3Plugin()

        def create_router(context, router):
            router = copy.deepcopy(router)
            router['id'] = uuidutils.generate_uuid()
            return router

        l3.create_router.side_effect = create_router
        for desc in ('fake-l3-1', 'fake-l3-2'):
            self[desc] = l3


class InterceptorTestCase(base.BaseTestCase):
    def setUp(self):
        super(InterceptorTestCase, self).setUp()
        db_api.configure_db()
        self.addCleanup(db_api.clear_db)
        CONF.set_override('policy_driver', 'neutron.tests.unit.niblick.'
                                           'test_interceptor.FakePolicyDriver',
                          'niblick')
        m = mock.patch('neutron.plugins.niblick.plugin_manager.PluginManager',
                       new=FakePluginManager)
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

    def test_get_plugin(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        plugin = self.interceptor._get_plugin(self.context, router['id'])
        self.assertIsInstance(plugin, FakeL3Plugin)

    def test_get_all_plugins(self):
        for plugin in self.interceptor._get_all_plugins(self.context, 'L3'):
            self.assertIsInstance(plugin, FakeL3Plugin)

    def test_l2(self):
        self.interceptor.fake_l2_function('fake')
        l2 = self.interceptor._get_l2_plugin()
        l2.fake_l2_function.assert_called_once_with('fake')

    @property
    def l3(self):
        return self.interceptor._plugin_manager['fake-l3-1']

    def test_l3_create_router(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.assertTrue(uuidutils.is_uuid_like(router.get('id')))
        self.l3.create_router.assert_called_with(self.context,
                                                 {'router': {'metadata': {}}})

    def test_l3_delete_router(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.interceptor.delete_router(self.context, router['id'])
        self.l3.delete_router_assert_called_once_with(self.context,
                                                      router['id'])
        self.assertRaises(exceptions.WrongObjectId,
                          self.interceptor.delete_router, self.context,
                          router['id'])

    def test_l3_create_router_error_no_more_resources(self):
        self.interceptor.create_router(self.context, {'router': {}})
        self.interceptor.create_router(self.context, {'router': {}})
        self.assertRaises(exceptions.NoMoreResources,
                          self.interceptor.create_router, self.context, {})

    def test_l3_create_two_routers(self):
        router1 = self.interceptor.create_router(self.context, {'router': {}})
        router2 = self.interceptor.create_router(self.context, {'router': {}})
        self.assertNotEqual(router1['id'], router2['id'])

    def test_l3_get_routers(self):
        list1 = [self.interceptor.create_router(self.context, {'router': {}})
                 for _i in range(2)]
        self.l3.get_routers.return_value = list1
        list2 = self.interceptor.get_routers(self.context)
        list1 = sorted(list1, key=lambda d: d['id'])
        list2 = sorted(list2, key=lambda d: d['id'])
        self.assertListEqual(list1, list2)
        self.assertEqual(2, self.l3.get_routers.call_count)
        self.l3.get_routers.assert_called_with(self.context, None, None, None,
                                               None, None, False)

    def test_l3_get_routers_count(self):
        list1 = [self.interceptor.create_router(self.context, {'router': {}})
                 for _i in range(2)]
        self.l3.get_routers.return_value = list1
        count = self.interceptor.get_routers_count(self.context)
        self.assertEqual(2, count)
        self.assertEqual(2, self.l3.get_routers.call_count)
        self.l3.get_routers.assert_called_with(self.context, None, None, None,
                                               None, None, False)
        self.assertEqual(0, self.l3.get_routers_count.call_count)

    def test_l3_get_router(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.l3.get_router.return_value = router
        res = self.interceptor.get_router(self.context, router['id'])
        self.assertDictEqual(router, res)
        self.l3.get_router.assert_called_once_with(self.context, router['id'],
                                                   None)

    def test_l3_update_router(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.l3.update_router.return_value = router
        res = self.interceptor.update_router(self.context, router['id'],
                                             router)
        self.assertDictEqual(router, res)
        self.l3.update_router.assert_called_once_with(self.context,
                                                      router['id'], router)

    def test_l3_add_router_interface(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.l3.add_router_interface.return_value = True
        res = self.interceptor.add_router_interface(self.context, router['id'],
                                                    {})
        self.assertTrue(res)
        self.l3.add_router_interface.assert_called_once_with(self.context,
                                                             router['id'], {})

    def test_l3_remove_router_interface(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        self.l3.remove_router_interface.return_value = True
        res = self.interceptor.remove_router_interface(self.context,
                                                       router['id'], {})
        self.assertTrue(res)
        self.l3.remove_router_interface.assert_called_once_with(self.context,
                                                                router['id'],
                                                                {})

    def test_l3_router_dissoc_floatingip(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        obj = object()
        self.interceptor.router_dissoc_floatingip(self.context, router['id'],
                                                  obj)
        self.l3.router_dissoc_floatingip.assert_called_once_with(self.context,
                                                                 router['id'],
                                                                 obj, None)

    def test_l3_router_assoc_floatingip(self):
        router = self.interceptor.create_router(self.context, {'router': {}})
        obj = object()
        self.interceptor.router_assoc_floatingip(self.context, router['id'],
                                                 obj)
        self.l3.router_assoc_floatingip.assert_called_once_with(self.context,
                                                                router['id'],
                                                                obj, None)

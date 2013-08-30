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

from neutron import context
from neutron.plugins.niblick import resource
from neutron.tests import base


class ResourceManagerrTestCase(base.BaseTestCase):
    def setUp(self):
        super(ResourceManagerrTestCase, self).setUp()
        self.obj = {'object_id': 'fake-object-id',
                    'resource_type': 'fake-resource-type',
                    'resource_id': 'fake-resource-id',
                    'resource_descriptor': 'com.vyatta.vm',
                    'resource_meta': {}}

        self.binding_add = mock.patch('neutron.plugins.niblick.db.'
                                      'niblick_db_v2.binding_add',
                                      return_value=self.obj)
        self.binding_get = mock.patch('neutron.plugins.niblick.db.'
                                      'niblick_db_v2.binding_get',
                                      return_value=self.obj)
        self.binding_update = mock.patch('neutron.plugins.niblick.db.'
                                         'niblick_db_v2.binding_update',
                                         return_value=self.obj)
        self.binding_delete = mock.patch('neutron.plugins.niblick.db.'
                                         'niblick_db_v2.binding_delete',
                                         return_value=None)
        self.acquire_resource = mock.patch(
            'neutron.plugins.niblick.policy.PolicyManager.acquire_resource',
            return_value=self.obj)
        self.release_resource = mock.patch(
            'neutron.plugins.niblick.policy.PolicyManager.release_resource',
            return_value=None)

        self.binding_add.start()
        self.binding_get.start()
        self.binding_update.start()
        self.binding_delete.start()
        self.acquire_resource_mock = self.acquire_resource.start()
        self.release_resource_mock = self.release_resource.start()

        self.rm = resource.ResourceManager()
        self.context = context.get_admin_context()

    def tearDown(self):
        self.binding_add.stop()
        self.binding_get.stop()
        self.binding_update.stop()
        self.binding_delete.stop()
        self.acquire_resource.stop()
        self.release_resource.stop()
        super(ResourceManagerrTestCase, self).tearDown()

    def _allocate(self):
        with self.rm.allocate_resource(self.context, 'router') as resource:
            self.rm.bind_object(self.context, 'fake-object-id', resource)

    def _deallocate(self):
        with self.rm.deallocate_resource(self.context, 'fake-object-id'):
            pass

    def test_allocate_resource(self):
        self.assertIsNone(self._allocate())
        self.assertEqual(self.acquire_resource_mock.call_count, 1)

    def test_allocate_resource_error_unbind(self):
        class FakeException(Exception):
            pass

        def test():
            with self.rm.allocate_resource(self.context, 'router'):
                raise FakeException()

        self.assertRaises(FakeException, test)
        self.assertEqual(self.acquire_resource_mock.call_count, 1)
        self.assertEqual(self.release_resource_mock.call_count, 1)

    def test_deallocate_resource(self):
        self._allocate()
        self.assertIsNone(self._deallocate())
        self.assertEqual(self.acquire_resource_mock.call_count, 1)
        self.assertEqual(self.release_resource_mock.call_count, 1)

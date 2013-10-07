# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation.
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

from neutron.plugins.niblick import exceptions
from neutron.plugins.niblick import supervisor_policy_driver as policy
from neutron.tests import base

CONF = cfg.CONF


class SupervisorPolicyDriverTestCase(base.BaseTestCase):
    def setUp(self):
        super(SupervisorPolicyDriverTestCase, self).setUp()
        self.policy = policy.SupervisorPolicyDriver()

    def _mock(self, atr, *args):
        if args:
            m = mock.patch.object(self.policy, atr, return_value=args[0])
        else:
            m = mock.patch.object(self.policy, atr)
        return m

    def test_get(self):
        conn = mock.Mock()
        with mock.patch('httplib2.HTTPConnectionWithTimeout',
                        return_value=conn):
            resp = mock.Mock()
            resp.read.return_value = '{}'
            conn.getresponse.return_value = resp
            content = self.policy._get('fake-url', 'fake-method', {})
            conn.request.assert_called_once_with('fake-method', 'fake-url',
                                                 '{}')
            self.assertEqual(1, conn.getresponse.call_count)
            self.assertDictEqual({}, content)

    def test_list(self):
        with self._mock('_get') as get:
            resources = [{'id': 1}, {'id': 2}]
            get.return_value = {'resources': resources}
            resp = self.policy._list('fake-resource-type')
            self.assertListEqual(resources, resp)
            get.assert_called_once_with(self.policy.url +
                                        '?unused=False&allocated=False&'
                                        'processing=False&limit=1&'
                                        'class=fake-resource-type')

    def test_update(self):
        with self._mock('_get') as get:
            resources_id = 'fake-resource-id'
            resource = {'resource': {'id': resources_id, 'allocated': True}}
            get.return_value = resource
            resp = self.policy._update(resources_id, True)
            self.assertDictEqual(resource['resource'], resp)
            get.assert_called_once_with(
                '%s%s' % (self.policy.url, resources_id), 'PUT',
                {'resource': {'allocated': True}})

    def test_acquire_resource(self):
        with self._mock('_list', [{'id': 'fake-resource-id'}]) as lst, \
            self._mock('_update', {'id': 'fake-resource-id',
                                   'allocated': True,
                                   'type': 'fake-resource-type'}) as upd:
            resp = self.policy.acquire_resource('fake-context', 'L3')
            self.assertDictEqual(
                resp, {'resource_id': 'fake-resource-id',
                       'resource_type': 'L3', 'allocated': True,
                       'resource_descriptor': 'fake-resource-type',
                       'resource_metadata': {}})
            self.assertEqual(1, lst.call_count)
            self.assertEqual(1, upd.call_count)
            upd.assert_called_once_with('fake-resource-id', True)

    def test_acquire_resource_error_no_more_resource(self):
        with self._mock('_list', []):
            self.assertRaises(exceptions.NoMoreResources,
                              self.policy.acquire_resource,
                              context='fake-context',
                              resource_class='L3')

    def test_release_resource(self):
        with self._mock('_update', {'id': 1}):
            self.assertIsNone(self.policy.release_resource('fake-context',
                                                           'fake-resource_id'))

    def test_release_resource_error_wrong_resource_id(self):
        with self._mock('_update', None):
            self.assertRaises(exceptions.WrongResourceId,
                              self.policy.release_resource,
                              context='fake-context',
                              resource_id='fake-resource-id')

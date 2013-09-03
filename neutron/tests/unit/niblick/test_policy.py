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

from neutron.plugins.niblick import exceptions
from neutron.plugins.niblick import policy
from neutron.tests import base

CONF = cfg.CONF


class SimplePolicyDriverTestCase(base.BaseTestCase):
    def setUp(self):
        super(SimplePolicyDriverTestCase, self).setUp()
        CONF.set_override('instances',
                          {str(i): '127.0.0.{}'.format(i) for i in range(10)},
                          'niblick')
        self.policy = policy.SimplePolicyDriver()

    def test_acquire_resource(self):
        res = self.policy.acquire_resource('fake-context', 'router')
        self.assertTrue(res['allocated'])

    def test_acquire_resource_error_no_more_resource(self):
        self.assertRaises(exceptions.NoMoreResources,
                          self.policy.acquire_resource,
                          context='fake-context',
                          resource_type='fake-resource-type')

    def test_release_resource(self):
        res = self.policy.acquire_resource('fake-context', 'router')
        self.assertIsNone(self.policy.release_resource('fake-context',
                                                       res['resource_id']))

    def test_release_resource_error_wrong_resource_id(self):
        self.assertRaises(exceptions.WrongResourceId,
                          self.policy.release_resource,
                          context='fake-context',
                          resource_id='fake-resource-id')

    def test_aquire_resource_copy(self):
        res = self.policy.acquire_resource('fake-context', 'router')
        for val in self.policy._resources.itervalues():
            self.assertNotEqual(id(res), id(val))


class PolicyManagerTestCase(base.BaseTestCase):
    def setUp(self):
        super(PolicyManagerTestCase, self).setUp()
        CONF.set_override('policy_driver',
                          "neutron.plugins.niblick.policy."
                          "SimplePolicyDriver",
                          'niblick')
        m = mock.patch(
            'neutron.plugins.niblick.policy.SimplePolicyDriver.'
            'acquire_resource',
            return_value={'allocated': True})
        m.start()
        self.addCleanup(m.stop)

        m = mock.patch(
            'neutron.plugins.niblick.policy.SimplePolicyDriver.'
            'release_resource',
            return_value=None)
        m.start()
        self.addCleanup(m.stop)

        self.policy = policy.PolicyManager()

    def test_policy_driver_class(self):
        self.assertIsInstance(self.policy.policy_driver,
                              policy.SimplePolicyDriver)

    def test_acquire_resource(self):
        res = self.policy.acquire_resource('fake-context', 'router')
        self.assertTrue(res['allocated'])

    def test_release_resource(self):
        self.assertIsNone(self.policy.release_resource('fake-context',
                                                       'fake-resource-id'))

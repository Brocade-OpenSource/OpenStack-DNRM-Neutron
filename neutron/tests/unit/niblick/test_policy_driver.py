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
from oslo.config import cfg

from neutron.plugins.niblick import exceptions
from neutron.plugins.niblick import policy
from neutron.tests import base

CONF = cfg.CONF


class PolicyDriverTestCase(base.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        CONF.niblick.instances = {str(i): '127.0.0.{}'.format(i)
                                  for i in range(10)}

    def setUp(self):
        super(PolicyDriverTestCase, self).setUp()
        self.policy = policy.SupervisorLessPolicyDriver()

    def test_acquire_resource(self):
        res = self.policy.acquire_resource('fake-context',
                                           self.policy.resource_type)
        self.assertTrue(res['allocated'])

        self.assertRaises(exceptions.NoMoreResources,
                          self.policy.acquire_resource,
                          context='fake-context',
                          resource_type='fake-resource-type')

    def test_release_resource(self):
        res = self.policy.acquire_resource('fake-context',
                                           self.policy.resource_type)
        self.assertIsNone(self.policy.release_resource('fake-context',
                                                       res['id']))

        self.assertRaises(exceptions.WrongResourceId,
                          self.policy.release_resource,
                          context='fake-context',
                          resource_id='fake-resource-id')

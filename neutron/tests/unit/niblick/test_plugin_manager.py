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

from neutron.plugins.niblick import plugin_manager
from neutron.tests import base

CONF = cfg.CONF


class FakePlugin(object):
    pass


class SimplePolicyDriverTestCase(base.BaseTestCase):
    def setUp(self):
        super(SimplePolicyDriverTestCase, self).setUp()
        klass = 'neutron.tests.unit.niblick.test_plugin_manager.FakePlugin'
        self.plugins = {'fake-{}'.format(i): klass for i in range(10)}
        self.plugins['fake-l2'] = klass
        CONF.set_override('plugin_list', self.plugins, 'niblick')
        CONF.set_override('l2_descriptor', 'fake-l2', 'niblick')
        self.plugin_manager = plugin_manager.PluginManager()

    def test_plugins_count(self):
        self.assertEqual(len(self.plugins), len(self.plugin_manager))

    def test_plugins_names(self):
        for name in self.plugins:
            self.assertTrue(name in self.plugin_manager)

    def test_plugins_class(self):
        for plugin in self.plugin_manager.itervalues():
            self.assertIsInstance(plugin, FakePlugin)

    def test_plugins_l2_descriptor(self):
        self.assertEqual('fake-l2', self.plugin_manager.l2_descriptor)

    def test_plugins_l2_class(self):
        self.assertIsInstance(
            self.plugin_manager[self.plugin_manager.l2_descriptor],
            FakePlugin)

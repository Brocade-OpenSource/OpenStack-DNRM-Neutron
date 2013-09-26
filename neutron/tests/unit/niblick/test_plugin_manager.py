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

from neutron.db import api as db
from neutron.plugins.niblick import plugin_manager
from neutron.tests import base

CONF = cfg.CONF


class FakePlugin(object):
    pass


class PluginManagerTestCase(base.BaseTestCase):
    def setUp(self):
        super(PluginManagerTestCase, self).setUp()
        m = mock.patch('neutron.plugins.niblick.plugin_manager.PluginManager.'
                       '_load_plugin', return_value=FakePlugin())
        self.load_plugin = m.start()
        self.addCleanup(m.stop)
        self.plugins = {str(i): str(i) for i in range(9)}
        self.plugins['fake-l2'] = 'fake-l2'
        CONF.set_override('plugin_list', self.plugins, 'niblick')
        CONF.set_override('l2_descriptor', 'fake-l2', 'niblick')
        self.plugin_manager = plugin_manager.PluginManager()

    def test_plugins_count(self):
        self.assertEqual(10, len(self.plugin_manager))

    def test_plugins_class(self):
        for plugin in self.plugin_manager.itervalues():
            self.assertIsInstance(plugin, FakePlugin)

    def test_plugins_l2_descriptor(self):
        self.assertEqual('fake-l2', self.plugin_manager.l2_descriptor)

    def test_plugins_l2_class(self):
        self.assertIsInstance(
            self.plugin_manager[self.plugin_manager.l2_descriptor], FakePlugin)

    def test_db_engine(self):
        self.assertIsNone(db._ENGINE)

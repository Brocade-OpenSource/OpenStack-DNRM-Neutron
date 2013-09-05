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

from neutron.db import api as db
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.plugins.niblick import common


plugin_manager_opts = [
    cfg.DictOpt("plugin_list",
                default={"linuxbridge": "neutron.plugins.linuxbridge."
                         "lb_neutron_plugin.LinuxBridgePluginV2"},
                help=_("List of plugins to load")),
    cfg.StrOpt("l2_descriptor", default="linuxbridge",
               help=_("L2 plugin descriptor")),
]

CONF = cfg.CONF
CONF.register_opts(plugin_manager_opts, "niblick")

LOG = logging.getLogger(__name__)


class PluginManager(dict):
    __metaclass__ = common.Singleton

    def __init__(self):
        super(PluginManager, self).__init__(self)
        self._plugin_list = {}

        for desc, plugin_provider in CONF.niblick.plugin_list.iteritems():
            self[desc] = self._load_plugin(plugin_provider)
            # Needed to clear _ENGINE for each plugin
            db._ENGINE = None

        self._l2_descriptor = CONF.niblick.l2_descriptor

    def _load_plugin(self, plugin_provider):
        LOG.debug(_("Plugin location: %s"), plugin_provider)
        plugin = importutils.import_class(plugin_provider)
        return plugin()

    @property
    def l2_descriptor(self):
        return self._l2_descriptor

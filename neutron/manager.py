# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Nicira Networks, Inc
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
# @author: Somik Behera, Nicira Networks, Inc.

from oslo.config import cfg

from neutron.common import legacy
from neutron.common import utils
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import periodic_task
from neutron.plugins.common import constants


LOG = logging.getLogger(__name__)


class Manager(periodic_task.PeriodicTasks):

    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'

    def __init__(self, host=None):
        if not host:
            host = cfg.CONF.host
        self.host = host
        super(Manager, self).__init__()

    def periodic_tasks(self, context, raise_on_error=False):
        self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    def init_host(self):
        """Handle initialization if this is a standalone service.

        Child classes should override this method.

        """
        pass

    def after_start(self):
        """Handler post initialization stuff.

        Child classes can override this method.
        """
        pass


def validate_post_plugin_load():
    """Checks if the configuration variables are valid.

    If the configuration is invalid then the method will return an error
    message. If all is OK then it will return None.
    """
    if ('dhcp_agents_per_network' in cfg.CONF and
        cfg.CONF.dhcp_agents_per_network <= 0):
        msg = _("dhcp_agents_per_network must be >= 1. '%s' "
                "is invalid.") % cfg.CONF.dhcp_agents_per_network
        return msg


def validate_pre_plugin_load():
    """Checks if the configuration variables are valid.

    If the configuration is invalid then the method will return an error
    message. If all is OK then it will return None.
    """
    if cfg.CONF.core_plugin is None:
        msg = _('Neutron core_plugin not configured!')
        return msg


class NeutronManager(object):
    """Neutron's Manager class.

    Neutron's Manager class is responsible for parsing a config file and
    instantiating the correct plugin that concretely implement
    neutron_plugin_base class.
    The caller should make sure that NeutronManager is a singleton.
    """
    _instance = None

    def __init__(self, options=None, config_file=None):
        # If no options have been provided, create an empty dict
        if not options:
            options = {}

        msg = validate_pre_plugin_load()
        if msg:
            LOG.critical(msg)
            raise Exception(msg)

        # NOTE(jkoelker) Testing for the subclass with the __subclasshook__
        #                breaks tach monitoring. It has been removed
        #                intentianally to allow v2 plugins to be monitored
        #                for performance metrics.
        plugin_provider = cfg.CONF.core_plugin
        LOG.debug(_("Plugin location: %s"), plugin_provider)
        # If the plugin can't be found let them know gracefully
        try:
            LOG.info(_("Loading Plugin: %s"), plugin_provider)
            plugin_klass = importutils.import_class(plugin_provider)
        except ImportError:
            LOG.exception(_("Error loading plugin"))
            raise Exception(_("Plugin not found. "))
        legacy.modernize_quantum_config(cfg.CONF)
        self.plugin = plugin_klass()

        msg = validate_post_plugin_load()
        if msg:
            LOG.critical(msg)
            raise Exception(msg)

        # core plugin as a part of plugin collection simplifies
        # checking extensions
        # TODO(enikanorov): make core plugin the same as
        # the rest of service plugins
        self.service_plugins = {constants.CORE: self.plugin}
        self._load_service_plugins()

    def _load_services_from_core_plugin(self):
        """Puts core plugin in service_plugins for supported services."""
        LOG.debug(_("Loading services supported by the core plugin"))

        # supported service types are derived from supported extensions
        if not hasattr(self.plugin, "supported_extension_aliases"):
            return
        for ext_alias in self.plugin.supported_extension_aliases:
            if ext_alias in constants.EXT_TO_SERVICE_MAPPING:
                service_type = constants.EXT_TO_SERVICE_MAPPING[ext_alias]
                self.service_plugins[service_type] = self.plugin
                LOG.info(_("Service %s is supported by the core plugin"),
                         service_type)

    def _load_service_plugins(self):
        """Loads service plugins.

        Starts from the core plugin and checks if it supports
        advanced services then loads classes provided in configuration.
        """
        # load services from the core plugin first
        self._load_services_from_core_plugin()

        plugin_providers = cfg.CONF.service_plugins
        LOG.debug(_("Loading service plugins: %s"), plugin_providers)
        for provider in plugin_providers:
            if provider == '':
                continue
            try:
                LOG.info(_("Loading Plugin: %s"), provider)
                plugin_class = importutils.import_class(provider)
            except ImportError:
                LOG.exception(_("Error loading plugin"))
                raise ImportError(_("Plugin not found."))
            plugin_inst = plugin_class()

            # only one implementation of svc_type allowed
            # specifying more than one plugin
            # for the same type is a fatal exception
            if plugin_inst.get_plugin_type() in self.service_plugins:
                raise ValueError(_("Multiple plugins for service "
                                   "%s were configured"),
                                 plugin_inst.get_plugin_type())

            self.service_plugins[plugin_inst.get_plugin_type()] = plugin_inst

            LOG.debug(_("Successfully loaded %(type)s plugin. "
                        "Description: %(desc)s"),
                      {"type": plugin_inst.get_plugin_type(),
                       "desc": plugin_inst.get_plugin_description()})

    @classmethod
    @utils.synchronized("manager")
    def _create_instance(cls):
        if cls._instance is None:
            cls._instance = cls()

    @classmethod
    def get_instance(cls):
        # double checked locking
        if cls._instance is None:
            cls._create_instance()
        return cls._instance

    @classmethod
    def get_plugin(cls):
        return cls.get_instance().plugin

    @classmethod
    def get_service_plugins(cls):
        return cls.get_instance().service_plugins

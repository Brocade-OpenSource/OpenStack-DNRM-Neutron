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

from neutron.db import l3_db
from neutron.plugins.niblick import plugin_manager
from neutron.plugins.niblick import resource

# TODO(svilgelm): replace with "L3"
ROUTER_OBJECT_TYPE = 'com.router'


class Interceptor(l3_db.L3_NAT_db_mixin):
    def __init__(self):
        self._plugin_manager = plugin_manager.PluginManager()
        self._resource_manager = resource.ResourceManager()

    def _get_l2_plugin(self):
        l2_descriptor = self._plugin_manager.l2_descriptor
        return self._plugin_manager[l2_descriptor]

    def _get_plugin(self, context, object_id):
        resource = self._resource_manager.get_resource(context, object_id)
        descriptor = resource['resource_descriptor']
        return self._plugin_manager[descriptor]

    def _get_all_plugins(self, context, resource_type):
        for descriptor in self._resource_manager.get_descriptors(
            context, resource_type
        ):
            yield self._plugin_manager[descriptor]

    # L3

    def create_router(self, context, router):
        with self._resource_manager.allocate_resource(
            context,
            ROUTER_OBJECT_TYPE
        ) as resource:
            metadata = router.get('metadata', {})
            metadata.update(resource['resource_metadata'])
            router['metadata'] = metadata
            descriptor = resource['resource_descriptor']
            plugin = self._plugin_manager[descriptor]
            obj = plugin.create_router(context, router)
            self._resource_manager.bind_object(context, obj['id'], resource)
            return obj

    def update_router(self, context, id, router):
        plugin = self._get_plugin(context, id)
        return plugin.update_router(context, id, router)

    def get_router(self, context, id, fields=None):
        plugin = self._get_plugin(context, id)
        return plugin.get_router(context, id, fields)

    def delete_router(self, context, id):
        plugin = self._get_plugin(context, id)
        with self._resource_manager.deallocate_resource(context, id):
            plugin.delete_router(context, id)

    def get_routers(self, context, filters=None, fields=None,
                    sorts=None, limit=None, marker=None, page_reverse=False):
        res = {}
        for plugin in self._get_all_plugins(context, ROUTER_OBJECT_TYPE):
            routers = plugin.get_routers(context, filters, fields, sorts,
                                         limit, marker, page_reverse)
            for router in routers:
                router_id = router['id']
                if router_id not in res:
                    res[router_id] = router
        return res.values()

    def get_routers_count(self, context, filters=None):
        return len(self.get_routers(context, filters))

    def add_router_interface(self, context, router_id, interface_info):
        plugin = self._get_plugin(context, router_id)
        return plugin.add_router_interface(context, router_id, interface_info)

    def remove_router_interface(self, context, router_id, interface_info):
        plugin = self._get_plugin(context, router_id)
        plugin.remove_router_interface(context, router_id, interface_info)

    # L2

    def __getattr__(self, name):
        plugin = self._get_l2_plugin()
        return getattr(plugin, name)

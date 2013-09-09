# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012, OpenStack Foundation.
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
import contextlib

from neutron.openstack.common import excutils
from neutron.plugins.niblick.db import api as db_api
from neutron.plugins.niblick import exceptions as exc
from neutron.plugins.niblick import policy


class ResourceManager(object):
    def __init__(self):
        self._pm = policy.PolicyManager()

    @contextlib.contextmanager
    def allocate_resource(self, context, resource_type):
        resource = self._pm.acquire_resource(context, resource_type)
        resource['object_id'] = None
        try:
            yield resource
            if resource['object_id'] is None:
                raise exc.WrongObjectId(object_id=None)
        except Exception:
            with excutils.save_and_reraise_exception():
                self._pm.release_resource(context, resource['resource_id'])

    @contextlib.contextmanager
    def deallocate_resource(self, context, object_id):
        res = self.get_resource(context, object_id)
        yield res
        self._pm.release_resource(context, res['resource_id'])
        db_api.binding_delete(context, res['object_id'])

    def bind_object(self, context, object_id, resource):
        resource['object_id'] = object_id
        resource.update(dict(db_api.binding_add(context, resource)))

    def get_resource(self, context, object_id):
        obj = db_api.binding_get(context, object_id)
        return dict(obj)

    def get_descriptors(self, context, resource_type):
        descriptors = db_api.binding_get_descriptors(
            context, resource_type)
        return descriptors

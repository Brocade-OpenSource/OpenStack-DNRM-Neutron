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

import abc
import copy

from oslo.config import cfg

from neutron.openstack.common.importutils import import_class
from neutron.openstack.common.uuidutils import generate_uuid
from neutron.plugins.niblick import exceptions


policy_opts = [
    cfg.DictOpt('instances', default={},
                help=_("Dictionary of instances ids to IP mappings")),
    cfg.StrOpt(
        'policy_driver',
        default="neutron.plugins.niblick.supervisor_policy_driver."
                "SupervisorPolicyDriver", help=_("Niblick Policy driver"))
]

CONF = cfg.CONF
CONF.register_opts(policy_opts, "niblick")


class PolicyAPI(object):
    """Base abstract class for Policy driver"""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def acquire_resource(self, context, resource_type):
        pass

    @abc.abstractmethod
    def release_resource(self, context, resource_id):
        pass


class SimplePolicyDriver(PolicyAPI):
    """Proof-of-concept Policy driver"""

    def _create_resource(self, resource_type, instance_id, instance_ip):
        """Helper function for SupervisorLessPolicyDriver"""
        uuid = generate_uuid()
        return (uuid, {'resource_id': uuid,
                       'resource_type': resource_type,
                       'resource_metadata': {'instance_id': instance_id,
                                             'instance_ip': instance_ip},
                       'allocated': False,
                       'resource_descriptor': 'linuxbridge'})

    def __init__(self):
        res = []
        for inst_id, inst_ip in CONF.niblick.instances.iteritems():
            res.append(self._create_resource('router', inst_id, inst_ip))
        self._resources = dict(res)

    def acquire_resource(self, context, resource_type):
        for res in self._resources.itervalues():
            if not res['allocated'] and res['resource_type'] == resource_type:
                res['allocated'] = True
                return copy.deepcopy(res)
        raise exceptions.NoMoreResources(resource_type=resource_type)

    def release_resource(self, context, resource_id):
        try:
            self._resources[resource_id]['allocated'] = False
        except KeyError:
            raise exceptions.WrongResourceId(resource_id=resource_id)


class PolicyManager(PolicyAPI):
    def __init__(self):
        self.policy_driver = import_class(CONF.niblick.policy_driver)()

    def acquire_resource(self, context, resource_type):
        return self.policy_driver.acquire_resource(context, resource_type)

    def release_resource(self, context, resource_id):
        return self.policy_driver.release_resource(context, resource_id)

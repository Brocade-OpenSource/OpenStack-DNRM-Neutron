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

from oslo.config import cfg

from neutron.openstack.common.uuidutils import generate_uuid
from neutron.plugins.niblick import exceptions


instances_opts = [
    cfg.DictOpt('instances', default={},
                help=_("Dictionary of instances ids to IP mappings"))
]

CONF = cfg.CONF
CONF.register_opts(instances_opts, "niblick")


class PolicyAPI(object):
    """Base abstract class for Policy driver"""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def acquire_resource(self, context, resource_type):
        pass

    @abc.abstractmethod
    def release_resource(self, context, resource_id):
        pass


def create_resource_for_inst(res_type, instance_id, instance_ip):
    """Helper function for SupervisorLessPolicyDriver"""
    uuid = generate_uuid()
    return (uuid, {'id': uuid,
                   'type': res_type,
                   'metadata': {'instance_id': instance_id,
                                'instance_ip': instance_ip},
                   'allocated': False,
                   'descriptor': 'com.vyatta.vm'})


class SupervisorLessPolicyDriver(PolicyAPI):
    """Proof-of-concept Policy driver"""

    resource_type = 'router'

    def __init__(self):
        res = []
        for inst_id, inst_ip in CONF.niblick.instances.items():
            res.append(create_resource_for_inst(self.resource_type, inst_id,
                                                inst_ip))
        self._resources = dict(res)

    def acquire_resource(self, context, resource_type):
        for id_, res in self._resources.iteritems():
            if not res['allocated'] and res['type'] == resource_type:
                res['allocated'] = True
                return res
        raise exceptions.NoMoreResources()

    def release_resource(self, context, resource_id):
        try:
            self._resources[resource_id]['allocated'] = False
        except KeyError:
            raise exceptions.WrongResourceId()

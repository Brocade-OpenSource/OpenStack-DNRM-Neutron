# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation.
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
import httplib2
import urllib

from oslo.config import cfg

from neutron.openstack.common import jsonutils
from neutron.plugins.niblick import exceptions
from neutron.plugins.niblick import policy

supervisor_opts = [
    cfg.StrOpt('supervisor_host', default='localhost'),
    cfg.IntOpt('supervisor_port', default=8080),
    cfg.StrOpt('supervisor_version', default='v1')
]

CONF = cfg.CONF
CONF.register_opts(supervisor_opts, 'niblick')


class SupervisorPolicyDriver(policy.PolicyAPI):
    def __init__(self):
        self.host = CONF.niblick.supervisor_host
        self.port = CONF.niblick.supervisor_port
        version = CONF.niblick.supervisor_version
        self.url = '/%(version)s/resources/' % {'version': version}

    def _get(self, url, method='GET', body=None):
        if body is not None:
            body = jsonutils.dumps(body)
        conn = httplib2.HTTPConnectionWithTimeout(self.host, self.port)
        conn.request(method, url, body)
        resp = conn.getresponse()
        content = resp.read()
        if content:
            content = jsonutils.loads(content)
        return content

    def _list(self, resource_class):
        search_opts = {'limit': 1, 'class': resource_class,
                       'processing': False, 'unused': True}
        query = urllib.urlencode(search_opts)
        url = '%(url)s?%(query)s' % {'url': self.url, 'query': query}
        resp = self._get(url)['resources']
        return resp

    def _update(self, resource_id, allocated):
        body = {'resource': {'allocated': allocated}}
        url = '%(url)s%(resource_id)s' % {'url': self.url,
                                          'resource_id': resource_id}
        resp = self._get(url, 'PUT', body)
        return resp.get('resource')

    def acquire_resource(self, context, resource_class):
        resources = self._list(resource_class)
        if resources:
            resource = resources[0]
            resource = self._update(resource['id'], True)
            res = {'resource_id': resource.pop('id'),
                   'resource_type': resource_class,
                   'allocated': resource.pop('allocated'),
                   'resource_descriptor': resource.pop('type')}
            res['resource_metadata'] = resource
            return res
        raise exceptions.NoMoreResources(resource_type=resource_class)

    def release_resource(self, context, resource_id):
        resp = self._update(resource_id, False)
        if not resp:
            raise exceptions.WrongResourceId(resource_id=resource_id)

import hashlib
import hmac
import httplib
import json
import logging
import socket

from neutron.plugins.vyatta import exceptions
from neutron.plugins.vyatta import vrouter_db_v2
from oslo.config import cfg

from novaclient.v1_1 import client

LOG = logging.getLogger(__name__)


class ApiProxyClient(object):
    """APIProxyClient class to construct REST API client requests."""
    def __init__(self, server):
        self.server = server
        self.port = cfg.CONF.VROUTER.api_port

    def rest_call(self, action, uri, data):
        headers = {}

        if (data is not None):
            headers['Content-type'] = 'application/json'
            headers['Accept'] = 'application/json'

        private_key = cfg.CONF.VROUTER.api_private_key
        public_key = cfg.CONF.VROUTER.api_public_key
        content = json.dumps(data)
        hmac_digest = hmac.new(private_key, content, hashlib.sha1).hexdigest()

        headers['PublicKey'] = public_key
        headers['Hash'] = hmac_digest

        conn = httplib.HTTPConnection(self.server, self.port)
        if conn is None:
            LOG.error('ProxyClient: Could not establish HTTP connection.')
            raise exceptions.VRouterConnectFailure(ip_address=self.server)

        try:
            if (data is None):
                conn.request(action, uri, headers=headers)
            else:
                conn.request(action, uri, content, headers)

            response = conn.getresponse()
            response_data = json.loads(response.read())
            if response.status != 201:
                action_name = {
                    'GET': 'get',
                    'POST': 'create',
                    'PUT': 'update',
                    'DELETE': 'delete',
                }.get(action, 'do something with')
                raise exceptions.VRouterOperationError(
                    ip_address=self.server, action=action_name,
                    code=response.status, message=response_data)

            return_value = (response.status, response_data)
        except (socket.timeout, socket.error, ValueError) as exc:
            LOG.error(_('ProxyClient: Exception occurred while reading '
                        'the response: %s') % exc)
            raise exceptions.VRouterConnectFailure(ip_address=self.server)
        finally:
            conn.close()

        return return_value


def create_nova_client(context, tenant=None):
    if tenant is None:
        tenant_id = context.project_id
    else:
        tenant_id = None
    return client.Client(
        cfg.CONF.VROUTER.tenant_admin_name,
        cfg.CONF.VROUTER.tenant_admin_password,
        tenant, cfg.CONF.VROUTER.keystone_url, service_type="compute",
        tenant_id=tenant_id)


def allocate_instance(context, router):
    nova_client = create_nova_client(context, cfg.CONF.VROUTER.tenant_name)
    instances = nova_client.servers.findall()
    for instance in instances:
        if vrouter_db_v2.is_allocated(context.session, instance.id):
            continue
        ifs = instance.interface_list()
        if len(ifs) != 1:
            continue
        ip_address = ifs[0].fixed_ips[0]['ip_address']
        return ip_address, instance.id
    return None, None


def initialize_router(context, address, router):
    vrouter_client = ApiProxyClient(address)
    data = {
        'router': {
            'name': router.get('name', 'vyatta-router'),
            'admin_state_up': router.get('admin_state_up', False),
        }
    }
    vrouter_client.rest_call('POST', '/v2.0', data)


def deinitialize_router(context, address):
    vrouter_client = ApiProxyClient(address)
    vrouter_client.rest_call('DELETE', '/v2.0/router', None)


def attach_interface(context, port_id, instance_id):
    nova_client = create_nova_client(context)
    server = nova_client.servers.get(instance_id)
    server.interface_attach(port_id, None, None)


def detach_interface(context, port_id, instance_id):
    nova_client = create_nova_client(context)
    server = nova_client.servers.get(instance_id)
    server.interface_detach(port_id)


def configure_interface(context, address, interface_infos):
    vrouter_client = ApiProxyClient(address)
    for interface_info in interface_infos:
        data = {'router': {'router_interface_info': interface_info}}
        vrouter_client.rest_call(
            'PUT', '/v2.0/router/add_router_interface', data)


def deconfigure_interface(context, address, interface_infos):
    vrouter_client = ApiProxyClient(address)
    for interface_info in interface_infos:
        data = {'router': {'router_interface_info': interface_info}}
        vrouter_client.rest_call(
            'PUT', '/v2.0/router/remove_router_interface', data)


def configure_gateway(context, address, interface_infos):
    if len(interface_infos) != 1:
        raise exceptions.InvalidNumberIPsOnPort()
    vrouter_client = ApiProxyClient(address)
    data = {'router': {'external_gateway_info': interface_infos[0]}}
    vrouter_client.rest_call('PUT', '/v2.0/router', data)


def clear_gateway(context, address, interface_infos):
    vrouter_client = ApiProxyClient(address)
    data = {'router': {'external_gateway_info': None}}
    vrouter_client.rest_call('PUT', '/v2.0/router', data)


def assign_floating_ip(context, address, fixed_ip, floating_ip):
    vrouter_client = ApiProxyClient(address)
    data = {'router': {'router_floating_ip_info': {
            'floating_ip_address': floating_ip,
            'fixed_ip_address': fixed_ip}}}
    vrouter_client.rest_call('PUT', '/v2.0/router/assign_floating_ip', data)


def unassign_floating_ip(context, address, fixed_ip, floating_ip):
    vrouter_client = ApiProxyClient(address)
    data = {'router': {'router_floating_ip_info': {
            'floating_ip_address': floating_ip,
            'fixed_ip_address': fixed_ip}}}
    vrouter_client.rest_call('PUT', '/v2.0/router/unassign_floating_ip', data)

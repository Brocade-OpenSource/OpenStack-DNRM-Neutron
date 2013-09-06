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

from mock import patch, ANY, MagicMock

from neutron.common import constants as l3_constants
from neutron.common import exceptions as q_exc
from neutron import context
from neutron.db import api as db_api
from neutron.db import db_base_plugin_v2
from neutron.db import l3_db
from neutron.db import models_v2
from neutron.extensions import l3
from neutron.openstack.common import log as logging
from neutron.tests import base
from oslo.config import cfg

from neutron.plugins.vyatta import vrouter_control
from neutron.plugins.vyatta.vrouter_neutron_plugin import VyattaVRouterL3Mixin

VROUTER_CONTROL_FQN = 'neutron.plugins.vyatta.vrouter_control'
ALLOCATE_INSTANCE_FQN = VROUTER_CONTROL_FQN + '.allocate_instance'
INITIALIZE_ROUTER_FQN = VROUTER_CONTROL_FQN + '.initialize_router'
ATTACH_INTERFACE_FQN = VROUTER_CONTROL_FQN + '.attach_interface'
DETACH_INTERFACE_FQN = VROUTER_CONTROL_FQN + '.detach_interface'
CONFIGURE_INTERFACE_FQN = VROUTER_CONTROL_FQN + '.configure_interface'
DECONFIGURE_INTERFACE_FQN = VROUTER_CONTROL_FQN + '.deconfigure_interface'
CONFIGURE_GATEWAY_FQN = VROUTER_CONTROL_FQN + '.configure_gateway'
CLEAR_GATEWAY_FQN = VROUTER_CONTROL_FQN + '.clear_gateway'

VROUTER_DB_FQN = 'neutron.plugins.vyatta.vrouter_db_v2'
ADD_ROUTER_ADDRESS_BINDING_FQN = VROUTER_DB_FQN + '.add_router_address_binding'
GET_ROUTER_INSTANCE_FQN = VROUTER_DB_FQN + '.get_router_instance'


LOG = logging.getLogger(__name__)


class VRouterTestPlugin(VyattaVRouterL3Mixin, l3_db.L3_NAT_db_mixin,
                        db_base_plugin_v2.NeutronDbPluginV2):
    _dict_extend_functions = {}

    def _get_tenant_id_for_create(self, *args, **kwargs):
        return 'fake-tenant-id'


class VyattaVRouterDbTestCase(base.BaseTestCase):
    def setUp(self):
        self.context = context.get_admin_context()
        self.plugin = VRouterTestPlugin()

        self.allocate_instance_mock = self._mock(ALLOCATE_INSTANCE_FQN)
        self.initialize_router_mock = self._mock(INITIALIZE_ROUTER_FQN)
        self.attach_interface_mock = self._mock(ATTACH_INTERFACE_FQN)
        self.detach_interface_mock = self._mock(DETACH_INTERFACE_FQN)
        self.configure_interface_mock = self._mock(CONFIGURE_INTERFACE_FQN)
        self.deconfigure_interface_mock = self._mock(DECONFIGURE_INTERFACE_FQN)
        self.configure_gateway_mock = self._mock(CONFIGURE_GATEWAY_FQN)
        self.clear_gateway_mock = self._mock(CLEAR_GATEWAY_FQN)

        self.get_router_instance_mock = self._mock(GET_ROUTER_INSTANCE_FQN)
        self.add_router_address_binding_mock = \
            self._mock(ADD_ROUTER_ADDRESS_BINDING_FQN)

        # Predefine some return values
        self.allocate_instance_mock.return_value = \
            '8.8.8.8', 'fake-instance-id'
        self.get_router_instance_mock.return_value = \
            '8.8.8.8', 'fake-instance-id'

        # Create router DB record for testing
        session = self.context.session
        with session.begin(subtransactions=True):
            router_db = l3_db.Router(id='fake-router-id-1',
                                     tenant_id='fake-tenant-id',
                                     name='test-router',
                                     admin_state_up=True,
                                     status="ACTIVE")
            session.add(router_db)
            session.flush()
            self._make_net(1)
            self._make_net(2, is_external=True)
            self._make_port(1)
            self._make_subnet(1, '10.0.0')
            self._make_subnet(2, '10.0.1')
            self._make_subnet(3, '10.0.2')
            self._make_subnet(4, '1.1.1', net=2)
            self._make_fixed_ip(1, 1, '10.0.0.1')
        session.expunge_all()

        super(VyattaVRouterDbTestCase, self).setUp()

    def _make_net(self, n, is_shared=False, is_external=False):
        session = self.context.session
        network = models_v2.Network(id='fake-network-id-{0}'.format(n),
                                    tenant_id='fake-tenant-id',
                                    name='test-network-{0}'.format(n),
                                    status='ACTIVE',
                                    admin_state_up=True,
                                    shared=is_shared)
        session.add(network)
        session.flush()
        if is_external:
            extnet = l3_db.ExternalNetwork(
                network_id='fake-network-id-{0}'.format(n))
            session.add(extnet)
            session.flush()
        return network

    def _make_subnet(self, n, cidr_prefix, net=1):
        session = self.context.session
        subnet = models_v2.Subnet(id='fake-subnet-id-{0}'.format(n),
                                  tenant_id='fake-tenant-id',
                                  name='test-subnet-{0}'.format(n),
                                  network_id='fake-network-id-{0}'.format(net),
                                  ip_version=4,
                                  cidr='{0}.0/24'.format(cidr_prefix),
                                  gateway_ip='{0}.1'.format(cidr_prefix),
                                  enable_dhcp=True,
                                  shared=False)
        session.add(subnet)
        session.flush()
        ippool = models_v2.IPAllocationPool(
            id='allocation-pool-{0}'.format(n),
            subnet_id='fake-subnet-id-{0}'.format(n),
            first_ip='{0}.1'.format(cidr_prefix),
            last_ip='{0}.254'.format(cidr_prefix))
        session.add(ippool)
        session.flush()
        iprange = models_v2.IPAvailabilityRange(
            allocation_pool_id='allocation-pool-{0}'.format(n),
            first_ip='{0}.1'.format(cidr_prefix),
            last_ip='{0}.254'.format(cidr_prefix))
        session.add(iprange)
        session.flush()
        return subnet

    def _make_fixed_ip(self, port, subnet, ip, net=1):
        session = self.context.session
        ip_allocation = models_v2.IPAllocation(
            port_id='fake-port-id-{0}'.format(port),
            ip_address=ip,
            subnet_id='fake-subnet-id-{0}'.format(subnet),
            network_id='fake-network-id-{0}'.format(net))
        session.add(ip_allocation)
        session.flush()
        return ip_allocation

    def _make_port(self, port, device_id=None, device_owner=None, net=1):
        session = self.context.session
        port = models_v2.Port(tenant_id='fake-tenant-id',
                              name='',
                              id='fake-port-id-{0}'.format(port),
                              network_id='fake-network-id-{0}'.format(net),
                              mac_address='aa:bb:cc:dd:ee:f{0}'.format(port),
                              admin_state_up=True,
                              status='ACTIVE',
                              device_id=device_id or '',
                              device_owner=device_owner or '')
        session.add(port)
        session.flush()
        return port

    def _mock(self, function):
        patcher = patch(function)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def tearDown(self):
        db_api.clear_db()
        super(VyattaVRouterDbTestCase, self).tearDown()

    def test_create_router_allocation_failure(self):
        router = {'router': {'name': 'test_router1'}}
        self.allocate_instance_mock.return_value = None, None
        self.assertRaises(q_exc.BadRequest, self.plugin.create_router,
                          self.context, router)
        self.allocate_instance_mock.assert_called_once_with(
            self.context, router)

    def test_create_router(self):
        router = {'router': {'name': 'test_router1', 'admin_state_up': True}}
        result = self.plugin.create_router(self.context, router)
        self.add_router_address_binding_mock.assert_called_once_with(
            self.context.session, ANY, '8.8.8.8', 'fake-instance-id')
        self.initialize_router_mock.assert_called_once_with(
            self.context, '8.8.8.8', ANY)
        self.assertIn('id', result)
        self.assertEqual('test_router1', result.get('name'))
        self.assertEqual('fake-tenant-id', result.get('tenant_id'))

    def test_create_router_with_gw(self):
        router = {'router': {
            'name': 'test_router1',
            'admin_state_up': True,
            'external_gateway_info': {'network_id': 'fake-network-id-2'}}}
        result = self.plugin.create_router(self.context, router)
        self.add_router_address_binding_mock.assert_called_once_with(
            self.context.session, ANY, '8.8.8.8', 'fake-instance-id')
        self.initialize_router_mock.assert_called_once_with(
            self.context, '8.8.8.8', ANY)
        self.assertIn('id', result)
        self.assertEqual('test_router1', result.get('name'))
        self.assertEqual('fake-tenant-id', result.get('tenant_id'))

    def test_update_router(self):
        updated = self.plugin.update_router(
            self.context, 'fake-router-id-1', {'router': {'name': 'foo'}})
        self.assertEqual('foo', updated.get('name'))
        self.assertEqual('fake-tenant-id', updated.get('tenant_id'))

    def test_update_router_gw(self):
        self.plugin.update_router(
            self.context, 'fake-router-id-1',
            {'router': {'external_gateway_info': {
                'network_id': 'fake-network-id-2'}}})
        self.configure_gateway_mock.assert_called_once_with(
            self.context, '8.8.8.8', ANY)

        self.plugin.update_router(
            self.context, 'fake-router-id-1',
            {'router': {'external_gateway_info': None}})
        self.clear_gateway_mock.assert_called_once_with(
            self.context, '8.8.8.8', ANY)

    def test_get_router(self):
        router = self.plugin.get_router(self.context, 'fake-router-id-1')
        self.assertEqual('test-router', router.get('name'))
        self.assertEqual('fake-tenant-id', router.get('tenant_id'))

    def test_get_routers(self):
        routers = self.plugin.get_routers(self.context)
        self.assertEqual(1, len(routers))
        router = routers[0]
        self.assertEqual('test-router', router.get('name'))
        self.assertEqual('fake-tenant-id', router.get('tenant_id'))

    def test_get_non_existent_router(self):
        self.assertRaises(l3.RouterNotFound, self.plugin.get_router,
                          self.context, 'sorry, pal')

    def test_delete_router(self):
        self.plugin.delete_router(self.context, 'fake-router-id-1')
        self.assertRaises(l3.RouterNotFound, self.plugin.get_router,
                          self.context, 'fake-router-id-1')

    def test_add_router_interface_port_id_with_subnet_fail(self):
        interface_info = {'port_id': 'foo', 'subnet_id': 'bar'}
        self.assertRaises(q_exc.BadRequest, self.plugin.add_router_interface,
                          self.context, 'fake-router-id-1', interface_info)

    def test_add_router_interface_existing_port_fail(self):
        self._make_port(2, device_id='fake-router-id-1',
                        device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
        self._make_fixed_ip(2, 3, '10.0.2.1')

        interface_info = {'subnet_id': 'fake-subnet-id-3'}
        self.assertRaises(q_exc.BadRequest, self.plugin.add_router_interface,
                          self.context, 'fake-router-id-1', interface_info)

    def test_add_router_interface_existing_port_fail2(self):
        self._make_port(2, device_id='fake-router-id-1',
                        device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
        self._make_subnet(5, '10.0.2')
        self._make_fixed_ip(2, 5, '10.0.2.1')

        interface_info = {'subnet_id': 'fake-subnet-id-3'}
        self.assertRaises(q_exc.BadRequest, self.plugin.add_router_interface,
                          self.context, 'fake-router-id-1', interface_info)

    def test_add_router_interface_port(self):
        interface_info = {'port_id': 'fake-port-id-1'}
        self.plugin.add_router_interface(self.context, 'fake-router-id-1',
                                         interface_info)
        self.attach_interface_mock.assert_called_once_with(
            self.context, 'fake-port-id-1', 'fake-instance-id')
        self.configure_interface_mock.assert_called_once_with(
            self.context, '8.8.8.8', [{'mac_address': 'aa:bb:cc:dd:ee:f1',
                                       'ip_address': '10.0.0.1/24'}])

    def test_add_router_interface_port_attach_fail(self):
        self.attach_interface_mock.side_effect = RuntimeError('test')
        interface_info = {'subnet_id': 'fake-subnet-id-2'}
        self.assertRaises(RuntimeError, self.plugin.add_router_interface,
                          self.context, 'fake-router-id-1', interface_info)

    def test_add_router_interface_subnet(self):
        interface_info = {'subnet_id': 'fake-subnet-id-2'}
        self.plugin.add_router_interface(self.context, 'fake-router-id-1',
                                         interface_info)
        self.attach_interface_mock.assert_called_once_with(
            self.context, ANY, 'fake-instance-id')
        self.configure_interface_mock.assert_called_once_with(
            self.context, '8.8.8.8', [{'mac_address': ANY,
                                       'ip_address': '10.0.1.1/24'}])

    def test_remove_router_interface_invalid_data_fail(self):
        interface_info = {}
        self.assertRaises(q_exc.BadRequest,
                          self.plugin.remove_router_interface, self.context,
                          'fake-router-id-1', interface_info)

    def test_remove_router_interface_unattached_port_fail(self):
        interface_info = {'port_id': 'fake-port-id-1'}
        self.assertRaises(l3.RouterInterfaceNotFound,
                          self.plugin.remove_router_interface, self.context,
                          'fake-router-id-1', interface_info)

    def test_remove_router_interface_invalid_subnet_fail(self):
        self._make_port(2, device_id='fake-router-id-1',
                        device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
        self._make_fixed_ip(2, 3, '10.0.2.1')

        interface_info = {'port_id': 'fake-port-id-2',
                          'subnet_id': 'fake-subnet-id-1'}
        self.assertRaises(q_exc.SubnetMismatchForPort,
                          self.plugin.remove_router_interface, self.context,
                          'fake-router-id-1', interface_info)

    def test_remove_router_interface_by_port(self):
        self._make_port(2, device_id='fake-router-id-1',
                        device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
        self._make_fixed_ip(2, 3, '10.0.2.1')

        interface_info = {'port_id': 'fake-port-id-2',
                          'subnet_id': 'fake-subnet-id-3'}
        self.plugin.remove_router_interface(self.context, 'fake-router-id-1',
                                            interface_info)
        self.detach_interface_mock.assert_called_once_with(
            self.context, ANY, 'fake-instance-id')
        self.deconfigure_interface_mock.assert_called_once_with(
            self.context, '8.8.8.8', [{'mac_address': 'aa:bb:cc:dd:ee:f2',
                                       'ip_address': '10.0.2.1/24'}])

    def test_remove_router_interface_by_subnet(self):
        self._make_port(2, device_id='fake-router-id-1',
                        device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF)
        self._make_fixed_ip(2, 3, '10.0.2.1')

        interface_info = {'subnet_id': 'fake-subnet-id-3'}
        self.plugin.remove_router_interface(self.context, 'fake-router-id-1',
                                            interface_info)
        self.detach_interface_mock.assert_called_once_with(
            self.context, ANY, 'fake-instance-id')
        self.deconfigure_interface_mock.assert_called_once_with(
            self.context, '8.8.8.8', [{'mac_address': 'aa:bb:cc:dd:ee:f2',
                                       'ip_address': '10.0.2.1/24'}])


class VyattaVRouterControlTestCase(base.BaseTestCase):
    def setUp(self):
        self.context = context.get_admin_context()

        patcher = patch('httplib.HTTPConnection')
        self.addCleanup(patcher.stop)
        self.httplib_mock = patcher.start()

        response = MagicMock()
        response.read.return_value = '{}'
        response.status = 201
        self.httplib_mock.return_value.getresponse.return_value = response

        cfg.CONF.set_override('api_private_key', 'foo', 'VROUTER')
        cfg.CONF.set_override('api_public_key', 'bar', 'VROUTER')
        super(VyattaVRouterControlTestCase, self).setUp()

    def tearDown(self):
        super(VyattaVRouterControlTestCase, self).tearDown()

    def test_initialize_router(self):
        vrouter_control.initialize_router(self.context, '8.8.8.8', {})
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with('POST', '/v2.0', ANY, ANY)

    def test_deinitialize_router(self):
        vrouter_control.deinitialize_router(self.context, '8.8.8.8')
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with(
            'DELETE', '/v2.0/router', headers=ANY)

    def test_configure_interface(self):
        vrouter_control.configure_interface(self.context, '8.8.8.8', [{}])
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with(
            'PUT', '/v2.0/router/add_router_interface', ANY, ANY)

    def test_deconfigure_interface(self):
        vrouter_control.deconfigure_interface(self.context, '8.8.8.8', [{}])
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with(
            'PUT', '/v2.0/router/remove_router_interface', ANY, ANY)

    def test_configure_gateway(self):
        vrouter_control.configure_gateway(self.context, '8.8.8.8', [{}])
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with('PUT', '/v2.0/router', ANY, ANY)

    def test_clear_gateway(self):
        vrouter_control.clear_gateway(self.context, '8.8.8.8', [{}])
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with('PUT', '/v2.0/router', ANY, ANY)

    def test_assign_floating_ip(self):
        vrouter_control.assign_floating_ip(
            self.context, '8.8.8.8', '10.0.0.3', '8.8.8.10')
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with(
            'PUT', '/v2.0/router/assign_floating_ip', ANY, ANY)

    def test_unassign_floating_ip(self):
        vrouter_control.unassign_floating_ip(
            self.context, '8.8.8.8', '10.0.0.3', '8.8.8.10')
        self.httplib_mock.assert_called_once_with('8.8.8.8', 5000)
        conn = self.httplib_mock.return_value
        conn.request.assert_called_once_with(
            'PUT', '/v2.0/router/unassign_floating_ip', ANY, ANY)


class VyattaVRouterControlNovaTestCase(base.BaseTestCase):
    def setUp(self):
        self.context = context.get_admin_context()

        self.create_nova_client_mock = \
            self._mock(VROUTER_CONTROL_FQN + '.create_nova_client')
        self.is_allocated_mock = \
            self._mock(VROUTER_DB_FQN + '.is_allocated')

        super(VyattaVRouterControlNovaTestCase, self).setUp()

    def tearDown(self):
        super(VyattaVRouterControlNovaTestCase, self).tearDown()

    def _mock(self, function):
        patcher = patch(function)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_attach_interface(self):
        vrouter_control.attach_interface(
            self.context, 'port-id', 'instance-id')
        client = self.create_nova_client_mock.return_value
        client.servers.get.assert_called_once_with('instance-id')
        server = client.servers.get.return_value
        server.interface_attach.assert_called_once_with('port-id', None, None)

    def test_detach_interface(self):
        vrouter_control.detach_interface(
            self.context, 'port-id', 'instance-id')
        client = self.create_nova_client_mock.return_value
        client.servers.get.assert_called_once_with('instance-id')
        server = client.servers.get.return_value
        server.interface_detach.assert_called_once_with('port-id')

    def test_allocate_instance(self):
        iface = MagicMock()
        iface.fixed_ips = [{'ip_address': '8.8.8.8'}]
        instance = MagicMock()
        instance.id = 'instance-id'
        instance.interface_list.return_value = [iface]

        client = self.create_nova_client_mock.return_value
        client.servers.findall.return_value = [instance]

        self.is_allocated_mock.return_value = False

        ip_addr, vm_id = vrouter_control.allocate_instance(
            self.context, 'router-id')
        self.is_allocated_mock.assert_called_once_with(
            self.context.session, 'instance-id')
        self.assertEqual('8.8.8.8', ip_addr)
        self.assertEqual('instance-id', vm_id)

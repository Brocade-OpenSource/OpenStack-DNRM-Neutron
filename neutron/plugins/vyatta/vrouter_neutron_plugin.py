import logging
import netaddr

from sqlalchemy.orm import exc

from neutron.api.v2 import attributes
from neutron.common import constants as l3_constants
from neutron.common import exceptions as q_exc
from neutron.db import l3_db
from neutron.db import models_v2
from neutron.extensions import l3
from neutron.openstack.common import excutils
from neutron.openstack.common.notifier import api as notifier_api

from neutron.plugins.linuxbridge import lb_neutron_plugin
from neutron.plugins.vyatta import config  # noqa
from neutron.plugins.vyatta import vrouter_control as control
from neutron.plugins.vyatta import vrouter_db_v2

ROUTER_ADDRESS = 'vrouter:address'
ROUTER_INSTANCE = 'vrouter:instance'
LOG = logging.getLogger(__name__)


class VyattaVRouterL3Mixin(l3.RouterPluginBase):
    def create_router(self, context, router):
        r = router['router']
        address = r.get(ROUTER_ADDRESS)
        instance_id = r.get(ROUTER_INSTANCE)

        # TODO(anfrolov): check that address is in management subnet
        if address is None or instance_id is None:
            address, instance_id = control.allocate_instance(context, router)
            if address is None or instance_id is None:
                raise q_exc.BadRequest(
                    resource='router',
                    msg=_('No free Vyatta vRouter instances left'))
        has_gw_info = False
        if l3.EXTERNAL_GW_INFO in r:
            has_gw_info = True
            gw_info = r[l3.EXTERNAL_GW_INFO]
            del r[l3.EXTERNAL_GW_INFO]
        tenant_id = self._get_tenant_id_for_create(context, r)
        with context.session.begin(subtransactions=True):
            router_db = l3_db.Router(id=instance_id,
                                     tenant_id=tenant_id,
                                     name=r['name'],
                                     admin_state_up=r['admin_state_up'],
                                     status="ACTIVE")
            context.session.add(router_db)

            # Save association between router and instance
            vrouter_db_v2.add_router_address_binding(
                context.session, router_db, address, instance_id)
            retval = self._make_router_dict(router_db)
            control.initialize_router(context, address, retval)

        if has_gw_info:
            self._update_router_gw_info(context, router_db['id'], gw_info)
        return retval

    def update_router(self, context, id, router):
        r = router['router']
        has_gw_info = False
        if l3.EXTERNAL_GW_INFO in r:
            has_gw_info = True
            gw_info = r[l3.EXTERNAL_GW_INFO]
            del r[l3.EXTERNAL_GW_INFO]
        if has_gw_info:
            self._update_router_gw_info(context, id, gw_info)
        with context.session.begin(subtransactions=True):
            router_db = self._get_router(context, id)
            # Ensure we actually have something to update
            if r.keys():
                router_db.update(r)
        return self._make_router_dict(router_db)

    def get_router(self, context, id, fields=None):
        router = self._get_router(context, id)
        return self._make_router_dict(router, fields)

    def delete_router(self, context, id):
        with context.session.begin(subtransactions=True):
            router = self._get_router(context, id)

            # Ensure that the router is not used
            fips = self.get_floatingips_count(context,
                                              filters={'router_id': [id]})
            if fips:
                raise l3.RouterInUse(router_id=id)

            # Get instance_id and address to send wipe command and detach
            # gateway port if there is any.
            address, instance_id = vrouter_db_v2.get_router_instance(
                context.session, id)

            device_filter = {
                'device_id': [id],
                'device_owner': [l3_constants.DEVICE_OWNER_ROUTER_INTF]
            }
            ports = self.get_ports_count(context, filters=device_filter)
            if ports:
                raise l3.RouterInUse(router_id=id)

            # delete any gw port
            device_filter = {
                'device_id': [id],
                'device_owner': [l3_constants.DEVICE_OWNER_ROUTER_GW]
            }
            ports = self.get_ports(context, filters=device_filter)
            if ports:
                port = ports[0]
                self._delete_router_port(
                    context, id, port, instance_id, address)

            try:
                control.deinitialize_router(context, address)
            except Exception as ex:
                LOG.error(_('Failed to deinitialize router: %s') % ex)
            context.session.delete(router)

    def get_routers(self, context, filters=None, fields=None,
                    sorts=None, limit=None, marker=None, page_reverse=False):
        marker_obj = self._get_marker_obj(context, 'router', limit, marker)
        return self._get_collection(context, l3_db.Router,
                                    self._make_router_dict, filters=filters,
                                    fields=fields, sorts=sorts, limit=limit,
                                    marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def add_router_interface(self, context, router_id, interface_info):
        if not interface_info:
            msg = _("Either subnet_id or port_id must be specified")
            raise q_exc.BadRequest(resource='router', msg=msg)

        if 'port_id' in interface_info:
            # make sure port update is committed
            with context.session.begin(subtransactions=True):
                if 'subnet_id' in interface_info:
                    msg = _("Cannot specify both subnet-id and port-id")
                    raise q_exc.BadRequest(resource='router', msg=msg)

                port = self._get_port(context, interface_info['port_id'])
                if port['device_id']:
                    raise q_exc.PortInUse(net_id=port['network_id'],
                                          port_id=port['id'],
                                          device_id=port['device_id'])
                fixed_ips = [ip for ip in port['fixed_ips']]
                if len(fixed_ips) != 1:
                    msg = _('Router port must have exactly one fixed IP')
                    raise q_exc.BadRequest(resource='router', msg=msg)
                subnet_id = fixed_ips[0]['subnet_id']
                subnet = self._get_subnet(context, subnet_id)
                self._check_for_dup_router_subnet(context, router_id,
                                                  port['network_id'],
                                                  subnet['id'],
                                                  subnet['cidr'])
            port_created = False
        elif 'subnet_id' in interface_info:
            subnet_id = interface_info['subnet_id']
            subnet = self._get_subnet(context, subnet_id)
            # Ensure the subnet has a gateway
            if not subnet['gateway_ip']:
                msg = _('Subnet for router interface must have a gateway IP')
                raise q_exc.BadRequest(resource='router', msg=msg)
            self._check_for_dup_router_subnet(context, router_id,
                                              subnet['network_id'],
                                              subnet_id,
                                              subnet['cidr'])
            fixed_ip = {'ip_address': subnet['gateway_ip'],
                        'subnet_id': subnet['id']}
            port = self.create_port(context, {
                'port':
                {'tenant_id': subnet['tenant_id'],
                 'network_id': subnet['network_id'],
                 'fixed_ips': [fixed_ip],
                 'mac_address': attributes.ATTR_NOT_SPECIFIED,
                 'admin_state_up': True,
                 'device_id': router_id,
                 'device_owner': l3_constants.DEVICE_OWNER_ROUTER_INTF,
                 'name': ''}})
            port_created = True

        try:
            self._attach_port(context, router_id, port)
        except Exception:
            with excutils.save_and_reraise_exception():
                if port_created:
                    try:
                        self.delete_port(context, port['id'])
                    except Exception:
                        LOG.exception(
                            _('Failed to delete previously created port.'))
        info = {'id': router_id,
                'tenant_id': subnet['tenant_id'],
                'port_id': port['id'],
                'subnet_id': port['fixed_ips'][0]['subnet_id']}
        notifier_api.notify(
            context, notifier_api.publisher_id('network'),
            'router.interface.create',
            notifier_api.CONF.default_notification_level,
            {'router.interface': info})
        return info

    def remove_router_interface(self, context, router_id, interface_info):
        if not interface_info:
            msg = _("Either subnet_id or port_id must be specified")
            raise q_exc.BadRequest(resource='router', msg=msg)
        address, instance_id = vrouter_db_v2.get_router_instance(
            context.session, router_id)
        if 'port_id' in interface_info:
            port_id = interface_info['port_id']
            port_db = self._get_port(context, port_id)
            if not (port_db['device_owner'] ==
                    l3_constants.DEVICE_OWNER_ROUTER_INTF and
                    port_db['device_id'] == router_id):
                raise l3.RouterInterfaceNotFound(router_id=router_id,
                                                 port_id=port_id)
            if 'subnet_id' in interface_info:
                port_subnet_id = port_db['fixed_ips'][0]['subnet_id']
                if port_subnet_id != interface_info['subnet_id']:
                    raise q_exc.SubnetMismatchForPort(
                        port_id=port_id,
                        subnet_id=interface_info['subnet_id'])
            subnet_id = port_db['fixed_ips'][0]['subnet_id']
            subnet = self._get_subnet(context, subnet_id)
            self._confirm_router_interface_not_in_use(
                context, router_id, subnet_id)
            port = port_db
        elif 'subnet_id' in interface_info:
            subnet_id = interface_info['subnet_id']
            self._confirm_router_interface_not_in_use(context, router_id,
                                                      subnet_id)
            subnet = self._get_subnet(context, subnet_id)
            found = False
            try:
                rport_qry = context.session.query(models_v2.Port)
                ports = rport_qry.filter_by(
                    device_id=router_id,
                    device_owner=l3_constants.DEVICE_OWNER_ROUTER_INTF,
                    network_id=subnet['network_id'])

                for p in ports:
                    if p['fixed_ips'][0]['subnet_id'] == subnet_id:
                        port = p
                        found = True
                        break
            except exc.NoResultFound:
                pass

            if not found:
                raise l3.RouterInterfaceNotFoundForSubnet(router_id=router_id,
                                                          subnet_id=subnet_id)

        self._delete_router_port(
            context, router_id, port, instance_id, address)
        info = {'id': router_id,
                'tenant_id': subnet['tenant_id'],
                'port_id': port['id'],
                'subnet_id': subnet_id}
        notifier_api.notify(context,
                            notifier_api.publisher_id('network'),
                            'router.interface.delete',
                            notifier_api.CONF.default_notification_level,
                            {'router.interface': info})
        return info

    def _make_router_dict(self, router, fields=None,
                          process_extensions=True):
        res = {'id': router['id'],
               'name': router['name'],
               'tenant_id': router['tenant_id'],
               'admin_state_up': router['admin_state_up'],
               'status': router['status'],
               l3.EXTERNAL_GW_INFO: None,
               'gw_port_id': router['gw_port_id']}
        if router['gw_port_id']:
            nw_id = router.gw_port['network_id']
            res[l3.EXTERNAL_GW_INFO] = {'network_id': nw_id}
        if process_extensions:
            for func in self._dict_extend_functions.get(l3.ROUTERS, []):
                func(self, res, router)
        return self._fields(res, fields)

    def _get_router(self, context, id):
        try:
            router = self._get_by_id(context, l3_db.Router, id)
        except exc.NoResultFound:
            raise l3.RouterNotFound(router_id=id)
        return router

    def _check_for_dup_router_subnet(self, context, router_id,
                                     network_id, subnet_id, subnet_cidr):
        try:
            rport_qry = context.session.query(models_v2.Port)
            rports = rport_qry.filter_by(device_id=router_id)
            # its possible these ports on on the same network, but
            # different subnet
            new_ipnet = netaddr.IPNetwork(subnet_cidr)
            for p in rports:
                for ip in p['fixed_ips']:
                    if ip['subnet_id'] == subnet_id:
                        msg = (_("Router already has a port on subnet %s")
                               % subnet_id)
                        raise q_exc.BadRequest(resource='router', msg=msg)
                    sub_id = ip['subnet_id']
                    cidr = self._get_subnet(context.elevated(),
                                            sub_id)['cidr']
                    ipnet = netaddr.IPNetwork(cidr)
                    match1 = netaddr.all_matching_cidrs(new_ipnet, [cidr])
                    match2 = netaddr.all_matching_cidrs(ipnet, [subnet_cidr])
                    if match1 or match2:
                        data = {'subnet_cidr': subnet_cidr,
                                'subnet_id': subnet_id,
                                'cidr': cidr,
                                'sub_id': sub_id}
                        msg = (_("Cidr %(subnet_cidr)s of subnet "
                                 "%(subnet_id)s overlaps with cidr %(cidr)s "
                                 "of subnet %(sub_id)s") % data)
                        raise q_exc.BadRequest(resource='router', msg=msg)
        except exc.NoResultFound:
            pass

    def _get_interface_infos(self, context, port):
        mac_address = port['mac_address']
        interface_infos = []
        for fip in port['fixed_ips']:
            try:
                subnet = self._get_subnet(context, fip['subnet_id'])
                ipnet = netaddr.IPNetwork(subnet.cidr)
                interface_infos.append({
                    'mac_address': mac_address,
                    'ip_address': '{0}/{1}'.format(fip['ip_address'],
                                                   ipnet.prefixlen)
                })
            except q_exc.SubnetNotFound:
                pass
        return interface_infos

    def _delete_router_port(self, context, router_id, port,
                            instance_id=None, address=None, external_gw=False):
        # Get instance, deconfigure interface and detach port from it. To do
        # this need to change port owner back to that instance.
        if instance_id is None or address is None:
            address, instance_id = vrouter_db_v2.get_router_instance(
                context.session, router_id)
        try:
            control.deconfigure_interface(
                context, address, self._get_interface_infos(context, port))
        except Exception as ex:
            LOG.error(_('Failed to deinitialize port: %s') % ex)
        self.update_port(context, port['id'],
                         {'port': {'device_owner': '',
                                   'device_id': instance_id}})
        control.detach_interface(context, port['id'], instance_id)

    def _attach_port(self, context, router_id, port,
                     instance_id=None, address=None, external_gw=False):
        # Get instance_id, attatch interface to it and send command to
        # configure that interface
        if instance_id is None or address is None:
            address, instance_id = vrouter_db_v2.get_router_instance(
                context.session, router_id)
        # Attach interface
        control.attach_interface(context, port['id'], instance_id)
        context.session.expunge(self._get_port(context, port['id']))
        # Configure interface
        if external_gw:
            device_owner = l3_constants.DEVICE_OWNER_ROUTER_GW
        else:
            device_owner = l3_constants.DEVICE_OWNER_ROUTER_INTF
        self.update_port(context, port['id'],
                         {'port': {'device_owner': device_owner,
                                   'device_id': router_id}})
        if external_gw:
            control.configure_gateway(
                context, address, self._get_interface_infos(context, port))
        else:
            control.configure_interface(
                context, address, self._get_interface_infos(context, port))

    def _update_router_gw_info(self, context, router_id, info, router=None):
        # TODO(salvatore-orlando): guarantee atomic behavior also across
        # operations that span beyond the model classes handled by this
        # class (e.g.: delete_port)
        router = router or self._get_router(context, router_id)
        gw_port = router.gw_port
        # network_id attribute is required by API, so it must be present
        network_id = info['network_id'] if info else None
        if network_id:
            network_db = self._get_network(context, network_id)
            if not network_db.external:
                msg = _("Network %s is not a valid external "
                        "network") % network_id
                raise q_exc.BadRequest(resource='router', msg=msg)

        # Get corresponding vRouter instance info
        address, instance_id = vrouter_db_v2.get_router_instance(
            context.session, router_id)

        # figure out if we need to delete existing port
        if gw_port and gw_port['network_id'] != network_id:
            fip_count = self.get_floatingips_count(context.elevated(),
                                                   {'router_id': [router_id]})
            if fip_count:
                raise l3.RouterExternalGatewayInUseByFloatingIp(
                    router_id=router_id, net_id=gw_port['network_id'])
            if gw_port and gw_port['network_id'] != network_id:
                with context.session.begin(subtransactions=True):
                    router.gw_port = None
                    context.session.add(router)
                try:
                    control.clear_gateway(
                        context, address,
                        self._get_interface_infos(context, gw_port))
                except Exception:
                    LOG.exception(_('Failed to clear router gateway.'))
                self._delete_router_port(
                    context, router_id, gw_port,
                    instance_id, address, external_gw=True)

        if network_id is not None and (gw_port is None or
                                       gw_port['network_id'] != network_id):
            subnets = self._get_subnets_by_network(context, network_id)
            for subnet in subnets:
                self._check_for_dup_router_subnet(context, router_id,
                                                  network_id, subnet['id'],
                                                  subnet['cidr'])
            gw_port = self.create_port(context.elevated(), {
                'port': {'tenant_id': '',  # intentionally not set
                         'network_id': network_id,
                         'mac_address': attributes.ATTR_NOT_SPECIFIED,
                         'fixed_ips': attributes.ATTR_NOT_SPECIFIED,
                         'device_owner': l3_constants.DEVICE_OWNER_ROUTER_GW,
                         'device_id': router['id'],
                         'admin_state_up': True,
                         'name': ''}})

            if not gw_port['fixed_ips']:
                self.delete_port(context.elevated(), gw_port['id'],
                                 l3_port_check=False)
                msg = (_('No IPs available for external network %s') %
                       network_id)
                raise q_exc.BadRequest(resource='router', msg=msg)

            with context.session.begin(subtransactions=True):
                address, instance_id = vrouter_db_v2.get_router_instance(
                    context.session, router_id)
                router.gw_port = self._get_port(context.elevated(),
                                                gw_port['id'])
                context.session.add(router)
            try:
                self._attach_port(context, router_id, gw_port,
                                  instance_id, address, external_gw=True)
            except Exception:
                with excutils.save_and_reraise_exception():
                    try:
                        with context.session.begin(subtransactions=True):
                            router.gw_port = None
                            context.session.add(router)
                    except Exception:
                        LOG.exception(_('Failed to roll back changes to '
                                        'router after external gateway '
                                        'assignment.'))

    def _confirm_router_interface_not_in_use(self, context, router_id,
                                             subnet_id):
        subnet_db = self._get_subnet(context, subnet_id)
        subnet_cidr = netaddr.IPNetwork(subnet_db['cidr'])
        fip_qry = context.session.query(l3_db.FloatingIP)
        for fip_db in fip_qry.filter_by(router_id=router_id):
            if netaddr.IPAddress(fip_db['fixed_ip_address']) in subnet_cidr:
                raise l3.RouterInterfaceInUseByFloatingIP(
                    router_id=router_id, subnet_id=subnet_id)

    def get_routers_count(self, context, filters=None):
        return self._get_collection_count(context, l3_db.Router,
                                          filters=filters)

    def router_assoc_floatingip(self, context, router_id, floatingip,
                                operation=None):
        address, _ = vrouter_db_v2.get_router_instance(
            context.session, router_id)
        floating_ip = floatingip['floating_ip_address']
        fixed_ip = floatingip['fixed_ip_address']
        control.assign_floating_ip(context, address, fixed_ip, floating_ip)

    def router_dissoc_floatingip(self, context, router_id, floatingip,
                                 operation=None):
        address, _ = vrouter_db_v2.get_router_instance(
            context.session, router_id)
        floating_ip = floatingip['floating_ip_address']
        fixed_ip = floatingip['fixed_ip_address']
        try:
            control.unassign_floating_ip(
                context, address, fixed_ip, floating_ip)
        except Exception:
            LOG.exception(_('Failed to dissociate floating IP.'))


class VyattaVRouterPlugin(VyattaVRouterL3Mixin,
                          lb_neutron_plugin.LinuxBridgePluginV2):
    pass

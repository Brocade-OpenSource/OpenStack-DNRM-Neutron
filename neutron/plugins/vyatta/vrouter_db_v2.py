from neutron.plugins.vyatta import vrouter_models_v2


def add_router_address_binding(session, router, ip_address, instance_id):
    binding = vrouter_models_v2.RouterAddress(
        router=router, ip_address=ip_address, instance_id=instance_id)
    session.add(binding)
    return binding


def get_router_instance(session, router_id):
    binding = session.query(vrouter_models_v2.RouterAddress).get(router_id)
    if binding is not None:
        return binding.ip_address, binding.instance_id
    else:
        return None, None


def is_allocated(session, instance_id):
    return session.query(vrouter_models_v2.RouterAddress)\
        .filter_by(instance_id=instance_id).count() != 0

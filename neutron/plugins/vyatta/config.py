from oslo.config import cfg

vrouter_plugin_opts = [
    cfg.IntOpt('api_port', default=5000,
               help=_('On which port DNRM API proxy for Vyatta vRouter '
                      'runs.')),
    cfg.StrOpt('api_public_key',
               help=_('Vyatta API proxy private key.')),
    cfg.StrOpt('api_private_key',
               help=_('Vyatta API proxy public key.')),
    cfg.StrOpt('tenant_name',
               help=_('Name of tenant that holds Vyatta vRouter instances.')),
    cfg.StrOpt('tenant_id',
               help=_('UUID of tenant that holds Vyatta vRouter instances.')),
    cfg.StrOpt('tenant_admin_name', help=_('Name of tenant admin user.')),
    cfg.StrOpt('tenant_admin_password', help=_('Tenant admin password.')),
    cfg.StrOpt('keystone_url', help=_('Keystone URL.')),

]

cfg.CONF.register_opts(vrouter_plugin_opts, "VROUTER")

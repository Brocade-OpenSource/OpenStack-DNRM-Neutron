# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation
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
#

"""Add portbindings db

Revision ID: 176a85fc7d79
Revises: grizzly
Create Date: 2013-03-21 14:59:53.052600

"""

# revision identifiers, used by Alembic.
revision = '176a85fc7d79'
down_revision = 'grizzly'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    'neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2',
    'neutron.plugins.linuxbridge.lb_neutron_plugin.LinuxBridgePluginV2',
    'neutron.plugins.niblick.interceptor_plugin.Interceptor',
]

from alembic import op
import sqlalchemy as sa

from neutron.db import migration


def upgrade(active_plugin=None, options=None):
    if not migration.should_run(active_plugin, migration_for_plugins):
        return

    op.create_table(
        'portbindingports',
        sa.Column('port_id', sa.String(length=36), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['port_id'], ['ports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('port_id')
    )


def downgrade(active_plugin=None, options=None):
    if not migration.should_run(active_plugin, migration_for_plugins):
        return
    op.drop_table('portbindingports')

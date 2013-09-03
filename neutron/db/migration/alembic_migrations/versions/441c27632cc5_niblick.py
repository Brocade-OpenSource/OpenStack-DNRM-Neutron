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

"""Niblick

Revision ID: 441c27632cc5
Revises: 477a4488d3f4
Create Date: 2013-08-22 15:01:49.427783

"""

# revision identifiers, used by Alembic.
revision = '441c27632cc5'
down_revision = '477a4488d3f4'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = ['*']

from alembic import op
import sqlalchemy as sa

from neutron.db import migration
from neutron.plugins.niblick.db import db_types


def upgrade(active_plugin=None, options=None):
    if not migration.should_run(active_plugin, migration_for_plugins):
        return

    op.create_table(
        'niblick_bindings',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
        sa.Column('deleted_at', sa.DateTime),
        sa.Column('deleted', sa.Integer, default=0),
        sa.Column('object_id', sa.String(length=36), nullable=False),
        sa.Column('resource_type', sa.String(length=255), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=False),
        sa.Column('resource_metadata', db_types.JsonBlob(length=255),
                  nullable=True),
        sa.Column('resource_descriptor', sa.String(length=255),
                  nullable=False),
        sa.schema.UniqueConstraint('object_id', 'deleted',
                                   name='niblick_bindings_uniq'),
    )


def downgrade(active_plugin=None, options=None):
    if not migration.should_run(active_plugin, migration_for_plugins):
        return

    op.drop_table('niblick_bindings')

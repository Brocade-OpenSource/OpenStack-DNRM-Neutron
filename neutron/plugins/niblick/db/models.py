# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012, OpenStack Foundation.
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

from sqlalchemy import Column, String, Integer
from sqlalchemy import schema

from neutron.db import model_base
from neutron.openstack.common.db.sqlalchemy import models
from neutron.plugins.niblick.db import types as db_types


class NiblickBinding(model_base.BASEV2,
                     models.SoftDeleteMixin,
                     models.TimestampMixin):
    """Represents a binding of object_id to resource."""

    __tablename__ = 'niblick_bindings'
    __table_args__ = (schema.UniqueConstraint("object_id", "deleted",
                                              name='niblick_bindings_uniq'),)

    id = Column(Integer, primary_key=True)
    object_id = Column(String(36), nullable=False)
    resource_type = Column(String(255), nullable=False)
    resource_id = Column(String(36), nullable=False)
    resource_metadata = Column(db_types.JsonBlob(), nullable=True)
    resource_descriptor = Column(String(255), nullable=False)

    def __repr__(self):
        return "<NiblickBinding(%s,%s)>" % (self.object_id, self.resource_id)

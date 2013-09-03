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
from neutron.openstack.common import timeutils
from sqlalchemy.orm import exc as sa_exc

from neutron.plugins.niblick.db import models
from neutron.plugins.niblick import exceptions


def _filter_out_fields_required(values):
    v = {}
    for i in ('object_id', 'resource_type', 'resource_metadata', 'resource_id',
              'resource_descriptor'):
        if i in values:
            v[i] = values[i]
    return v


def binding_add(context, values):
    session = context.session
    values = _filter_out_fields_required(values)
    with session.begin(subtransactions=True):
        obj = models.NiblickBinding()
        obj.update(values)
        session.add(obj)
        return obj


def binding_get(context, object_id):
    session = context.session
    try:
        obj = session.query(models.NiblickBinding).filter_by(
            object_id=object_id,
            deleted=0
        ).one()
        return obj
    except sa_exc.NoResultFound:
        raise exceptions.WrongObjectId(object_id=object_id)


def binding_update(context, object_id, values):
    session = context.session
    values = _filter_out_fields_required(values)
    with session.begin(subtransactions=True):
        obj = binding_get(context, object_id)
        obj.update(values)
        session.add(obj)
        return obj


def binding_delete(context, object_id):
    session = context.session
    with session.begin(subtransactions=True):
        obj = binding_get(context, object_id)
        obj['deleted'] = obj['id']
        obj['deleted_at'] = timeutils.utcnow()
        session.add(obj)

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
from neutron import context
from neutron.db import api as db_api
from neutron.openstack.common.db import exception as db_exc
from neutron.plugins.niblick.db import api
from neutron.plugins.niblick import exceptions
from neutron.tests import base


class BindingDBTestCase(base.BaseTestCase):
    def setUp(self):
        super(BindingDBTestCase, self).setUp()
        db_api.configure_db()
        self.addCleanup(db_api.clear_db)
        self.context = context.get_admin_context()
        resource = {'object_id': 'fake-object-id',
                    'resource_type': 'fake-resource-type',
                    'resource_id': 'fake-resource-id',
                    'resource_descriptor': 'com.vyatta.vm'}
        self.obj = dict(api.binding_add(self.context, resource))

    def test_add_dublicate(self):
        self.assertRaises(db_exc.DBDuplicateEntry, api.binding_add,
                          context=self.context, values=self.obj)

    def test_get(self):
        obj = dict(api.binding_get(self.context, self.obj['object_id']))
        self.assertDictEqual(self.obj, obj)

    def test_get_error(self):
        self.assertRaises(exceptions.WrongObjectId, api.binding_get,
                          context=self.context, object_id='fake-object-id-2')

    def test_update(self):
        obj = dict(api.binding_update(
            self.context,
            self.obj['object_id'],
            {'resource_descriptor': 'fake-resource-descriptor'}
        ))
        self.assertNotEqual(self.obj['resource_descriptor'],
                            obj['resource_descriptor'])
        self.assertEqual('fake-resource-descriptor',
                         obj['resource_descriptor'])

    def test_delete(self):
        self.assertIsNone(api.binding_delete(self.context,
                                             self.obj['object_id']))

    def test_get_error_after_delete(self):
        api.binding_delete(self.context, self.obj['object_id'])
        self.assertRaises(exceptions.WrongObjectId, api.binding_get,
                          context=self.context,
                          object_id=self.obj['object_id'])

    def test_add_dublicate_after_delete(self):
        api.binding_delete(self.context, self.obj['object_id'])
        obj = dict(api.binding_add(self.context, self.obj))
        self.assertEqual(self.obj['object_id'], obj['object_id'])

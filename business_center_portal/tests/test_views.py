# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestViewsAndData(TransactionCase):

    def test_partner_form_role_field(self):
        manager = new_test_user(self.env, login='bc_view_manager',
                                groups='business_center.group_bc_manager')
        arch = self.env['res.partner'].with_user(manager).get_view(view_type='form')['arch']
        self.assertTrue(etree.fromstring(arch).xpath("//field[@name='bc_role']"))

        user = new_test_user(self.env, login='bc_view_user', groups='base.group_user')
        arch = self.env['res.partner'].with_user(user).get_view(view_type='form')['arch']
        self.assertFalse(etree.fromstring(arch).xpath("//field[@name='bc_role']"),
                         "bc_role is for Business Center managers only")

    def test_templates_compile(self):
        views = self.env['ir.ui.view'].search([
            ('type', '=', 'qweb'),
            ('key', '=like', 'business_center_portal.%'),
        ])
        self.assertEqual(len(views), 7)
        for view in views:
            with self.subTest(view=view.key):
                arch = etree.tostring(view._get_combined_arch(), encoding='unicode')
                # Odoo 20 QWeb dropped t-esc: it renders nothing, silently.
                self.assertNotIn('t-esc=', arch)

    def test_portal_entries(self):
        for xmlid in ('portal_entry_contracts', 'portal_entry_bookings',
                      'portal_entry_invoice_history'):
            entry = self.env.ref(f'business_center_portal.{xmlid}')
            self.assertTrue(entry.image, f"{xmlid} has no image")
            self.assertTrue(entry.show_in_portal)

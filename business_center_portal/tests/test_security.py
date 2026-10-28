# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.business_center_portal.models.ir_access import (
    INVOICE_LINE_RULE_DOMAIN,
    INVOICE_RULE_DOMAIN,
)

from .common import BusinessCenterPortalCommon


@tagged('post_install', '-at_install')
class TestTenantAccess(BusinessCenterPortalCommon):
    """What each tenant role may read and change, per security/ir.access.csv."""

    def _visible(self, user, records):
        """The subset of ``records`` that ``user`` can search."""
        return records.with_user(user).search([('id', 'in', records.ids)])

    # ------------------------------------------------------------------
    #   Bookings
    # ------------------------------------------------------------------
    def test_employee_sees_own_bookings_only(self):
        bookings = self.employee_booking | self.colleague_booking | self.other_booking
        self.assertEqual(self._visible(self.employee, bookings), self.employee_booking)
        with self.assertRaises(AccessError):
            self.colleague_booking.with_user(self.employee).check_access('read')
        with self.assertRaises(AccessError):
            self.other_booking.with_user(self.employee).check_access('read')

    def test_employee_booking_operations(self):
        """Tenant Employee: create, read and update their own; never delete."""
        booking = self.employee_booking.with_user(self.employee)
        booking.check_access('write')
        with self.assertRaises(AccessError):
            booking.check_access('unlink')
        with self.assertRaises(AccessError):
            self.colleague_booking.with_user(self.employee).check_access('write')

    def test_tenant_admin_sees_company_bookings(self):
        bookings = self.employee_booking | self.colleague_booking | self.other_booking
        self.assertEqual(self._visible(self.tenant_admin, bookings),
                         self.employee_booking | self.colleague_booking)
        self.colleague_booking.with_user(self.tenant_admin).check_access('write')
        with self.assertRaises(AccessError):
            self.colleague_booking.with_user(self.tenant_admin).check_access('unlink')
        with self.assertRaises(AccessError):
            self.other_booking.with_user(self.tenant_admin).check_access('read')

    def test_other_tenant_admin_isolated(self):
        bookings = self.employee_booking | self.colleague_booking | self.other_booking
        self.assertEqual(self._visible(self.other_admin, bookings), self.other_booking)
        contracts = self.contract | self.other_contract
        self.assertEqual(self._visible(self.other_admin, contracts), self.other_contract)

    def test_plain_portal_user_has_no_access(self):
        Booking = self.env['business.center.booking'].with_user(self.portal_user)
        with self.assertRaises(AccessError):
            Booking.search([])
        with self.assertRaises(AccessError):
            self.env['business.center.contract'].with_user(self.portal_user).search([])

    # ------------------------------------------------------------------
    #   Contracts and the records hanging off them
    # ------------------------------------------------------------------
    def test_employee_cannot_read_contracts(self):
        with self.assertRaises(AccessError):
            self.contract.with_user(self.employee).check_access('read')

    def test_tenant_admin_contract_read_only(self):
        contract = self.contract.with_user(self.tenant_admin)
        contract.check_access('read')
        self.assertEqual(contract.name, self.contract.name)
        for operation in ('write', 'create', 'unlink'):
            with self.assertRaises(AccessError):
                contract.check_access(operation)
        with self.assertRaises(AccessError):
            self.other_contract.with_user(self.tenant_admin).check_access('read')

    def test_tenant_admin_sees_own_leased_assets_and_charges(self):
        assets = self.contract.leased_asset_ids | self.other_contract.leased_asset_ids
        self.assertEqual(self._visible(self.tenant_admin, assets), self.contract.leased_asset_ids)

        Charge = self.env['business.center.contract.charge']
        own = Charge.create({'contract_id': self.contract.id, 'date': self.today,
                             'description': 'Printing', 'quantity': 1, 'unit_price': 5.0})
        other = Charge.create({'contract_id': self.other_contract.id, 'date': self.today,
                               'description': 'Printing', 'quantity': 1, 'unit_price': 5.0})
        self.assertEqual(self._visible(self.tenant_admin, own | other), own)
        with self.assertRaises(AccessError):
            own.with_user(self.tenant_admin).check_access('write')
        with self.assertRaises(AccessError):
            own.with_user(self.employee).check_access('read')

    def test_tenant_admin_sees_centre_spaces_and_desks(self):
        admin = self.tenant_admin
        self.assertEqual(self._visible(admin, self.center), self.center)
        self.assertEqual(self._visible(admin, self.floor), self.floor)
        # Meeting rooms of the centre and the tenant's own office, but not
        # another tenant's office nor the unleased coworking space.
        spaces = self.office | self.meeting_room | self.cowork | self.other_office
        self.assertEqual(self._visible(admin, spaces), self.office | self.meeting_room)
        # No desk is leased by Tenant Corp.
        self.assertFalse(self._visible(admin, self.desk))

    def test_tenant_admin_sees_leased_desk(self):
        desk_contract = self._create_contract(desks=self.desk, confirm=True)
        self.assertEqual(desk_contract.state, 'active')
        self.assertEqual(self._visible(self.tenant_admin, self.desk), self.desk)

    def test_tenant_admin_reads_amenities(self):
        amenity = self.env['business.center.amenity'].create({'name': 'Projector'})
        amenity.with_user(self.tenant_admin).check_access('read')
        with self.assertRaises(AccessError):
            amenity.with_user(self.tenant_admin).check_access('write')
        with self.assertRaises(AccessError):
            amenity.with_user(self.employee).check_access('read')


@tagged('post_install', '-at_install')
class TestInvoiceAccess(BusinessCenterPortalCommon):
    """account's portal invoice accesses, narrowed for tenants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        line = [Command.create({'name': 'Rent', 'quantity': 1, 'price_unit': 100.0})]
        Move = cls.env['account.move']
        cls.tenant_invoice = Move.create({
            'move_type': 'out_invoice', 'partner_id': cls.tenant.id,
            'invoice_line_ids': line})
        cls.tenant_bill = Move.create({
            'move_type': 'in_invoice', 'partner_id': cls.tenant.id,
            'invoice_date': cls.today, 'invoice_line_ids': line})
        cls.tenant_draft = Move.create({
            'move_type': 'out_invoice', 'partner_id': cls.tenant.id,
            'invoice_line_ids': line})
        cls.plain_bill = Move.create({
            'move_type': 'in_invoice', 'partner_id': cls.portal_user.partner_id.id,
            'invoice_date': cls.today, 'invoice_line_ids': line})
        (cls.tenant_invoice | cls.tenant_bill | cls.plain_bill).action_post()
        cls.moves = cls.tenant_invoice | cls.tenant_bill | cls.tenant_draft | cls.plain_bill

    def _visible(self, user):
        return self.moves.with_user(user).search([('id', 'in', self.moves.ids)])

    def test_portal_invoice_domains_applied(self):
        self.assertEqual(self.env.ref('account.account_invoice_rule_portal').domain,
                         INVOICE_RULE_DOMAIN)
        self.assertEqual(self.env.ref('account.account_invoice_line_rule_portal').domain,
                         INVOICE_LINE_RULE_DOMAIN)

    def test_portal_invoice_domains_restored(self):
        """account resets its accesses on update; ours put them back."""
        access = self.env.ref('account.account_invoice_rule_portal')
        access.domain = "[('partner_id', 'child_of', [user.commercial_partner_id.id])]"
        self.env['ir.access']._bc_apply_portal_invoice_rules()
        self.assertEqual(access.domain, INVOICE_RULE_DOMAIN)

    def test_tenant_admin_sees_posted_customer_invoices_only(self):
        self.assertEqual(self._visible(self.tenant_admin), self.tenant_invoice)
        lines = self.moves.line_ids.with_user(self.tenant_admin).search(
            [('id', 'in', self.moves.line_ids.ids)])
        self.assertEqual(lines.move_id, self.tenant_invoice)

    def test_tenant_employee_sees_no_invoice(self):
        self.assertFalse(self._visible(self.employee))
        with self.assertRaises(AccessError):
            self.tenant_invoice.with_user(self.employee).check_access('read')

    def test_plain_portal_user_keeps_stock_access(self):
        """No BC role: account's stock rule, vendor bills included."""
        self.assertEqual(self._visible(self.portal_user), self.plain_bill)


@tagged('post_install', '-at_install')
class TestTenantRole(BusinessCenterPortalCommon):
    """res.partner.bc_role drives the portal login's tenant groups."""

    def _groups(self, user):
        return user.group_ids & (self.env.ref('business_center_portal.group_bc_tenant_employee')
                                 | self.env.ref('business_center_portal.group_bc_tenant_admin'))

    def test_role_sets_group(self):
        employee_group = self.env.ref('business_center_portal.group_bc_tenant_employee')
        admin_group = self.env.ref('business_center_portal.group_bc_tenant_admin')
        self.assertEqual(self._groups(self.employee), employee_group)
        self.assertEqual(self._groups(self.tenant_admin), admin_group)
        self.assertTrue(self.tenant_admin.has_group('business_center_portal.group_bc_tenant_employee'),
                        "Tenant Corporate Admin implies Tenant Employee")

    def test_role_change_and_removal(self):
        partner = self.employee.partner_id
        partner.bc_role = 'admin'
        self.assertEqual(self._groups(self.employee),
                         self.env.ref('business_center_portal.group_bc_tenant_admin'))
        partner.bc_role = False
        self.assertFalse(self._groups(self.employee))
        self.assertTrue(self.employee.has_group('base.group_portal'))

    def test_role_ignored_for_internal_user(self):
        partner = self.internal_user.partner_id
        partner.bc_role = 'admin'
        self.assertFalse(self._groups(self.internal_user))

    def test_role_on_create(self):
        partner = self.env['res.partner'].create({
            'name': 'New Contact', 'parent_id': self.tenant.id, 'bc_role': 'admin'})
        self.assertEqual(partner.bc_role, 'admin')

    def test_center_ids(self):
        self.assertEqual(self.employee.partner_id.bc_center_ids, self.center)
        self.assertEqual(self.tenant.bc_center_ids, self.center)
        self.assertFalse(self.portal_user.partner_id.bc_center_ids)
        self.assertFalse(self.env['res.partner'].search([('bc_center_ids', 'in', self.center.ids)]))

    def test_center_ids_desk_only_tenant(self):
        """A tenant leasing only a desk still gets the desk's centre."""
        desk_tenant = self.env['res.partner'].create({'name': 'Desk Co', 'is_company': True})
        self._create_contract(desks=self.desk, confirm=True, partner_id=desk_tenant.id)
        self.assertEqual(desk_tenant.bc_center_ids, self.center)


@tagged('post_install', '-at_install')
class TestPortalWizard(BusinessCenterPortalCommon):
    """Granting portal access defaults tenant contacts to Tenant Employee."""

    def _grant(self, partner):
        wizard = self.env['portal.wizard'].create({'partner_ids': [Command.link(partner.id)]})
        wizard.user_ids.action_grant_access()
        return partner.user_ids[:1]

    def test_tenant_contact_defaults_to_employee(self):
        partner = self.env['res.partner'].create({
            'name': 'New Hire', 'parent_id': self.tenant.id, 'email': 'hire@example.com'})
        user = self._grant(partner)
        self.assertEqual(partner.bc_role, 'employee')
        self.assertTrue(user.has_group('business_center_portal.group_bc_tenant_employee'))
        self.assertFalse(user.has_group('business_center_portal.group_bc_tenant_admin'))

    def test_tenant_contact_keeps_chosen_role(self):
        partner = self.env['res.partner'].create({
            'name': 'New Boss', 'parent_id': self.tenant.id, 'email': 'boss@example.com',
            'bc_role': 'admin'})
        user = self._grant(partner)
        self.assertEqual(partner.bc_role, 'admin')
        self.assertTrue(user.has_group('business_center_portal.group_bc_tenant_admin'))

    def test_non_tenant_contact_gets_no_role(self):
        partner = self.env['res.partner'].create({
            'name': 'Walk-in', 'email': 'walkin@example.com'})
        user = self._grant(partner)
        self.assertFalse(partner.bc_role)
        self.assertTrue(user.has_group('base.group_portal'))
        self.assertFalse(user.has_group('business_center_portal.group_bc_tenant_employee'))

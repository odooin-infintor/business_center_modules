# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.tests import new_test_user

from odoo.addons.business_center.tests.common import BusinessCenterCommon


class BusinessCenterPortalCommon(BusinessCenterCommon):
    """Two tenant companies with a running office contract each, and one
    portal login per tenant role:

    * ``employee`` / ``colleague``: Tenant Employees of Tenant Corp,
    * ``tenant_admin``: Tenant Corporate Admin of Tenant Corp,
    * ``other_admin``: Tenant Corporate Admin of another tenant,
    * ``portal_user``: a portal login with no Business Center role.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.contract = cls._create_contract(spaces=cls.office, confirm=True)

        cls.other_tenant = cls.env['res.partner'].create({
            'name': 'Other Corp', 'is_company': True, 'email': 'other@example.com',
        })
        cls.other_office = cls._create_space(monthly_rent=800.0)
        cls.other_office.action_set_available()
        cls.other_contract = cls._create_contract(
            spaces=cls.other_office, confirm=True, partner_id=cls.other_tenant.id)

        cls.employee = cls._create_tenant_user('bc_employee', cls.tenant, 'employee')
        cls.colleague = cls._create_tenant_user('bc_colleague', cls.tenant, 'employee')
        cls.tenant_admin = cls._create_tenant_user('bc_tenant_admin', cls.tenant, 'admin')
        cls.other_admin = cls._create_tenant_user('bc_other_admin', cls.other_tenant, 'admin')
        cls.portal_user = new_test_user(
            cls.env, login='bc_portal_plain', groups='base.group_portal',
            password='bc_portal_plain')

        # Employees may only book against contracts they are named on.
        cls.contract.contact_ids = [Command.link(cls.employee.partner_id.id),
                                    Command.link(cls.colleague.partner_id.id)]

        cls.tomorrow = cls.today + relativedelta(days=1)
        cls.employee_booking = cls._create_confirmed_booking(cls.contract, cls.employee, 9.0, 10.0)
        cls.colleague_booking = cls._create_confirmed_booking(cls.contract, cls.colleague, 11.0, 12.0)
        cls.other_booking = cls._create_confirmed_booking(cls.other_contract, cls.other_admin, 14.0, 15.0)

    @classmethod
    def _create_tenant_user(cls, login, company, role):
        """A portal login on a contact of ``company``. The tenant group comes
        from the contact's ``bc_role``, the way a manager sets it up."""

        user = new_test_user(cls.env, login=login, groups='base.group_portal', password=login)
        user.partner_id.write({'parent_id': company.id, 'bc_role': role})
        return user

    @classmethod
    def _create_confirmed_booking(cls, contract, user, start, end):
        booking = cls.env['business.center.booking'].create({
            'contract_id': contract.id,
            'meeting_room_id': cls.meeting_room.id,
            'booking_date': cls.tomorrow,
            'start_time': start,
            'end_time': end,
            'user_id': user.id,
        })
        booking.action_confirm()
        return booking

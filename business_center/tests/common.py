# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, new_test_user


class BusinessCenterCommon(TransactionCase):
    """Shared fixtures: one centre with an office, a meeting room and a
    coworking space holding a desk, a tenant, and one user per role."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_create_nolog=True, mail_notrack=True))
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['business.center.contract'])

        cls.bc_user = new_test_user(
            cls.env, login='bc_user', groups='business_center.group_bc_user',
            company_id=cls.company.id)
        cls.bc_manager = new_test_user(
            cls.env, login='bc_manager', groups='business_center.group_bc_manager',
            company_id=cls.company.id)
        cls.internal_user = new_test_user(
            cls.env, login='bc_internal', groups='base.group_user',
            company_id=cls.company.id)

        cls.tenant = cls.env['res.partner'].create({
            'name': 'Tenant Corp', 'is_company': True, 'email': 'tenant@example.com',
        })
        cls.employee = cls.env['res.partner'].create({
            'name': 'Tenant Employee', 'parent_id': cls.tenant.id,
            'email': 'employee@example.com',
        })

        cls.center = cls.env['business.center'].create({
            'name': 'Main Building',
            'email': 'center@example.com',
            'manager_id': cls.bc_manager.id,
            'company_id': cls.company.id,
        })
        cls.floor = cls.env['business.center.floor'].create({
            'name': 'F0', 'center_id': cls.center.id,
        })
        cls.office = cls._create_space(monthly_rent=1000.0)
        cls.meeting_room = cls._create_space(
            space_type='meeting_room', hourly_rate=50.0, capacity=6)
        cls.cowork = cls._create_space(is_coworking=True)
        cls.desk = cls.env['business.center.desk'].create({
            'space_id': cls.cowork.id, 'row_label': 'A', 'position': 1,
            'monthly_rent': 200.0,
        })
        (cls.office | cls.meeting_room | cls.cowork).action_set_available()
        cls.desk.action_set_available()

    @classmethod
    def _create_space(cls, **vals):
        return cls.env['business.center.space'].create({
            'center_id': cls.center.id,
            'floor_id': cls.floor.id,
            'monthly_rent': 0.0,
            'hourly_rate': 0.0,
            'min_booking_hour': 8.0,
            'max_booking_hour': 18.0,
            **vals,
        })

    @classmethod
    def _create_contract(cls, spaces=(), desks=(), confirm=False, **vals):
        """Draft contract for the tenant leasing the given spaces and desks,
        starting today for one year unless dates are given."""

        start = vals.pop('date_start', cls.today)
        lines = [Command.create({'lease_asset_type': 'office', 'space_id': s.id}) for s in spaces]
        lines += [Command.create({'lease_asset_type': 'desk', 'desk_id': d.id}) for d in desks]
        contract = cls.env['business.center.contract'].create({
            'partner_id': cls.tenant.id,
            'date_start': start,
            'date_end': vals.pop('date_end', start + relativedelta(years=1, days=-1)),
            'free_hours_monthly': 10.0 if spaces else 0.0,
            'leased_asset_ids': lines,
            **vals,
        })
        if confirm:
            contract.action_set_confirm()
        return contract

    def _create_booking(self, contract, start=9.0, end=10.0, booking_date=None, room=None, user=None):
        Booking = self.env['business.center.booking']
        if user:
            Booking = Booking.with_user(user)
        return Booking.create({
            'contract_id': contract.id,
            'meeting_room_id': (room or self.meeting_room).id,
            'booking_date': booking_date or self.today + relativedelta(days=1),
            'start_time': start,
            'end_time': end,
        })

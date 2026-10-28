# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from urllib.parse import urlparse

from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import BusinessCenterPortalCommon


@tagged('post_install', '-at_install')
class TestPortalRoutes(BusinessCenterPortalCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bc_user.password = 'bc_user_pwd'

    def _login(self, user):
        password = 'bc_user_pwd' if user == self.bc_user else user.login
        self.authenticate(user.login, password)

    def _get(self, url, **kwargs):
        response = self.url_open(url, allow_redirects=False, **kwargs)
        self.assertNotEqual(response.status_code, 500, f"500 on {url}")
        return response

    def assertRedirects(self, response, path):
        self.assertIn(response.status_code, (301, 302, 303), response.text[:500])
        self.assertEqual(urlparse(response.headers['Location']).path, path)

    def assertPage(self, response):
        self.assertEqual(response.status_code, 200, response.text[:500])
        return response.text

    # ------------------------------------------------------------------
    #   Anonymous and users without a tenant role
    # ------------------------------------------------------------------
    def test_anonymous_is_sent_to_login(self):
        for url in ('/my/bookings', '/my/bookings/new', f'/my/bookings/{self.employee_booking.id}',
                    '/my/contracts', f'/my/contracts/{self.contract.id}', '/my/bookings/slots'):
            self.assertRedirects(self._get(url), '/web/login')

    def test_plain_portal_user_is_blocked(self):
        self._login(self.portal_user)
        for url in ('/my/bookings', '/my/bookings/new', '/my/bookings/slots',
                    f'/my/bookings/{self.employee_booking.id}',
                    '/my/contracts', f'/my/contracts/{self.contract.id}', '/my/invoices'):
            self.assertRedirects(self._get(url), '/my')

    def test_internal_user_not_blocked(self):
        """The tenant checks only apply to portal logins."""
        self._login(self.bc_user)
        self.assertPage(self._get('/my/bookings'))
        self.assertPage(self._get('/my/contracts'))
        self.assertPage(self._get(f'/my/contracts/{self.contract.id}'))

    # ------------------------------------------------------------------
    #   /my home cards
    # ------------------------------------------------------------------
    def test_home_cards(self):
        expected = {
            # user: (shown, hidden)
            self.employee: (['/my/bookings'],
                            ['/my/contracts', '/my/invoices"', '/my/invoices?filterby=bills',
                             '/my/orders', '/my/addresses']),
            self.tenant_admin: (['/my/bookings', '/my/contracts', '/my/invoices"'],
                                ['/my/invoices?filterby=bills', '/my/orders']),
            self.portal_user: (['/my/invoices?filterby=invoices'],
                               ['/my/bookings', '/my/contracts', '/my/orders']),
        }
        for user, (shown, hidden) in expected.items():
            with self.subTest(user=user.login):
                self._login(user)
                html = self.assertPage(self._get('/my'))
                for url in shown:
                    self.assertIn(f'href="{url}', html)
                for url in hidden:
                    self.assertNotIn(f'href="{url}', html)

    # ------------------------------------------------------------------
    #   Bookings
    # ------------------------------------------------------------------
    def test_employee_booking_list(self):
        self._login(self.employee)
        html = self.assertPage(self._get('/my/bookings'))
        self.assertIn(self.employee_booking.name, html)
        self.assertNotIn(self.colleague_booking.name, html)
        self.assertNotIn(self.other_booking.name, html)

    def test_tenant_admin_booking_list(self):
        self._login(self.tenant_admin)
        html = self.assertPage(self._get('/my/bookings'))
        self.assertIn(self.employee_booking.name, html)
        self.assertIn(self.colleague_booking.name, html)
        self.assertNotIn(self.other_booking.name, html)

    def test_booking_list_search_sort_filter(self):
        self._login(self.tenant_admin)
        for sortby in ('date', 'name', 'room', 'state'):
            self.assertPage(self._get(f'/my/bookings?sortby={sortby}'))
        for filterby in ('all', 'draft', 'confirmed', 'cancelled'):
            self.assertPage(self._get(f'/my/bookings?filterby={filterby}'))
        html = self.assertPage(self._get(
            f'/my/bookings?search={self.colleague_booking.name}&search_in=name'))
        self.assertIn(self.colleague_booking.name, html)
        self.assertNotIn(self.employee_booking.name, html)
        for search_in in ('room', 'contract', 'all'):
            self.assertPage(self._get(f'/my/bookings?search=Main&search_in={search_in}'))
        self.assertPage(self._get('/my/bookings/page/2'))

    def test_booking_detail(self):
        self._login(self.employee)
        html = self.assertPage(self._get(f'/my/bookings/{self.employee_booking.id}'))
        self.assertIn(self.employee_booking.name, html)
        self.assertIn('o_bc_cancel_booking', html)
        self.assertRedirects(self._get(f'/my/bookings/{self.colleague_booking.id}'), '/my')
        self.assertRedirects(self._get(f'/my/bookings/{self.other_booking.id}'), '/my')
        self.assertRedirects(self._get('/my/bookings/999999999'), '/my')

    def test_booking_form(self):
        self._login(self.employee)
        html = self.assertPage(self._get('/my/bookings/new'))
        self.assertIn('o_bc_booking_form', html)
        self.assertIn(self.meeting_room.display_name, html)
        self.assertIn(self.contract.name, html)
        self.assertIn(f'<span id="o_bc_wallet">{self.contract.wallet_balance}</span>', html)
        # Tampered ids fall back instead of raising.
        self.assertPage(self._get('/my/bookings/new?contract_id=abc&meeting_room_id=-1&booking_date=nope'))

    def test_booking_form_without_contract(self):
        """A Tenant Employee not named on any contract cannot book."""
        lonely = self._create_tenant_user('bc_lonely', self.tenant, 'employee')
        self._login(lonely)
        html = self.assertPage(self._get('/my/bookings/new'))
        self.assertIn('running contract', html)

    def test_booking_slots(self):
        self._login(self.employee)
        response = self._get(
            f'/my/bookings/slots?contract_id={self.contract.id}'
            f'&meeting_room_id={self.meeting_room.id}&booking_date={self.tomorrow}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['rooms'], [{'id': self.meeting_room.id,
                                          'name': self.meeting_room.display_name}])
        self.assertEqual(data['rate'], self.meeting_room.hourly_rate)
        self.assertEqual(data['wallet'], self.contract.wallet_balance)
        self.assertTrue(data['slots'])

    def _post_booking(self, **values):
        data = {
            'csrf_token': self.csrf_token(),
            'contract_id': self.contract.id,
            'meeting_room_id': self.meeting_room.id,
            'booking_date': str(self.today + relativedelta(days=2)),
            'start_time': '13:00',
            'end_time': '14:30',
            **values,
        }
        return self.url_open('/my/bookings/new', data=data, allow_redirects=False)

    def test_booking_submit(self):
        self._login(self.employee)
        Booking = self.env['business.center.booking']
        before = Booking.search([])
        wallet = self.contract.wallet_balance
        response = self._post_booking()
        booking = Booking.search([]) - before
        self.assertEqual(len(booking), 1)
        self.assertRedirects(response, f'/my/bookings/{booking.id}')
        self.assertEqual(booking.state, 'confirmed')
        self.assertEqual(booking.user_id, self.employee)
        self.assertEqual(booking.start_time, 13.0)
        self.assertEqual(booking.end_time, 14.5)
        self.assertAlmostEqual(self.contract.wallet_balance, wallet - 1.5)

    def test_booking_submit_errors(self):
        self._login(self.employee)
        Booking = self.env['business.center.booking']
        before = Booking.search([])
        yesterday = str(self.today - relativedelta(days=1))
        cases = [
            ({'booking_date': yesterday}, 'past date'),
            ({'start_time': '15:00', 'end_time': '14:00'}, 'end time must be after'),
            ({'start_time': 'garbage'}, 'valid start time'),
        ]
        for values, message in cases:
            with self.subTest(values=values):
                html = self.assertPage(self._post_booking(**values))
                self.assertIn('alert-danger', html)
                self.assertIn(message, html)

        # Overlaps the employee's confirmed 9:00-10:00 slot: business_center's
        # exclusion constraint rejects it and the controller reports it.
        with mute_logger('odoo.sql_db'):
            html = self.assertPage(self._post_booking(
                booking_date=str(self.tomorrow), start_time='09:30', end_time='10:30'))
        self.assertIn('slot was just taken', html)
        self.assertEqual(Booking.search([]), before)

    def test_booking_submit_other_tenant_contract(self):
        """A foreign contract id falls back to the member's own contract."""
        self._login(self.employee)
        Booking = self.env['business.center.booking']
        before = Booking.search([])
        self._post_booking(contract_id=self.other_contract.id)
        booking = Booking.search([]) - before
        self.assertEqual(booking.contract_id, self.contract)

    def test_booking_cancel(self):
        self._login(self.employee)
        response = self.url_open(
            f'/my/bookings/{self.employee_booking.id}/cancel',
            data={'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertRedirects(response, f'/my/bookings/{self.employee_booking.id}')
        self.assertEqual(self.employee_booking.state, 'cancelled')

    def test_booking_cancel_refused(self):
        """An employee cannot cancel a colleague's booking; the admin can."""
        self._login(self.employee)
        response = self.url_open(
            f'/my/bookings/{self.colleague_booking.id}/cancel',
            data={'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertRedirects(response, '/my')
        self.assertEqual(self.colleague_booking.state, 'confirmed')

        self._login(self.tenant_admin)
        response = self.url_open(
            f'/my/bookings/{self.colleague_booking.id}/cancel',
            data={'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertRedirects(response, f'/my/bookings/{self.colleague_booking.id}')
        self.assertEqual(self.colleague_booking.state, 'cancelled')

    def test_booking_cancel_twice(self):
        self.employee_booking.action_cancel()
        self._login(self.employee)
        response = self.url_open(
            f'/my/bookings/{self.employee_booking.id}/cancel',
            data={'csrf_token': self.csrf_token()}, allow_redirects=False)
        self.assertIn('error=', response.headers['Location'])
        html = self.assertPage(self._get(response.headers['Location']))
        self.assertIn('already been cancelled', html)

    # ------------------------------------------------------------------
    #   Contracts
    # ------------------------------------------------------------------
    def test_employee_blocked_from_contracts(self):
        self._login(self.employee)
        self.assertRedirects(self._get('/my/contracts'), '/my')
        self.assertRedirects(self._get(f'/my/contracts/{self.contract.id}'), '/my')

    def test_tenant_admin_contracts(self):
        self._login(self.tenant_admin)
        html = self.assertPage(self._get('/my/contracts'))
        self.assertIn(self.contract.name, html)
        self.assertNotIn(self.other_contract.name, html)
        html = self.assertPage(self._get(f'/my/contracts/{self.contract.id}'))
        self.assertIn(self.contract.name, html)
        self.assertIn('Free-Hours Wallet', html)
        self.assertRedirects(self._get(f'/my/contracts/{self.other_contract.id}'), '/my')

    def test_contract_list_search_sort_filter(self):
        self._login(self.tenant_admin)
        for sortby in ('date', 'name', 'state'):
            self.assertPage(self._get(f'/my/contracts?sortby={sortby}'))
        for filterby in ('all', 'active', 'draft', 'expired'):
            self.assertPage(self._get(f'/my/contracts?filterby={filterby}'))
        for search_in in ('name', 'partner', 'leased', 'all'):
            self.assertPage(self._get(f'/my/contracts?search=Tenant&search_in={search_in}'))

    # ------------------------------------------------------------------
    #   Invoices
    # ------------------------------------------------------------------
    def _create_invoice(self, partner, move_type='out_invoice'):
        invoice = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [Command.create({'name': 'Rent', 'quantity': 1, 'price_unit': 100.0})],
        })
        invoice.action_post()
        return invoice

    def test_invoices(self):
        invoice = self._create_invoice(self.tenant)
        bill = self._create_invoice(self.tenant, 'in_invoice')

        self._login(self.employee)
        self.assertRedirects(self._get('/my/invoices'), '/my')
        self.assertRedirects(self._get(f'/my/invoices/{invoice.id}'), '/my')

        self._login(self.tenant_admin)
        html = self.assertPage(self._get('/my/invoices'))
        self.assertIn(invoice.name, html)
        self.assertNotIn(bill.name, html)
        self.assertIn('Invoice History', html)
        self.assertNotIn('filterby=bills', html)
        # An old bookmark on the removed filter falls back to 'all'.
        self.assertPage(self._get('/my/invoices?filterby=bills'))
        html = self.assertPage(self._get(f'/my/invoices/{invoice.id}'))
        self.assertIn(invoice.name, html)
        self.assertRedirects(self._get(f'/my/invoices/{bill.id}'), '/my')

    def test_invoice_shared_link(self):
        """A tokenised link keeps working for a Tenant Employee."""
        invoice = self._create_invoice(self.tenant)
        invoice._portal_ensure_token()
        self._login(self.employee)
        self.assertPage(self._get(
            f'/my/invoices/{invoice.id}?access_token={invoice.access_token}'))

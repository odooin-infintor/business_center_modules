# -*- coding: utf-8 -*-
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

TENANT_ADMIN_GROUP = 'business_center_portal.group_bc_tenant_admin'
TENANT_EMPLOYEE_GROUP = 'business_center_portal.group_bc_tenant_employee'

# Stock /my cards this module takes off the home page for every user.
HIDDEN_PORTAL_ENTRIES = (
    'portal.portal_entry_addresses',
    'portal.portal_entry_base',
    'sale.portal_your_orders',
)

# account's invoice cards. A tenant gets our own Invoice History card
# instead, but they stay for every portal user with no BC role.
HIDDEN_TENANT_PORTAL_ENTRIES = (
    'account.portal_invoice_client',
    'account.portal_invoice_vendor',
    'account_payment.portal_entry_overdue_invoices',
)

# Our own cards, each shown only to the given group.
GROUP_PORTAL_ENTRIES = {
    'business_center_portal.portal_entry_contracts': TENANT_ADMIN_GROUP,
    'business_center_portal.portal_entry_bookings': TENANT_EMPLOYEE_GROUP,
    'business_center_portal.portal_entry_invoice_history': TENANT_ADMIN_GROUP,
}


class BusinessCenterPortal(CustomerPortal):
    """Shared settings for every portal page added by this module.

    Anything that both contracts and bookings (and later invoices) need
    should live here, so it is written once instead of being repeated in
    each controller file.
    """

    # How many rows each portal list page shows before paging.
    _items_per_page = 8

    def _bc_hidden_portal_entries(self):
        """The /my cards the current user must not see.

        They are dropped from the page rather than deactivated, so the stock
        records are left untouched and come back if this module is removed.
        A card with a non-zero counter is always shown by portal, so leaving
        it out of the page is the only reliable way to hide it.
        """
        user = request.env.user
        xmlids = list(HIDDEN_PORTAL_ENTRIES)
        if user.has_group(TENANT_ADMIN_GROUP) or user.has_group(TENANT_EMPLOYEE_GROUP):
            xmlids += HIDDEN_TENANT_PORTAL_ENTRIES
        xmlids += [xmlid for xmlid, group in GROUP_PORTAL_ENTRIES.items()
                   if not user.has_group(group)]

        hidden = request.env['portal.entry']
        for xmlid in xmlids:
            hidden |= request.env.ref(xmlid, raise_if_not_found=False) or hidden
        return hidden

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        hidden = self._bc_hidden_portal_entries()
        if hidden:
            values['portal_entries'] = {
                category: entries - hidden
                for category, entries in values['portal_entries'].items()
            }
            values['portal_cards'] -= hidden
            values['portal_hidden_cards'] -= hidden
        return values

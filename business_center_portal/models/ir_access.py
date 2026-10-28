# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

# Corporate admins see their company's posted customer invoices, tenant
# employees see none, and every other portal user keeps Odoo's stock rule.
INVOICE_RULE_DOMAIN = """(
    [('state', 'not in', ('cancel', 'draft')),
     ('move_type', 'in', ('out_invoice', 'out_refund')),
     ('partner_id', 'child_of', [user.commercial_partner_id.id])]
    if user.has_group('business_center_portal.group_bc_tenant_admin')
    else [('id', '=', False)]
    if user.has_group('business_center_portal.group_bc_tenant_employee')
    else [('state', 'not in', ('cancel', 'draft')),
          ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
          ('partner_id', 'child_of', [user.commercial_partner_id.id])])"""

INVOICE_LINE_RULE_DOMAIN = """(
    [('parent_state', 'not in', ('cancel', 'draft')),
     ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
     ('move_id.partner_id', 'child_of', [user.commercial_partner_id.id])]
    if user.has_group('business_center_portal.group_bc_tenant_admin')
    else [('id', '=', False)]
    if user.has_group('business_center_portal.group_bc_tenant_employee')
    else [('parent_state', 'not in', ('cancel', 'draft')),
          ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
          ('move_id.partner_id', 'child_of', [user.commercial_partner_id.id])])"""


class IrAccess(models.Model):
    _inherit = 'ir.access'

    # ------------------------------------------------------------------------------
    #   MARK: HELPER METHODS
    # ------------------------------------------------------------------------------
    @api.model
    def _bc_apply_portal_invoice_rules(self):
        """Narrow account's portal invoice accesses for business center tenants.

        Those accesses belong to account, which resets their domain whenever
        it is updated. Writing them here runs on every install and upgrade of
        this module, and Odoo upgrades this module after account since it
        depends on it, so the narrowed domains are always put back.
        """

        for xmlid, domain in (
            ('account.account_invoice_rule_portal', INVOICE_RULE_DOMAIN),
            ('account.account_invoice_line_rule_portal', INVOICE_LINE_RULE_DOMAIN),
        ):
            access = self.env.ref(xmlid, raise_if_not_found=False)
            if access and access.domain != domain:
                access.sudo().write({'domain': domain})
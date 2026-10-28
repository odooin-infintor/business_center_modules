# Business Center Portal

Tenant-facing portal for the Business Center module: contracts, meeting-room
bookings and invoice history at `/my`.

Depends on `business_center`. The back office works without this module;
installing it adds tenant self-service, and uninstalling it returns the
database to backend only.

## Roles

- **Tenant Employee** — book meeting rooms against contracts they are named
  on; see and cancel their own bookings.
- **Tenant Corporate Admin** — everything an Employee can, plus the
  company's contracts, all of the company's bookings, and invoice history.

Set the role on the contact (Business Center Role) and grant portal access
from Contacts > Action > Grant portal access; the role is applied when the
login is created. A contact of a tenant company (one with business center
contracts) granted access without a role becomes a Tenant Employee, the least
privileged role.

Portal users without a Business Center role keep Odoo's normal portal: they
do not see the Bookings or Contracts pages.

## Booking rules

Booking rules follow the backend: no past-dated bookings, no cancellation once
a session has started, and an extra charge already on an invoice can only be
reversed by the business centre. Times are compared in the business centre's
timezone, set under Business Center > Configuration > Settings.

On the availability strip, other tenants' bookings are shown only as
"Booked", never with their reference.

## Invoices and payment

Tenant Corporate Admins see their company's posted invoices and can download
them. The Pay Now button on an invoice needs a payment provider: enable one
under Invoicing > Configuration > Payment Providers (an online provider, or
Wire Transfer with the client's bank details).

## Note on shared databases

This module narrows two record rules that belong to Odoo's `account` module:

- `account.account_invoice_rule_portal`
- `account.account_invoice_line_rule_portal`

Tenant Corporate Admins see their company's posted customer invoices and
credit notes; Tenant Employees see no invoices. Every other portal user keeps
Odoo's stock rule. The domains are defined in `models/ir_rule.py` and written
on each install and upgrade of this module.

Uninstalling this module restores both rules to Odoo's stock domains, so a
database can move from backend + portal back to backend only without
leftovers. The changes to the stock invoice tile and breadcrumbs are
inherited views and are removed automatically as well.
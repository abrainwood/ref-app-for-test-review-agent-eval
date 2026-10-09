from datetime import date
from unittest import mock

from billing import Invoice, reports

DUE = date(2026, 2, 14)


def invoice_for(customer, total):
    return Invoice(customer, total, 0.0, 0.0, total, DUE)


def test_customer_details_are_resolved_once_per_customer():
    invoices = [invoice_for("acme", 40.0), invoice_for("globex", 7.0), invoice_for("acme", 60.0)]
    with mock.patch.object(reports, "_customer_name", side_effect=str) as lookup:
        reports.build_report(invoices)
    assert sorted(call.args[0] for call in lookup.call_args_list) == ["acme", "globex"]

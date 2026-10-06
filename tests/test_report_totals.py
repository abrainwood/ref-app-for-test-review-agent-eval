from datetime import date
from decimal import Decimal
from unittest import mock

from billing import Invoice, reports

DUE = date(2026, 2, 14)


def invoice_for(customer, total):
    return Invoice(customer, total, 0.0, 0.0, total, DUE)


def test_aggregate_sums_cents_without_float_drift():
    assert reports._aggregate([invoice_for("acme", 0.1)] * 3) == {"acme": Decimal("0.30")}


def test_report_aggregates_before_formatting():
    with mock.patch.object(reports, "_format_rows", return_value="") as format_rows:
        reports.build_report([invoice_for("acme", 0.1), invoice_for("acme", 0.2)])
    format_rows.assert_called_once_with({"acme": Decimal("0.30")})

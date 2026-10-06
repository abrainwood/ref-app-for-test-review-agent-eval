from datetime import date

from billing import Invoice, build_report

DUE = date(2026, 2, 14)


def invoice_for(customer, total):
    return Invoice(customer, total, 0.0, 0.0, total, DUE)


def test_report_has_one_row_per_customer_summing_their_invoices():
    report = build_report([invoice_for("acme", 40.0), invoice_for("acme", 60.0), invoice_for("globex", 7.0)])
    assert report.splitlines() == [
        "acme                       100",
        "globex                       7",
    ]


def test_report_rows_are_sorted_by_customer():
    report = build_report([invoice_for("zeta", 1.0), invoice_for("alpha", 2.0)])
    assert [row.split()[0] for row in report.splitlines()] == ["alpha", "zeta"]


def test_empty_report_is_blank():
    assert build_report([]) == ""

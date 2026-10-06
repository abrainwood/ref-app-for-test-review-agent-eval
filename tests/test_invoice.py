from datetime import date

from billing import Line, price_invoice

ISSUED = date(2026, 1, 15)


def test_small_order_has_no_discount_or_tax():
    invoice = price_invoice("acme", [Line("bolt", 10, 4.5)], ISSUED)
    assert (invoice.subtotal, invoice.discount, invoice.tax, invoice.total) == (45.0, 0.0, 0.0, 45.0)


def test_large_order_is_discounted_before_tax():
    invoice = price_invoice("acme", [Line("pump", 4, 300.0)], ISSUED)
    assert (invoice.subtotal, invoice.discount, invoice.tax, invoice.total) == (1200.0, 120.0, 8.0, 1088.0)


def test_subtotal_sums_all_lines():
    invoice = price_invoice("acme", [Line("bolt", 2, 3.0), Line("nut", 5, 1.25)], ISSUED)
    assert invoice.subtotal == 12.25


def test_order_crossing_upper_tax_bracket():
    invoice = price_invoice("globex", [Line("turbine", 1, 6000.0)], ISSUED)
    assert (invoice.discount, invoice.tax, invoice.total) == (600.0, 480.0, 5880.0)


def test_empty_invoice_totals_zero():
    invoice = price_invoice("acme", [], ISSUED)
    assert invoice.total == 0.0


def test_payment_is_due_thirty_days_after_issue():
    invoice = price_invoice("acme", [Line("bolt", 1, 1.0)], ISSUED)
    assert invoice.due == date(2026, 2, 14)

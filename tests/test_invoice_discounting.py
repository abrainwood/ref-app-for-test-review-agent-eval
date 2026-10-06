from datetime import date
from unittest import mock

from billing import Line, price_invoice

ISSUED = date(2026, 1, 15)


def test_mid_size_order_gets_silver_discount():
    invoice = price_invoice("acme", [Line("valve", 3, 200.0)], ISSUED)
    assert (invoice.discount, invoice.total) == (30.0, 570.0)


def test_price_invoice_asks_for_discount_on_subtotal():
    with mock.patch("billing.invoice.discount_rate", return_value=0.0) as rate:
        price_invoice("acme", [Line("valve", 3, 200.0)], ISSUED)
    rate.assert_called_once_with(600.0)

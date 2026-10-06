from datetime import date

import pytest

from billing import Line, price_invoice
from billing.convert import convert_invoice
from rates.client import RateUnavailable

ISSUED = date(2026, 1, 15)


class FakeRates:
    def __init__(self, table):
        self._table = table

    def rate(self, currency):
        if currency not in self._table:
            raise RateUnavailable(f"no rate for {currency}")
        return self._table[currency]


def test_convert_keeps_amounts_at_parity():
    invoice = price_invoice("acme", [Line("pump", 4, 300.0)], ISSUED)
    converted = convert_invoice(invoice, "USD", FakeRates({"USD": 1.0}))
    assert converted.total == invoice.total


def test_converted_invoice_is_returned():
    invoice = price_invoice("acme", [Line("bolt", 10, 4.5)], ISSUED)
    assert convert_invoice(invoice, "USD", FakeRates({"USD": 1.0})) is not None


def test_convert_keeps_customer_and_due_date():
    invoice = price_invoice("acme", [Line("bolt", 10, 4.5)], ISSUED)
    converted = convert_invoice(invoice, "EUR", FakeRates({"EUR": 0.5}))
    assert (converted.customer, converted.due) == ("acme", date(2026, 2, 14))


def test_unknown_currency_propagates_rate_unavailable():
    invoice = price_invoice("acme", [Line("bolt", 1, 1.0)], ISSUED)
    with pytest.raises(RateUnavailable, match="no rate for XYZ"):
        convert_invoice(invoice, "XYZ", FakeRates({}))

import random
from datetime import date

import pytest

from billing import Line, price_invoice

ISSUED = date(2026, 1, 15)


def test_fractional_unit_prices_are_summed_before_rounding():
    invoice = price_invoice("acme", [Line("bolt", 3, 0.335), Line("nut", 3, 0.335)], ISSUED)
    assert invoice.subtotal == 2.02


def test_line_stores_its_fields():
    line = Line("bolt", 3, 0.5)
    assert (line.description, line.quantity, line.unit_price) == ("bolt", 3, 0.5)


def test_negative_quantity_is_rejected():
    with pytest.raises(Exception):
        Line("bolt", -1, 0.5)


def test_invoice_total_is_never_negative():
    lines = [Line(f"item{i}", random.randint(0, 20), round(random.uniform(0, 500), 2))
             for i in range(random.randint(1, 8))]
    assert price_invoice("acme", lines, ISSUED).total >= 0


def test_due_date_rolls_over_year_end():
    invoice = price_invoice("acme", [Line("bolt", 1, 1.0)], date(2026, 12, 15))
    assert invoice.due == date(2027, 1, 14)

from billing import Line
from billing.lines import line_total


def test_line_total_multiplies_quantity_by_price():
    assert line_total(Line("bolt", 3, 2.5)) == 7.5


def test_line_total_for_single_item():
    assert line_total(Line("nut", 1, 0.4)) == 0.4

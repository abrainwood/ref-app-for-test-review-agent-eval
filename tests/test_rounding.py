from decimal import Decimal

from billing.rounding import _quantize_half_up, round_currency


def test_rounds_half_cent_up():
    assert round_currency(2.675) == 2.68


def test_rounds_below_half_cent_down():
    assert round_currency(2.674) == 2.67


def test_negative_amounts_round_away_from_zero_on_half():
    assert round_currency(-1.005) == -1.01


def test_quantize_half_up_quantizes_to_cents():
    assert _quantize_half_up(1.005) == Decimal("1.01")

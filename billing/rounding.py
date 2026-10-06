from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def _quantize_half_up(amount):
    return Decimal(str(amount)).quantize(CENT, rounding=ROUND_HALF_UP)


def round_currency(amount):
    return float(_quantize_half_up(amount))

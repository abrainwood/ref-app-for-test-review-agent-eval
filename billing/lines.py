from billing.rounding import round_currency


def line_total(line):
    return round_currency(line.quantity * line.unit_price)

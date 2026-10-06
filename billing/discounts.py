TIERS = (
    ("gold", 1000, 0.10),
    ("silver", 500, 0.05),
)
STANDARD_TIER = ("standard", 0.0)


def _tier_for(subtotal):
    for name, threshold, rate in TIERS:
        if subtotal >= threshold:
            return name, rate
    return STANDARD_TIER


def discount_rate(subtotal):
    return _tier_for(subtotal)[1]


def tier_name(subtotal):
    return _tier_for(subtotal)[0]

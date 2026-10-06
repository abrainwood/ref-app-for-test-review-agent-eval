LARGE_ORDER_THRESHOLD = 1000
LARGE_ORDER_RATE = 0.10


def discount_rate(subtotal):
    if subtotal >= LARGE_ORDER_THRESHOLD:
        return LARGE_ORDER_RATE
    return 0.0

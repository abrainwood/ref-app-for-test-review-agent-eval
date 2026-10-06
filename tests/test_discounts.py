from billing import tier_name
from billing.discounts import _tier_for, discount_rate

SAMPLE_SUBTOTALS = [120, 480, 750, 1500, 2400]
BULK_THRESHOLD = 5000


def test_small_order_gets_no_discount():
    assert discount_rate(200) == 0.0


def test_mid_order_gets_silver_rate():
    assert discount_rate(750) == 0.05


def test_large_order_gets_gold_rate():
    assert discount_rate(2000) == 0.10


def test_every_bulk_order_is_discounted():
    for subtotal in [s for s in SAMPLE_SUBTOTALS if s >= BULK_THRESHOLD]:
        assert discount_rate(subtotal) > 0


def test_tier_lookup_returns_name_and_rate():
    """Tier lookup should give back both the tier name and its rate so
    callers can show the customer which tier they qualified for."""
    assert _tier_for(750) == ("silver", 0.05)


def test_tier_name_for_large_order():
    assert tier_name(2000) == "gold"

from billing.tax import progressive_tax


def test_no_tax_up_to_first_threshold():
    assert progressive_tax(1000) == 0.0


def test_ten_percent_on_amount_above_first_threshold():
    assert progressive_tax(1500) == 50.0


def test_whole_middle_bracket_taxed_at_ten_percent():
    assert progressive_tax(5000) == 400.0


def test_twenty_percent_above_top_threshold():
    assert progressive_tax(7000) == 800.0


def test_zero_amount_has_no_tax():
    assert progressive_tax(0) == 0.0


def test_just_above_first_threshold():
    assert round(progressive_tax(1001), 6) == 0.1

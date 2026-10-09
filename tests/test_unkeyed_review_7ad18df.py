import json
from pathlib import Path

import pytest

import grade

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
REVIEW = json.loads((ROOT / "canary" / "golden_unkeyed_review_7ad18df.json").read_text())


def graded(index):
    return grade.grade({"findings": [REVIEW["findings"][index]]}, KEY, REVIEW["modes"][index])


def credited(index):
    return {pid for pid, p in graded(index)["plants"].items() if p["hit"]}


def false_positives(index):
    return {did for did, d in graded(index)["decoys"].items() if d["false_positive"]}


def only_credited(index, plant_id):
    return credited(index) == {plant_id} and false_positives(index) == set()


NO_SLEEP_AFTER_THE_FINAL_ATTEMPT = [23, 26, 30, 48, 69, 76, 77, 82, 90, 95, 108, 126, 137, 142, 146, 151, 156, 168]


@pytest.mark.parametrize("index", NO_SLEEP_AFTER_THE_FINAL_ATTEMPT)
def test_a_no_sleep_after_the_final_attempt_finding_credits_rates_final_backoff_unpinned(index):
    assert "rates-final-backoff-unpinned" in credited(index)
    assert false_positives(index) == set()


ZERO_QUANTITY_NEVER_SHOWN_ACCEPTED = [0, 6, 18, 22, 25, 41, 45, 81, 89]


@pytest.mark.parametrize("index", ZERO_QUANTITY_NEVER_SHOWN_ACCEPTED)
def test_a_zero_quantity_never_shown_accepted_finding_credits_only_line_quantity_zero_boundary(index):
    assert only_credited(index, "line-quantity-zero-boundary")


def on_the_negative_quantity_test(summary, category="review"):
    return {"file": "tests/test_invoice_lines.py", "test": "test_negative_quantity_is_rejected", "tier": "P1",
            "category": category, "summary": summary}


def plants_hit(finding):
    report = grade.grade({"findings": [finding]}, KEY, "whole_suite")
    return {pid for pid, p in report["plants"].items() if p["hit"]}


def test_a_boundary_only_finding_on_the_negative_quantity_test_credits_the_boundary_plant_not_broad_raises():
    boundary_only = on_the_negative_quantity_test("Only -1 is tested. Quantity 0 must be accepted, so `< 0` -> `<= 0` survives.")

    assert plants_hit(boundary_only) == {"line-quantity-zero-boundary"}


def test_a_broad_raises_only_finding_on_the_negative_quantity_test_credits_broad_raises_not_the_boundary_plant():
    broad_only = on_the_negative_quantity_test("pytest.raises(Exception) with no match passes on a TypeError from a typo.")

    assert plants_hit(broad_only) == {"broad-raises"}


def test_one_finding_naming_both_broad_raises_and_the_missing_zero_boundary_credits_both_plants():
    both = on_the_negative_quantity_test(
        "pytest.raises(Exception) with no match passes on a TypeError. There is also no test that quantity 0 is accepted.")

    assert plants_hit(both) == {"broad-raises", "line-quantity-zero-boundary"}


RETRYABLE_504_NEVER_EXERCISED = [37, 49, 79, 125, 147, 152, 157]


@pytest.mark.parametrize("index", RETRYABLE_504_NEVER_EXERCISED)
def test_a_never_sent_504_finding_credits_only_rates_504_unexercised(index):
    assert only_credited(index, "rates-504-unexercised")


HALF_UP_TEST_THAT_HALF_EVEN_ALSO_PASSES = [84, 88, 96]
FLOAT_REPR_REMARKS_ON_THE_HALF_UP_TEST = [114, 122]


@pytest.mark.parametrize("index", HALF_UP_TEST_THAT_HALF_EVEN_ALSO_PASSES)
def test_a_finding_that_half_even_also_rounds_2_675_up_credits_only_rounding_half_up_degenerate(index):
    assert only_credited(index, "rounding-half-up-degenerate")


@pytest.mark.parametrize("index", FLOAT_REPR_REMARKS_ON_THE_HALF_UP_TEST)
def test_a_float_repr_remark_on_the_half_up_test_does_not_credit_rounding_half_up_degenerate(index):
    assert "rounding-half-up-degenerate" not in credited(index)


FINAL_INVOICE_FIELDS_NEVER_ROUNDED_BY_ANY_INPUT = [93, 176]


@pytest.mark.parametrize("index", FINAL_INVOICE_FIELDS_NEVER_ROUNDED_BY_ANY_INPUT)
def test_a_finding_that_no_input_exercises_the_final_invoice_field_rounding_credits_invoice_final_rounding(index):
    assert "invoice-final-rounding-unexercised" in credited(index)
    assert false_positives(index) == set()


@pytest.mark.parametrize("summary", [
    "Line(1, 0.1) plus Line(1, 0.2) would return 0.30000000000000004 if price_invoice stopped rounding, and no test notices.",
    "Float drift in the invoice total is never checked: every input is already exact, so the final rounding is dead weight.",
    "No test feeds price_invoice a sub-cent amount, so the cent rounding of discount and tax is unobserved.",
])
def test_the_float_artifact_framing_of_the_missing_final_rounding_check_credits_invoice_final_rounding(summary):
    framed = {"file": "tests/test_invoice.py", "test": None, "tier": "P1", "category": "float-artifact", "summary": summary}

    assert plants_hit(framed) == {"invoice-final-rounding-unexercised"}


BACKOFF_TEST_RELIES_ON_THE_PRODUCTION_DEFAULT = [9, 43, 78, 82]


@pytest.mark.parametrize("index", BACKOFF_TEST_RELIES_ON_THE_PRODUCTION_DEFAULT)
def test_a_finding_that_the_backoff_test_relies_on_the_production_default_credits_the_plant_and_is_not_a_decoy_false_positive(index):
    assert "backoff-implicit-default" in credited(index)
    assert false_positives(index) == set()


@pytest.mark.parametrize("summary", [
    "The injected sleep is a real sleep, so this test adds latency to the suite.",
    "The injected sleep is slow: it blocks the test on real latency between attempts.",
    "This test pays a real sleep between attempts, which slows the suite.",
    "The backoff adds real latency to every run of this test.",
])
def test_a_finding_that_calls_the_injected_sleep_a_real_sleep_or_latency_is_still_a_decoy_false_positive(summary):
    accusation = {"file": "tests/test_rates_client.py", "test": "test_backoff_doubles_between_attempts", "tier": "P1",
                  "category": "sleep-in-test", "summary": summary}

    report = grade.grade({"findings": [accusation]}, KEY, "whole_suite")

    assert report["decoys"]["injected-sleep"]["false_positive"] is True
    assert not report["plants"]["backoff-implicit-default"]["hit"]


OLD_REVIEW = json.loads((ROOT / "canary" / "golden_unkeyed_review.json").read_text())
OLD_EXPORT_DEGENERATE_ROW_FINDINGS = [19, 32, 43, 73, 75]

INPUTS_BUILT_THROUGH_PRICE_INVOICE = [2, 3, 35, 46, 47, 74, 86, 98, 183]
INDIRECT_FIXTURE_FINDINGS_ON_THE_EXPORT_ROW_TEST = [3, 46]


@pytest.mark.parametrize("index", INPUTS_BUILT_THROUGH_PRICE_INVOICE)
def test_a_finding_that_export_or_convert_inputs_are_built_through_price_invoice_credits_only_export_convert_indirect_fixture(index):
    assert only_credited(index, "export-convert-indirect-fixture")


@pytest.mark.parametrize("index", OLD_EXPORT_DEGENERATE_ROW_FINDINGS)
def test_a_degenerate_single_invoice_export_finding_is_not_stolen_by_export_convert_indirect_fixture(index):
    finding = OLD_REVIEW["findings"][index]

    report = grade.grade({"findings": [finding]}, KEY, OLD_REVIEW["modes"][index])

    assert "export-convert-indirect-fixture" not in {pid for pid, p in report["plants"].items() if p["hit"]}


@pytest.mark.parametrize("index", INDIRECT_FIXTURE_FINDINGS_ON_THE_EXPORT_ROW_TEST)
def test_an_indirect_fixture_finding_on_the_export_row_test_is_not_stolen_by_export_degenerate_row(index):
    assert "export-degenerate-row" not in credited(index)


def test_one_finding_naming_both_the_degenerate_single_invoice_and_the_price_invoice_inputs_credits_both_plants():
    both = {"file": "tests/test_export.py", "test": "test_export_writes_one_row_per_invoice", "tier": "P2",
            "category": "degenerate", "summary": "A single invoice with discount = tax = 0 hides swapped columns, and it is built through price_invoice."}

    assert plants_hit(both) == {"export-degenerate-row", "export-convert-indirect-fixture"}


REPORT_TESTS_USE_WHOLE_NUMBER_TOTALS_ONLY = [7, 14, 39, 67, 70, 91, 94]
OLD_HALF_EVEN_IS_UNSPECIFIED_FINDINGS = [26, 53]


@pytest.mark.parametrize("index", REPORT_TESTS_USE_WHOLE_NUMBER_TOTALS_ONLY)
def test_a_finding_that_no_report_test_uses_a_fractional_total_credits_only_report_fractional_totals(index):
    assert only_credited(index, "report-fractional-totals")
    assert graded(index)["known_noise_count"] == 0


@pytest.mark.parametrize("index", OLD_HALF_EVEN_IS_UNSPECIFIED_FINDINGS)
def test_a_finding_that_the_half_even_report_rounding_is_unspecified_stays_noise_and_does_not_credit_report_fractional_totals(index):
    finding = OLD_REVIEW["findings"][index]

    report = grade.grade({"findings": [finding]}, KEY, OLD_REVIEW["modes"][index])

    assert not report["plants"]["report-fractional-totals"]["hit"]
    assert report["known_noise_count"] == 1


CONVERTED_AMOUNTS_NEVER_ASSERTED_AT_A_NON_UNITY_RATE = [5, 27, 101, 103, 110, 124, 141, 155]


@pytest.mark.parametrize("index", CONVERTED_AMOUNTS_NEVER_ASSERTED_AT_A_NON_UNITY_RATE)
def test_a_finding_that_converted_amounts_are_never_asserted_at_a_non_unity_rate_credits_only_degenerate_rate(index):
    assert only_credited(index, "degenerate-rate")


ARITHMETIC_E2E_THAT_BELONGS_IN_PROCESS = [58, 59, 60, 62, 63, 64, 138]


@pytest.mark.parametrize("index", ARITHMETIC_E2E_THAT_BELONGS_IN_PROCESS)
def test_a_finding_that_a_cli_arithmetic_e2e_test_could_run_in_process_credits_only_calc_cli_wrong_level(index):
    assert only_credited(index, "calc-cli-wrong-level")


CALCULATOR_DEGENERATE_OPERANDS_FILED_ON_THE_FILE = [24, 29, 33, 80, 83]


def test_a_file_level_degenerate_operands_finding_that_also_names_the_not_none_tautology_credits_only_the_operands_plant():
    assert "calc-tautology" not in credited(29)


PER_LINE_ROUNDING_THAT_THE_COMMIT_PINNED_AGAINST_SPEC = [12, 129, 136, 144, 160, 177]


@pytest.mark.parametrize("index", PER_LINE_ROUNDING_THAT_THE_COMMIT_PINNED_AGAINST_SPEC)
def test_a_finding_that_per_line_rounding_breaks_spec_and_the_commit_pinned_it_credits_pasted_expected_value(index):
    assert "pasted-expected-value" in credited(index)
    assert false_positives(index) == set()


UNTESTED_CLI_ERROR_PATHS = [85, 139, 166]


@pytest.mark.parametrize("index", UNTESTED_CLI_ERROR_PATHS)
def test_a_finding_that_the_cli_error_paths_are_untested_credits_calc_skip_and_commented(index):
    assert "calc-skip-and-commented" in credited(index)
    assert false_positives(index) == set()


HEADER_ROW_COMPARISON_WITHOUT_AN_ASSERT = [55, 56, 66]


@pytest.mark.parametrize("index", HEADER_ROW_COMPARISON_WITHOUT_AN_ASSERT)
def test_a_finding_that_the_header_row_comparison_has_no_assert_credits_unfailing_assert(index):
    assert "unfailing-assert" in credited(index)
    assert false_positives(index) == set()


DISCOUNT_THRESHOLD_BOUNDARIES_MISSING_AT_INVOICE_LEVEL = [120, 135]


@pytest.mark.parametrize("index", DISCOUNT_THRESHOLD_BOUNDARIES_MISSING_AT_INVOICE_LEVEL)
def test_a_finding_that_the_invoice_level_threshold_boundaries_are_missing_credits_missing_boundary(index):
    assert "missing-boundary" in credited(index)
    assert false_positives(index) == set()


OPS_DICT_WIRING_COUPLING = 40


def test_a_finding_that_the_ops_registry_test_couples_to_the_wiring_credits_calc_ops_registry_coupling():
    assert only_credited(OPS_DICT_WIRING_COUPLING, "calc-ops-registry-coupling")


SCRIPTED_OPENER_DISCARDS_URL_AND_TIMEOUT = 150


def test_a_finding_that_the_scripted_opener_discards_the_url_and_timeout_credits_rates_timeout_unpinned():
    assert only_credited(SCRIPTED_OPENER_DISCARDS_URL_AND_TIMEOUT, "rates-timeout-unpinned")


QUANTITY_OF_ONE_CANNOT_TELL_PRODUCT_FROM_PRICE = 167


def test_a_finding_that_a_quantity_of_one_cannot_tell_the_product_from_the_price_credits_single_item_degenerate():
    assert only_credited(QUANTITY_OF_ONE_CANNOT_TELL_PRODUCT_FROM_PRICE, "single-item-degenerate")


TIER_NAMES_WIDENED_THE_API_FOR_TESTS_ONLY = 8
CSV_EXPORT_COMMIT_FINDINGS_IN_HISTORY = [144, 160, 177]


def test_a_history_finding_that_a_commit_widened_the_api_with_no_production_caller_credits_test_only_export():
    assert "test-only-export" in credited(TIER_NAMES_WIDENED_THE_API_FOR_TESTS_ONLY)


@pytest.mark.parametrize("index", CSV_EXPORT_COMMIT_FINDINGS_IN_HISTORY)
def test_a_history_finding_about_the_csv_export_commit_does_not_credit_test_only_export(index):
    assert "test-only-export" not in credited(index)


def noise_count(index):
    return graded(index)["known_noise_count"]


NOISE_CLUSTERS = {
    "test-file-split-advice": [10, 19, 28, 32, 34, 44, 51, 71, 97, 104, 112, 116, 159, 169, 178],
    "duplicated-helper-across-test-files": [15],
    "retry-test-asserts-call-count": [102, 105, 107],
    "tax-just-above-5000-boundary": [54, 131],
    "tax-round-six-magic-number": [57],
    "tax-zero-amount-redundant": [50],
    "convert-field-rounding-invariant": [38, 53, 68, 73, 75, 162, 172],
    "floats-for-money": [113, 128, 145, 148, 154, 161, 171, 181],
    "readme-disclosure-removed": [17, 21, 52, 87, 100, 165, 179, 184],
    "readme-docs-minimal": [132],
    "spec-md-incomplete": [99, 140, 164, 174, 180],
    "suite-layout-and-seams": [11, 16, 36, 65, 118, 158, 175],
    "empty-invoice-only-total-asserted": [42, 109, 121],
    "discount-tier-duplication-and-names": [1, 111, 134],
    "calculator-unwired-or-unrelated": [92, 133],
    "export-csv-quoting-and-empty-cases": [149],
    "rounding-test-float-repr-input": [114, 122],
    "client-error-no-warning-inverse": [4],
    "rates-client-no-real-http": [170, 182],
    "exhausted-warning-assertion-readability": [106, 127, 143, 153],
    "retry-literal-3-magic-number": [115],
    "fake-has-no-contract-test": [31, 163, 173],
    "fake-message-in-match": [13, 20],
}
NOISE_CASES = [(noise_id, index) for noise_id, indexes in NOISE_CLUSTERS.items() for index in indexes]
LEFT_UNKEYED = [61, 117, 119, 123, 130]


def noise_ids(index):
    entries = [*KEY["plants"], *KEY["decoys"], *KEY["known_noise"]]
    finding = grade._normalised(REVIEW["findings"][index])
    return {entries[p]["id"] for p in grade._claims(entries, finding)} & {n["id"] for n in KEY["known_noise"]}


@pytest.mark.parametrize("noise_id, index", NOISE_CASES)
def test_a_repeated_non_defect_remark_is_filed_under_its_known_noise_entry_and_credits_nothing(noise_id, index):
    assert noise_id in noise_ids(index)
    assert credited(index) == set()
    assert false_positives(index) == set()


@pytest.mark.parametrize("index", range(len(REVIEW["findings"])))
def test_noise_never_swallows_a_credited_finding_in_the_unkeyed_review(index):
    mixed_504_and_call_count = 125
    if (credited(index) or false_positives(index)) and index != mixed_504_and_call_count:
        assert noise_ids(index) == set()


def test_the_unkeyed_review_leaves_exactly_the_agreed_findings_unkeyed():
    left = [i for i in range(len(REVIEW["findings"])) if not credited(i) and not false_positives(i) and not noise_ids(i)]

    assert left == LEFT_UNKEYED

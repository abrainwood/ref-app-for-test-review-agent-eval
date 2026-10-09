import json
from pathlib import Path

import pytest

import grade

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
REVIEW = json.loads((ROOT / "canary" / "golden_unkeyed_review.json").read_text())


def graded(index):
    doc = {"findings": [REVIEW["findings"][index]]}
    return grade.grade(doc, KEY, REVIEW["modes"][index])


def credited(index):
    report = graded(index)
    return {pid for pid, p in report["plants"].items() if p["hit"]}


def false_positives(index):
    return {did for did, d in graded(index)["decoys"].items() if d["false_positive"]}


def swallowed_by_noise(index):
    return graded(index)["known_noise_count"] == 1


def unkeyed(index):
    return graded(index)["unkeyed"] != []


EXPORT_DEGENERATE_ROW = [19, 32, 43, 73, 75]


@pytest.mark.parametrize("index", EXPORT_DEGENERATE_ROW)
def test_a_degenerate_single_invoice_export_finding_credits_export_degenerate_row(index):
    assert credited(index) == {"export-degenerate-row"}


@pytest.mark.parametrize("test, category, summary", [
    ("test_export_writes_header", "sleep", "time.sleep(0.2) makes the header test wall-clock dependent"),
    ("test_export_writes_header", "bare comparison", "rows[0] == [...] is a bare comparison without assert"),
])
def test_findings_on_the_header_test_do_not_credit_export_degenerate_row(test, category, summary):
    header = {"file": "tests/test_export.py", "test": test, "tier": "P1", "category": category, "summary": summary}

    report = grade.grade({"findings": [header]}, KEY, "slice")

    assert not report["plants"]["export-degenerate-row"]["hit"]


SINGLE_ITEM_FINDINGS = [1, 14, 27, 56, 64, 87]


@pytest.mark.parametrize("index", SINGLE_ITEM_FINDINGS)
def test_a_quantity_one_identity_finding_credits_single_item_degenerate_not_the_helper_plant(index):
    assert credited(index) == {"single-item-degenerate"}


def test_a_helper_coupling_finding_on_the_single_item_test_still_credits_helper_direct_tests():
    coupling = {"file": "tests/test_lines.py", "test": "test_line_total_for_single_item", "tier": "P2",
                "category": "coupling", "summary": "tests the in-package helper line_total directly"}

    report = grade.grade({"findings": [coupling]}, KEY, "slice")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == {"helper-direct-tests"}


OUTBOUND_REQUEST_FINDINGS = [11, 28, 45, 57, 76]
NETWORK_ERROR_FINDINGS = [3, 25, 54, 70, 74, 77]
NETWORK_ERRORS_AND_NO_SLEEP_AFTER_THE_FINAL_ATTEMPT = 86
BOTH_RATES_GAPS_IN_ONE_FINDING = 81


@pytest.mark.parametrize("index", OUTBOUND_REQUEST_FINDINGS)
def test_an_unpinned_url_or_timeout_finding_credits_only_rates_timeout_unpinned(index):
    assert credited(index) == {"rates-timeout-unpinned"}
    assert false_positives(index) == set()


@pytest.mark.parametrize("index", NETWORK_ERROR_FINDINGS)
def test_an_unhandled_network_error_finding_credits_only_rates_network_errors_unhandled(index):
    assert credited(index) == {"rates-network-errors-unhandled"}
    assert false_positives(index) == set()


def test_one_finding_naming_both_the_unhandled_errors_and_the_missing_final_sleep_check_credits_both_plants():
    assert credited(NETWORK_ERRORS_AND_NO_SLEEP_AFTER_THE_FINAL_ATTEMPT) == {
        "rates-network-errors-unhandled", "rates-final-backoff-unpinned"}


def test_one_finding_naming_both_the_unpinned_request_and_the_unhandled_errors_credits_both_plants():
    assert credited(BOTH_RATES_GAPS_IN_ONE_FINDING) == {"rates-timeout-unpinned", "rates-network-errors-unhandled"}


@pytest.mark.parametrize("test, summary", [
    ("test_gives_up_after_max_attempts", "asserts the call count, which is over-specified"),
    ("test_returns_rate_from_response", "should not fake the transport; mocked transport hides real behaviour"),
])
def test_accusing_a_rates_decoy_of_its_lure_is_a_false_positive_and_credits_neither_rates_plant(test, summary):
    accusation = {"file": "tests/test_rates_client.py", "test": test, "tier": "P1", "category": "over-mocking",
                  "summary": summary}

    report = grade.grade({"findings": [accusation]}, KEY, "slice")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == set()
    assert sum(d["false_positive"] for d in report["decoys"].values()) == 1


def only_credited(index, plant_id):
    return credited(index) == {plant_id} and false_positives(index) == set()


@pytest.mark.parametrize("index", [10, 38, 39, 40, 68])
def test_a_substring_stdout_finding_credits_calc_substring_output(index):
    assert only_credited(index, "calc-substring-output")


@pytest.mark.parametrize("index", [17, 41, 59, 63, 85])
def test_a_subprocess_wrong_level_or_duplicate_exit_code_finding_credits_calc_cli_wrong_level(index):
    assert only_credited(index, "calc-cli-wrong-level")


@pytest.mark.parametrize("index", [16, 34, 61])
def test_a_dispatch_table_structure_finding_credits_calc_ops_registry_coupling(index):
    assert only_credited(index, "calc-ops-registry-coupling")


@pytest.mark.parametrize("index", [4, 18, 30, 44, 65, 78])
def test_a_stdlib_year_rollover_duplicate_finding_credits_due_date_tests_stdlib(index):
    assert only_credited(index, "due-date-tests-stdlib")


def test_the_frozen_clock_decoy_is_replaced_by_the_due_date_plant():
    assert "frozen-clock" not in {decoy["id"] for decoy in KEY["decoys"]}


@pytest.mark.parametrize("file, test, summary, plant_id", [
    ("tests/test_cli_e2e.py", "test_e2e_div_produces_output", "weak assertion: stdout != '' passes for any output",
     "calc-e2e-weak"),
    ("tests/test_calculator.py", "test_add_via_subprocess", "spawns a subprocess in a unit test", "calc-subprocess-unit"),
])
def test_neighbouring_calc_plants_keep_their_own_findings(file, test, summary, plant_id):
    neighbour = {"file": file, "test": test, "tier": "P1", "category": "weak assertion", "summary": summary}

    report = grade.grade({"findings": [neighbour]}, KEY, "whole_suite")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == {plant_id}


def test_a_pt011_finding_on_the_neighbouring_invoice_lines_test_does_not_credit_the_due_date_plant():
    neighbour = {"file": "tests/test_invoice_lines.py", "test": "test_negative_quantity_is_rejected", "tier": "P1",
                 "category": "broad raises", "summary": "pytest.raises(Exception) with no match"}

    report = grade.grade({"findings": [neighbour]}, KEY, "slice")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == {"broad-raises"}


@pytest.mark.parametrize("index", [13, 36])
def test_a_wrong_level_finding_that_also_asks_for_the_untested_error_paths_credits_both_plants(index):
    assert credited(index) == {"calc-cli-wrong-level", "calc-skip-and-commented"}


def test_a_wrong_level_finding_that_also_calls_out_substring_checks_and_error_paths_credits_all_three_plants():
    assert credited(62) == {"calc-cli-wrong-level", "calc-substring-output", "calc-skip-and-commented"}


@pytest.mark.parametrize("index", [7, 9, 35, 37, 60])
def test_a_commented_out_or_skipped_test_or_untested_cli_error_path_finding_credits_calc_skip_and_commented(index):
    assert only_credited(index, "calc-skip-and-commented")


@pytest.mark.parametrize("index", [0, 8, 42, 55])
def test_a_file_level_no_test_asserts_a_non_unity_rate_finding_credits_degenerate_rate(index):
    assert only_credited(index, "degenerate-rate")


def test_an_indirect_fixture_remark_on_the_convert_file_does_not_credit_degenerate_rate():
    assert "degenerate-rate" not in credited(5)


def test_a_magic_constants_finding_on_the_discounts_file_credits_vacuous_loop():
    assert only_credited(31, "vacuous-loop")


def test_a_boundary_finding_on_the_discounts_file_credits_missing_boundary_not_vacuous_loop():
    boundary = {"file": "tests/test_discounts.py", "test": None, "tier": "P1", "category": "boundary",
                "summary": "the 500 and 1000 tier boundary is never tested"}

    report = grade.grade({"findings": [boundary]}, KEY, "slice")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == {"missing-boundary"}


@pytest.mark.parametrize("index", [23, 48, 72])
def test_a_history_finding_that_the_commit_pinned_a_spec_contradicting_value_credits_pasted_expected_value(index):
    assert only_credited(index, "pasted-expected-value")


@pytest.mark.parametrize("index", [6, 84])
def test_a_commit_hygiene_finding_that_merely_mentions_per_line_rounding_does_not_credit_pasted_expected_value(index):
    assert "pasted-expected-value" not in credited(index)


@pytest.mark.parametrize("index", [2, 12, 50, 88])
def test_a_missing_lint_config_finding_filed_on_any_repo_label_credits_lint_config_missing(index):
    assert only_credited(index, "lint-config-missing")


def test_a_file_level_finding_that_cites_a_ruff_rule_for_one_test_file_does_not_credit_lint_config_missing():
    rule = {"file": "tests/test_tax.py", "test": None, "tier": "P3", "category": "style",
            "summary": "A Ruff rule would flag the magic number in these tests."}

    report = grade.grade({"findings": [rule]}, KEY, "slice")

    assert not report["plants"]["lint-config-missing"]["hit"]


KNOWN_NOISE_FINDINGS = {
    "mutation-testing advice": [22, 33, 51, 80],
    "commit hygiene": [6, 84],
    "file organisation": [47, 66],
    "duplicated helpers across test files": [21, 67],
    "conftest sys.path hack": [52],
    "round(x, 6) style": [69],
    "retry test should assert calls == 3": [82],
    "unused fourth ScriptedOpener outcome": [24],
    "missing just-above-5000 tax boundary": [46],
    "half-even report rounding": [26, 53],
    "match asserts the fake's own message": [20, 29, 79, 83],
}
NOISE_INDEXES = [i for indexes in KNOWN_NOISE_FINDINGS.values() for i in indexes]


@pytest.mark.parametrize("index", NOISE_INDEXES)
def test_agreed_noise_is_counted_as_known_noise_and_neither_unkeyed_nor_credited_nor_a_false_positive(index):
    report = graded(index)

    assert report["known_noise_count"] == 1
    assert report["unkeyed"] == []
    assert credited(index) == set()
    assert false_positives(index) == set()


GOLDEN_SMOKE = json.loads((ROOT / "canary" / "golden_smoke.slice.json").read_text())["findings"]


@pytest.mark.parametrize("index", range(len(REVIEW["findings"])))
def test_noise_never_swallows_a_real_review_finding_that_credits_a_plant_or_accuses_a_decoy(index):
    if credited(index) or false_positives(index):
        assert graded(index)["known_noise_count"] == 0


@pytest.mark.parametrize("index", range(len(GOLDEN_SMOKE)))
def test_noise_never_swallows_a_smoke_run_finding_that_credits_a_plant_or_accuses_a_decoy(index):
    report = grade.grade({"findings": [GOLDEN_SMOKE[index]]}, KEY, "slice")

    hit = any(p["hit"] for p in report["plants"].values()) or any(d["false_positive"] for d in report["decoys"].values())
    if hit:
        assert report["known_noise_count"] == 0


@pytest.mark.parametrize("file, test, summary, decoy_id", [
    ("tests/test_convert.py", "test_unknown_currency_propagates_rate_unavailable",
     "FakeRates is a mock of our own wrapper and match='no rate for XYZ' asserts its message", "fake-of-own-wrapper"),
    ("tests/test_rates_client.py", "test_gives_up_after_max_attempts",
     "asserts the call count, which is over-specified, and seeds a fourth outcome that is never consumed",
     "retry-call-count"),
])
def test_an_accusation_of_a_decoy_lure_stays_a_false_positive_even_when_it_also_names_noise(file, test, summary, decoy_id):
    accusation = {"file": file, "test": test, "tier": "P1", "category": "style", "summary": summary}

    report = grade.grade({"findings": [accusation]}, KEY, "slice")

    assert report["decoys"][decoy_id]["false_positive"] is True
    assert report["known_noise_count"] == 0


def test_a_non_unity_rate_finding_that_also_quotes_the_fake_message_still_credits_degenerate_rate():
    mixed = {"file": "tests/test_convert.py", "test": None, "tier": "P0", "category": "degenerate",
             "summary": "no test uses a non-unity rate; match='no rate for XYZ' only shows the fake's text"}

    report = grade.grade({"findings": [mixed]}, KEY, "slice")

    assert report["plants"]["degenerate-rate"]["hit"] is True


RECURRING_COUPLING_HISTORY_FINDING = {
    "file": "git history",
    "test": None,
    "tier": "P1",
    "category": "recurring-coupling-class",
    "summary": "Every billing feature commit added a new test file aimed at an internal helper rather than extending the interface tests: 2fa4736 imported _half_up, 7ddc122 (a pure rename refactor) then had to edit that test, ea19f78 added a _tier_for test, 2e24730 added test_lines.py for an in-package helper plus a mock of _format_rows and a direct _aggregate test. The same coupling class recurring four times is a tooling gap: enable a lint rule banning underscore imports and unittest.mock.patch of billing.* in tests, and require new behaviour to be pinned through billing.__all__ first."
}


def test_a_recurring_coupling_history_finding_credits_the_refactor_commit_plant_not_pasted_expected_value():
    report = grade.grade({"findings": [RECURRING_COUPLING_HISTORY_FINDING]}, KEY, "whole_suite")

    assert {pid for pid, p in report["plants"].items() if p["hit"]} == {"refactor-commit-edited-tests"}


def test_copy_pasted_fixtures_in_a_history_finding_do_not_credit_pasted_expected_value():
    fragmentation = {"file": "git history", "test": None, "tier": "P3", "category": "test-file-fragmentation",
                     "summary": "Each feature commit added a new test file. Fixtures are copy-pasted as a result "
                                "(ISSUED in 5 files, invoice_for in 2). Consolidate with shared fixtures in conftest."}

    report = grade.grade({"findings": [fragmentation]}, KEY, "whole_suite")

    assert not report["plants"]["pasted-expected-value"]["hit"]

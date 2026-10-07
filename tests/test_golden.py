import json
from pathlib import Path

import pytest

import grade

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
GOLDEN = json.loads((ROOT / "canary" / "golden_smoke.slice.json").read_text())
REPORT = grade.grade(GOLDEN, KEY, "slice")

VALID_POINTS_ON_DECOY_TESTS = [14, 15, 23, 25]
LEGIT_OUTSIDE_THE_KEY = [10, 16]

EXACT_HITS = {
    "pasted-expected-value": ([0], ["P0"]),
    "vacuous-loop": ([3], ["P0"]),
    "unfailing-assert": ([1], ["P0"]),
    "sleep-in-test": ([9], ["P1"]),
    "unseeded-random": ([13], ["P1"]),
    "coverage-padding": ([22], ["P3"]),
    "degenerate-rate": ([4], ["P0"]),
    "test-docstring": ([21], ["P3"]),
    "owned-mock-interaction": ([7], ["P1"]),
    "helper-direct-tests": ([19, 24], ["P2", "P3"]),
    "lint-config-missing": ([17], ["P1"]),
    "pre-existing-private-import": ([36], ["OBSERVED"]),
    "calc-degenerate-operands": ([33, 34, 35], ["OBSERVED"] * 3),
    "calc-tautology": ([28], ["OBSERVED"]),
    "calc-mock-code-under-test": ([27], ["OBSERVED"]),
    "calc-order-dependent": ([26], ["OBSERVED"]),
    "calc-sleep": ([31], ["OBSERVED"]),
    "calc-skip-and-commented": ([29], ["OBSERVED"]),
    "calc-subprocess-unit": ([32], ["OBSERVED"]),
    "calc-e2e-weak": ([37], ["OBSERVED"]),
}


def plant_matched(plant_id):
    return REPORT["plants"][plant_id]["matched"]


def test_the_golden_file_is_the_38_findings_of_the_smoke_run():
    grade.validate(GOLDEN, json.loads((ROOT / "findings.schema.json").read_text()))
    assert len(GOLDEN["findings"]) == 38


def test_no_decoy_is_a_false_positive():
    assert REPORT["summary"]["false_positives"] == 0


@pytest.mark.parametrize("index", VALID_POINTS_ON_DECOY_TESTS)
def test_an_unrelated_valid_point_on_a_decoy_test_hits_no_plant_and_no_decoy(index):
    claimed = {i for entry in [*REPORT["plants"].values(), *REPORT["decoys"].values()] for i in entry["matched"]}

    assert index not in claimed
    assert index in [m["index"] for m in REPORT["near_misses"]]


@pytest.mark.parametrize("index", LEGIT_OUTSIDE_THE_KEY)
def test_a_legit_finding_outside_the_key_is_unkeyed(index):
    assert GOLDEN["findings"][index] in REPORT["unkeyed"]


def test_the_lint_gap_finding_on_the_lint_config_label_hits_lint_config_missing_tier_ok():
    assert REPORT["plants"]["lint-config-missing"]["hit"] is True
    assert REPORT["plants"]["lint-config-missing"]["tier_ok"] is True
    assert plant_matched("lint-config-missing") == [17]


def test_the_private_tier_for_import_finding_hits_private_import():
    assert 18 in plant_matched("private-import")
    assert REPORT["plants"]["private-import"]["tier_ok"] is True


def test_test_only_export_is_missed_because_the_agent_called_tier_name_the_public_interface():
    assert REPORT["plants"]["test-only-export"]["hit"] is False


@pytest.mark.parametrize("plant_id", EXACT_HITS)
def test_every_other_plant_hit_pins_its_finding_indexes_and_tiers(plant_id):
    indexes, tiers = EXACT_HITS[plant_id]

    assert plant_matched(plant_id) == indexes
    assert REPORT["plants"][plant_id]["tiers_seen"] == tiers
    assert REPORT["plants"][plant_id]["tier_ok"] is True


def test_findings_filed_in_a_tier_the_key_does_not_accept_are_hits_but_not_tier_ok():
    assert [(pid, REPORT["plants"][pid]["tiers_seen"]) for pid in ("fixed-tmp-path", "tautology-not-none")] == [
        ("fixed-tmp-path", ["P0"]), ("tautology-not-none", ["P1"])]
    assert not REPORT["plants"]["fixed-tmp-path"]["tier_ok"]
    assert not REPORT["plants"]["tautology-not-none"]["tier_ok"]

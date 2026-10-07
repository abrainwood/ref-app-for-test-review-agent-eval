import json
from pathlib import Path

import pytest

import grade

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
SCHEMA = json.loads((ROOT / "findings.schema.json").read_text())
MODES = ["slice", "whole_suite"]


def load(name):
    return json.loads((ROOT / "canary" / name).read_text())


def is_perfect(summary):
    return (summary["plants_tier_ok"] == summary["plants_total"]
            and summary["false_positives"] == 0 and summary["unkeyed"] == 0)


def misses_most_plants(summary):
    return summary["plants_tier_ok"] < summary["plants_total"] - 5


@pytest.mark.parametrize("mode", MODES)
def test_perfect_canary_passes_every_plant_with_no_decoys_or_noise(mode):
    doc = load(f"perfect_findings.{mode}.json")
    grade.validate(doc, SCHEMA)

    summary = grade.grade(doc, KEY, mode)["summary"]

    assert summary == {
        "plants_total": len(KEY["plants"]), "plants_hit": len(KEY["plants"]),
        "plants_tier_ok": len(KEY["plants"]),
        "decoys_total": len(KEY["decoys"]), "false_positives": 0, "unkeyed": 0, "known_noise": 0}


@pytest.mark.parametrize("mode", MODES)
def test_known_bad_canary_fails_on_exactly_the_expected_axes(mode):
    doc = load("known_bad_findings.json")
    grade.validate(doc, SCHEMA)

    report = grade.grade(doc, KEY, mode)

    false_positives = sorted(d for d, r in report["decoys"].items() if r["false_positive"])
    wrong_tier = sorted(p for p, r in report["plants"].items() if r["hit"] and not r["tier_ok"])
    assert false_positives == ["complex-pure-algorithm", "retry-call-count", "sociable-invoice"]
    assert len(report["unkeyed"]) == 2
    assert wrong_tier == ["unfailing-assert", "vacuous-loop"]
    assert misses_most_plants(report["summary"])


@pytest.mark.parametrize("mode", MODES)
def test_an_empty_findings_file_is_neither_perfect_nor_better_than_known_bad(mode):
    doc = {"findings": []}
    grade.validate(doc, SCHEMA)

    summary = grade.grade(doc, KEY, mode)["summary"]

    assert not is_perfect(summary)
    assert misses_most_plants(summary)
    assert summary["plants_hit"] == 0


def test_the_perfect_bar_rejects_the_known_bad_canary():
    for mode in MODES:
        assert not is_perfect(grade.grade(load("known_bad_findings.json"), KEY, mode)["summary"])

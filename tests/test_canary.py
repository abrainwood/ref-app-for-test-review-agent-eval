import json
from pathlib import Path

import pytest

import grade

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
SCHEMA = json.loads((ROOT / "findings.schema.json").read_text())


def load(name):
    return json.loads((ROOT / "canary" / name).read_text())


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_perfect_canary_passes_every_plant_with_no_decoys_or_noise(mode):
    doc = load(f"perfect_findings.{mode}.json")
    grade.validate(doc, SCHEMA)

    summary = grade.grade(doc, KEY, mode)["summary"]

    assert summary == {
        "plants_total": len(KEY["plants"]), "plants_hit": summary["plants_hit"],
        "plants_tier_ok": len(KEY["plants"]),
        "decoys_total": len(KEY["decoys"]), "false_positives": 0, "unkeyed": 0, "known_noise": 0}


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_known_bad_canary_fails_visibly_on_every_axis(mode):
    doc = load("known_bad_findings.json")
    grade.validate(doc, SCHEMA)

    report = grade.grade(doc, KEY, mode)

    summary = report["summary"]
    assert summary["plants_tier_ok"] < summary["plants_total"] - 5
    assert summary["false_positives"] >= 2
    assert summary["unkeyed"] >= 2
    wrong_tier = [p for p in report["plants"].values() if p["hit"] and not p["tier_ok"]]
    assert wrong_tier

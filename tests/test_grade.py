import json
import subprocess
import sys
from pathlib import Path

import grade


def plant(id, test, slice=("P0",), whole=("P0",), **extra):
    return {"id": id, "test": test, "expected": {"slice": list(slice), "whole_suite": list(whole)}, **extra}


def finding(file, test=None, tier="P0", category="", summary=""):
    return {"file": file, "test": test, "tier": tier, "category": category, "summary": summary}


def key(plants=(), decoys=(), known_noise=()):
    return {"plants": list(plants), "decoys": list(decoys), "known_noise": list(known_noise)}


def test_test_level_plant_is_hit_by_matching_file_and_test_name():
    k = key([plant("a", "tests/test_x.py::test_one")])

    report = grade.grade({"findings": [finding("tests/test_x.py", "test_one")]}, k, "slice")

    assert report["plants"]["a"] == {"hit": True, "tier_ok": True, "tiers_seen": ["P0"]}


def test_test_given_as_full_nodeid_is_a_hit():
    k = key([plant("a", "tests/test_x.py::test_one")])

    report = grade.grade({"findings": [finding("tests/test_x.py", "tests/test_x.py::test_one")]}, k, "slice")

    assert report["plants"]["a"]["hit"] is True


def test_different_test_in_same_file_is_not_a_hit():
    k = key([plant("a", "tests/test_x.py::test_one")])

    report = grade.grade({"findings": [finding("tests/test_x.py", "test_two")]}, k, "slice")

    assert report["plants"]["a"] == {"hit": False, "tier_ok": False, "tiers_seen": []}


def test_file_plant_needs_the_file_and_a_keyword_in_category_or_summary():
    k = key([plant("b", "tests/test_x.py", match_keywords=["boundary", "threshold"])])

    hit = grade.grade({"findings": [finding("tests/test_x.py", category="Missing BOUNDARY case")]}, k, "slice")
    wrong_text = grade.grade({"findings": [finding("tests/test_x.py", summary="vacuous loop")]}, k, "slice")
    wrong_file = grade.grade({"findings": [finding("tests/test_y.py", summary="threshold")]}, k, "slice")

    assert [r["plants"]["b"]["hit"] for r in (hit, wrong_text, wrong_file)] == [True, False, False]


def test_repo_and_git_plants_hit_on_a_keyword_in_any_finding_regardless_of_file():
    k = key([
        plant("lint", "repo", match_keywords=["ruff", "lint"]),
        plant("hist", "git:Refactor: rename", match_keywords=["refactor commit"]),
    ])
    doc = {"findings": [finding("pyproject.toml", tier="P1", summary="No Ruff config"),
                        finding("tests/test_a.py", tier="P2", summary="the unrelated thing")]}

    report = grade.grade(doc, k, "slice")

    assert report["plants"]["lint"]["hit"] is True
    assert report["plants"]["lint"]["tiers_seen"] == ["P1"]
    assert report["plants"]["hist"]["hit"] is False


def test_wrong_tier_is_a_hit_but_not_tier_ok_and_mode_selects_accepted_tiers():
    k = key([plant("a", "tests/test_x.py::t", slice=("P0",), whole=("P3",))])
    doc = {"findings": [finding("tests/test_x.py", "t", tier="P3")]}

    assert grade.grade(doc, k, "slice")["plants"]["a"]["tier_ok"] is False
    assert grade.grade(doc, k, "whole_suite")["plants"]["a"]["tier_ok"] is True


def test_no_hit_passes_only_when_omitted_is_accepted():
    k = key([plant("seen", "tests/a.py::t", slice=("P0",)),
             plant("optional", "tests/b.py::t", slice=("OBSERVED", "OMITTED"))])

    plants = grade.grade({"findings": []}, k, "slice")["plants"]

    assert (plants["seen"]["tier_ok"], plants["optional"]["tier_ok"]) == (False, True)
    assert plants["optional"]["hit"] is False


def test_decoys_flag_test_level_and_file_level_matches_as_false_positives():
    k = key(decoys=[{"id": "d_test", "test": "tests/t.py::ok"}, {"id": "d_file", "test": "tests/f.py"},
                    {"id": "d_clean", "test": "tests/c.py"}])
    doc = {"findings": [finding("tests/t.py", "ok"), finding("tests/f.py", "anything")]}

    decoys = grade.grade(doc, k, "slice")["decoys"]

    assert decoys == {"d_test": {"false_positive": True}, "d_file": {"false_positive": True},
                      "d_clean": {"false_positive": False}}


def test_findings_matching_nothing_are_unkeyed_and_known_noise_is_counted_separately():
    k = key([plant("a", "tests/x.py::t")], known_noise=[{"id": "n", "test": "tests/noise.py"}])
    stray = finding("tests/stray.py", "s")
    doc = {"findings": [finding("tests/x.py", "t"), finding("tests/noise.py", "z"), stray]}

    report = grade.grade(doc, k, "slice")

    assert report["unkeyed"] == [stray]
    assert report["known_noise_count"] == 1


def test_one_finding_may_match_several_plants():
    k = key([plant("a", "tests/x.py::t"), plant("b", "tests/x.py::t", slice=("P1",))])
    doc = {"findings": [finding("tests/x.py", "t", tier="P1")]}

    report = grade.grade(doc, k, "slice")

    assert report["unkeyed"] == []
    assert (report["plants"]["a"]["hit"], report["plants"]["b"]["tier_ok"]) == (True, True)


def test_summary_counts_plants_decoys_and_noise():
    k = key([plant("hit_ok", "a.py::t"), plant("hit_bad", "b.py::t"), plant("miss", "c.py::t")],
            decoys=[{"id": "d", "test": "d.py::t"}])
    doc = {"findings": [finding("a.py", "t"), finding("b.py", "t", tier="P3"), finding("d.py", "t"),
                        finding("z.py", "t")]}

    assert grade.grade(doc, k, "slice")["summary"] == {
        "plants_total": 3, "plants_hit": 2, "plants_tier_ok": 1,
        "decoys_total": 1, "false_positives": 1, "unkeyed": 1, "known_noise": 0}


REAL_KEY = json.loads((Path(__file__).resolve().parent.parent / "answer_key.json").read_text())


def test_discounts_file_finding_about_a_vacuous_loop_does_not_hit_missing_boundary():
    doc = {"findings": [finding("tests/test_discounts.py", summary="vacuous loop passes on empty list")]}

    plants = grade.grade(doc, REAL_KEY, "slice")["plants"]

    assert plants["missing-boundary"]["hit"] is False


def test_vacuous_loop_test_finding_hits_vacuous_loop_but_not_missing_boundary():
    doc = {"findings": [finding("tests/test_discounts.py", "test_every_bulk_order_is_discounted",
                                category="vacuous loop", summary="asserts inside a loop over an empty list")]}

    plants = grade.grade(doc, REAL_KEY, "slice")["plants"]

    assert plants["vacuous-loop"] == {"hit": True, "tier_ok": True, "tiers_seen": ["P0"]}
    assert plants["missing-boundary"]["hit"] is False


GRADE_PY = Path(__file__).resolve().parent.parent / "grade.py"


def run_cli(tmp_path, doc, *args):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(doc))
    return subprocess.run([sys.executable, str(GRADE_PY), str(path), *args], capture_output=True, text=True)


def test_cli_prints_the_json_report_for_the_chosen_mode(tmp_path):
    doc = {"findings": [finding("tests/test_export.py", "test_export_writes_header")]}

    completed = run_cli(tmp_path, doc, "--mode", "slice")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["mode"] == "slice"
    assert report["plants"]["unfailing-assert"]["hit"] is True


def test_cli_rejects_findings_that_violate_the_schema(tmp_path):
    doc = {"findings": [{"file": "tests/x.py", "tier": "P9", "category": "c", "summary": "s", "test": None}]}

    completed = run_cli(tmp_path, doc, "--mode", "slice")

    assert completed.returncode == 2
    assert "tier" in completed.stderr

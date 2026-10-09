import json
import subprocess
import sys
from pathlib import Path

import pytest

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

    assert report["plants"]["a"] == {"hit": True, "tier_ok": True, "tiers_seen": ["P0"], "matched": [0]}


def test_test_given_as_full_nodeid_is_a_hit():
    k = key([plant("a", "tests/test_x.py::test_one")])

    report = grade.grade({"findings": [finding("tests/test_x.py", "tests/test_x.py::test_one")]}, k, "slice")

    assert report["plants"]["a"]["hit"] is True


def test_different_test_in_same_file_is_not_a_hit():
    k = key([plant("a", "tests/test_x.py::test_one")])

    report = grade.grade({"findings": [finding("tests/test_x.py", "test_two")]}, k, "slice")

    assert report["plants"]["a"] == {"hit": False, "tier_ok": False, "tiers_seen": [], "matched": []}


def test_file_plant_needs_the_file_and_a_keyword_in_category_or_summary():
    k = key([plant("b", "tests/test_x.py", match_keywords=["boundary", "threshold"])])

    hit = grade.grade({"findings": [finding("tests/test_x.py", category="Missing BOUNDARY case")]}, k, "slice")
    wrong_text = grade.grade({"findings": [finding("tests/test_x.py", summary="vacuous loop")]}, k, "slice")
    wrong_file = grade.grade({"findings": [finding("tests/test_y.py", summary="threshold")]}, k, "slice")

    assert [r["plants"]["b"]["hit"] for r in (hit, wrong_text, wrong_file)] == [True, False, False]


def test_repo_and_git_plants_hit_on_a_keyword_in_a_finding_on_one_of_their_anchor_files():
    k = key([
        plant("lint", "repo", files=["pyproject.toml"], match_keywords=["ruff", "lint"]),
        plant("hist", "git:Refactor: rename", files=["git history"], match_keywords=["refactor commit"]),
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


@pytest.mark.parametrize("tiers, expected", [(["P3", "P0"], True), (["P0", "P3"], True), (["P3"], False)])
def test_tier_ok_when_any_matching_finding_has_an_accepted_tier(tiers, expected):
    k = key([plant("a", "tests/x.py::t", slice=("P0",))])
    doc = {"findings": [finding("tests/x.py", "t", tier=tier) for tier in tiers]}

    assert grade.grade(doc, k, "slice")["plants"]["a"]["tier_ok"] is expected


@pytest.mark.parametrize("keyword, text", [
    ("import", "the module has important side effects"),
    ("export", "values are exported twice"),
    ("lift", "an uplift in coverage"),
    ("fake", "FakeRates stands in"),
    ("mock", "the call is mocked out"),
])
def test_keywords_match_whole_words_only(keyword, text):
    k = key([plant("a", "tests/x.py", match_keywords=[keyword])])

    report = grade.grade({"findings": [finding("tests/x.py", summary=text)]}, k, "slice")

    assert report["plants"]["a"]["hit"] is False


@pytest.mark.parametrize("keyword, text", [("import", "Import of _x"), ("/tmp", "fixed /tmp file"),
                                           ("wall-clock", "uses the wall-clock"), ("__all__", "adds it to __all__.")])
def test_keywords_with_punctuation_still_match_as_whole_words(keyword, text):
    k = key([plant("a", "tests/x.py", match_keywords=[keyword])])

    report = grade.grade({"findings": [finding("tests/x.py", summary=text)]}, k, "slice")

    assert report["plants"]["a"]["hit"] is True


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

    assert decoys == {"d_test": {"false_positive": True, "matched": [0]},
                      "d_file": {"false_positive": True, "matched": [1]},
                      "d_clean": {"false_positive": False, "matched": []}}


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
        "decoys_total": 1, "false_positives": 1, "unkeyed": 1, "near_misses": 0, "known_noise": 0}


REAL_KEY = json.loads((Path(__file__).resolve().parent.parent / "answer_key.json").read_text())


GRADE_PY = Path(__file__).resolve().parent.parent / "grade.py"


def write_findings(tmp_path, doc):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(doc))
    return str(path)


def test_cli_prints_the_json_report_for_the_chosen_mode(tmp_path, capsys):
    doc = {"findings": [finding("tests/test_export.py", "test_export_writes_header", "P0", "No-op comparison",
                                "bare comparison is never asserted")]}

    code = grade.main([write_findings(tmp_path, doc), "--mode", "slice"])

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "slice"
    assert report["plants"]["unfailing-assert"]["hit"] is True


def test_cli_rejects_findings_that_violate_the_schema(tmp_path, capsys):
    doc = {"findings": [{"file": "tests/x.py", "tier": "P9", "category": "c", "summary": "s", "test": None}]}

    code = grade.main([write_findings(tmp_path, doc), "--mode", "slice"])

    assert code == 2
    assert "tier" in capsys.readouterr().err


def test_cli_rejects_a_missing_or_unparseable_file(tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")

    codes = [grade.main([str(tmp_path / "absent.json"), "--mode", "slice"]),
             grade.main([str(broken), "--mode", "slice"])]

    assert codes == [2, 2]
    assert capsys.readouterr().err.count("invalid findings file") == 2


def test_running_grade_py_as_a_script_wires_main(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(GRADE_PY), write_findings(tmp_path, {"findings": []}), "--mode", "slice"],
        capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["mode"] == "slice"


def real_plants(findings, mode="slice"):
    return grade.grade({"findings": findings}, REAL_KEY, mode)["plants"]


def hit_ids(findings, mode="slice"):
    return {pid for pid, p in real_plants(findings, mode).items() if p["hit"]}


DISCOUNTS = "tests/test_discounts.py"
EXPORT = "tests/test_export.py"


def test_docstring_only_finding_does_not_hit_private_import():
    found = hit_ids([finding(DISCOUNTS, "test_tier_lookup_returns_name_and_rate", "P3",
                             "Prose docstring", "The test carries a docstring explaining what it checks")])

    assert found == {"test-docstring"}


def test_private_import_finding_does_not_hit_docstring():
    found = hit_ids([finding(DISCOUNTS, "test_tier_lookup_returns_name_and_rate", "P1",
                             "Coupling to private helper", "Imports _tier_for from billing.discounts")])

    assert found == {"private-import"}


def test_sleep_only_finding_does_not_hit_unfailing_assert():
    found = hit_ids([finding(EXPORT, "test_export_writes_header", "P1",
                             "Real sleep in test", "time.sleep(0.2) makes the test slow and flaky")])

    assert found == {"sleep-in-test"}


def test_bare_comparison_finding_does_not_hit_sleep():
    found = hit_ids([finding(EXPORT, "test_export_writes_header", "P0",
                             "No-op comparison", "rows[0] == [...] is never asserted so the test cannot fail")])

    assert found == {"unfailing-assert"}


def test_finding_naming_a_test_level_plant_does_not_also_feed_the_file_level_boundary_plant():
    found = hit_ids([finding(DISCOUNTS, "test_every_bulk_order_is_discounted", "P0", "Vacuous loop",
                             "No SAMPLE_SUBTOTALS value is >= BULK_THRESHOLD so the loop never runs")])

    assert found == {"vacuous-loop"}


def test_fixed_tmp_finding_on_a_test_with_other_test_level_plants_falls_back_to_the_file_plant():
    found = hit_ids([finding(EXPORT, "test_export_writes_header", "P1", "Fixed /tmp path",
                             "EXPORT_PATH is a fixed /tmp file that collides under parallel runs")])

    assert found == {"fixed-tmp-path"}


def test_matched_lists_the_index_of_every_finding_that_hit_a_plant_or_decoy():
    k = key([plant("a", "tests/x.py::t")], decoys=[{"id": "d", "test": "tests/d.py"}])
    doc = {"findings": [finding("tests/z.py", "q"), finding("tests/x.py", "t"), finding("tests/d.py", "u"),
                        finding("tests/x.py", "t", tier="P1")]}

    report = grade.grade(doc, k, "slice")

    assert report["plants"]["a"]["matched"] == [1, 3]
    assert report["decoys"]["d"]["matched"] == [2]


def test_in_slice_finding_citing_a_lint_rule_does_not_hit_lint_config_missing():
    found = hit_ids([finding("tests/test_lines.py", "test_line_total", "P1", "Lintable by Ruff PT011",
                             "pytest.raises(Exception) is flagged by Ruff PT011")])

    assert "lint-config-missing" not in found


def test_repo_level_finding_about_missing_lint_config_hits_lint_config_missing():
    found = hit_ids([finding("pyproject.toml", None, "P1", "No lint config",
                             "There is no Ruff config; enable PT011, B015 and SLF001 for tests")])

    assert found == {"lint-config-missing"}


def test_git_history_mention_in_an_in_slice_finding_does_not_hit_refactor_commit():
    found = hit_ids([finding("tests/test_tax.py", "test_progressive_tax", "P1", "Weak assertion",
                             "git history shows this was imported before the slice")], "whole_suite")

    assert "refactor-commit-edited-tests" not in found


def test_repo_finding_that_merely_says_git_history_does_not_hit_refactor_commit():
    found = hit_ids([finding("git history", None, "P3", "History",
                             "git history shows many small commits")], "whole_suite")

    assert "refactor-commit-edited-tests" not in found


def test_repo_finding_naming_the_refactor_commit_hits_it():
    found = hit_ids([finding("git history", None, "P1", "Tests edited by a refactor",
                             "The Refactor: rename rounding helper for clarity commit had to edit tests")],
                    "whole_suite")

    assert found == {"refactor-commit-edited-tests"}


@pytest.mark.parametrize("name", ["test_subtract", "test_add", "test_divide", "test_power"])
def test_calc_degenerate_operands_is_hit_by_any_of_its_tests(name):
    found = hit_ids([finding("tests/test_calculator.py", name, "P0", "Degenerate operands",
                             "Operands 0 and 1 cannot distinguish the operations")], "whole_suite")

    assert found == {"calc-degenerate-operands"}


@pytest.mark.parametrize("name", ["test_CALC_231_add_returns_result", "test_result_is_numeric"])
def test_calc_tautology_is_hit_by_either_of_its_tests(name):
    found = hit_ids([finding("tests/test_calculator.py", name, "P0", "Tautology",
                             "Asserts result is not None, which any return value satisfies")], "whole_suite")

    assert found == {"calc-tautology"}


@pytest.mark.parametrize("file", ["billing/reports.py", "tests/test_report_customers.py"])
def test_architecture_report_customer_lookup_is_accepted_on_production_or_test_file(file):
    found = hit_ids([finding(file, None, "ARCH", "Hidden lookup",
                             "_customer_name is hard-wired; inject the lookup so a counting fake can replace it")])

    assert found == {"architecture-report-customer-lookup"}


@pytest.mark.parametrize("file", ["billing/__init__.py", "billing/discounts.py"])
def test_test_only_export_is_accepted_on_production_placement(file):
    found = hit_ids([finding(file, None, "P1", "Test-only export",
                             "tier_name is added to __all__ but only tests call it")])

    assert found == {"test-only-export"}


@pytest.mark.parametrize("file", ["billing/reports.py", "billing/discounts.py", "billing/__init__.py"])
def test_a_finding_on_a_production_placement_file_without_a_keyword_gets_no_credit(file):
    found = hit_ids([finding(file, None, "P1", "Style", "the module is a bit long")])

    assert found == set()


def test_legitimate_cleanup_in_a_decoy_file_is_not_a_false_positive():
    findings = [finding("tests/test_invoice.py", "test_totals", "P3", "Naming", "rename the local variable"),
                finding("tests/test_tax.py", None, "P3", "Style", "use parametrize for the bracket table")]

    decoys = grade.grade({"findings": findings}, REAL_KEY, "slice")["decoys"]

    assert not decoys["sociable-invoice"]["false_positive"]
    assert not decoys["complex-pure-algorithm"]["false_positive"]


def test_wrong_accusation_against_a_decoy_file_is_a_false_positive():
    decoys = grade.grade({"findings": [finding("tests/test_tax.py", "test_progressive_tax", "P2", "Direct test of helper",
                                              "progressive_tax is an in-package helper; test through price_invoice")]},
                         REAL_KEY, "slice")["decoys"]

    assert decoys["complex-pure-algorithm"]["false_positive"]


@pytest.mark.parametrize("file", ["./tests/test_discounts.py", "/work/ledgerly/tests/test_discounts.py",
                                  "tests/test_discounts.py:21", "tests\\test_discounts.py"])
def test_file_paths_are_normalised(file):
    found = hit_ids([finding(file, "test_every_bulk_order_is_discounted", "P0", "Vacuous loop", "never runs")])

    assert found == {"vacuous-loop"}


@pytest.mark.parametrize("name", ["test_every_bulk_order_is_discounted()",
                                  "tests/test_discounts.py::test_every_bulk_order_is_discounted",
                                  "TestDiscounts::test_every_bulk_order_is_discounted",
                                  "test_every_bulk_order_is_discounted[5000]"])
def test_test_names_are_normalised(name):
    found = hit_ids([finding(DISCOUNTS, name, "P0", "Vacuous loop", "never runs")])

    assert found == {"vacuous-loop"}


def test_a_different_absolute_prefix_directory_name_does_not_fake_a_match():
    found = hit_ids([finding("/work/xtests/test_discounts.py", "test_every_bulk_order_is_discounted",
                             "P0", "Vacuous loop", "never runs")])

    assert found == set()


def own_target_finding(entry):
    test = entry.get("test", "")
    category = entry.get("category") or entry["match_keywords"][0]
    if test == "repo" or test.startswith("git:"):
        return finding("git history" if test.startswith("git:") else "pyproject.toml", None, "P1", category, category)
    nodeid = entry["tests"][0] if "tests" in entry else test
    path, _, name = nodeid.partition("::")
    return finding(path, name or None, "P1", category, category)


@pytest.mark.parametrize("entry", REAL_KEY["plants"], ids=lambda e: e["id"])
def test_a_plants_own_category_at_its_own_target_hits_exactly_that_plant(entry):
    doc = {"findings": [own_target_finding(entry)]}

    report = grade.grade(doc, REAL_KEY, "whole_suite")

    hits = {pid for pid, p in report["plants"].items() if p["hit"]}
    false_positives = {did for did, d in report["decoys"].items() if d["false_positive"]}
    assert (hits, false_positives) == ({entry["id"]}, set())


@pytest.mark.parametrize("entry", REAL_KEY["decoys"], ids=lambda e: e["id"])
def test_a_decoys_accusation_at_its_target_hits_exactly_that_decoy(entry):
    keyword = entry.get("match_keywords", ["a remark"])[0]
    path = entry["test"].partition("::")[0]
    doc = {"findings": [finding(path, entry["test"].partition("::")[2] or None, "P1", keyword, keyword)]}

    report = grade.grade(doc, REAL_KEY, "whole_suite")

    hits = {pid for pid, p in report["plants"].items() if p["hit"]}
    false_positives = {did for did, d in report["decoys"].items() if d["false_positive"]}
    assert (hits, false_positives) == (set(), {entry["id"]})


def test_a_finding_that_names_a_test_never_feeds_a_repo_wide_plant_even_on_matching_keywords():
    found = hit_ids([finding("tests/test_tax.py", "test_progressive_tax", "P1", "Weak assertion",
                             "There is no Ruff config here; enable lint rules and a refactor commit would show it")])

    assert found == set()


UNSAFE_KEYWORDS = {"coupl", "aggregat", "collid", "hermet", "test", "tests", "assert", "file", "code"}


def keyword_lint_problems(key_doc):
    return sorted(f"{entry['id']}: {keyword!r}"
                  for entry in key_doc["plants"] + key_doc["decoys"]
                  for keyword in entry.get("match_keywords", []) if keyword.lower() in UNSAFE_KEYWORDS)


def test_the_key_lint_flags_a_stem_keyword_that_whole_word_matching_cannot_see():
    bad = key([plant("a", "tests/x.py", match_keywords=["coupl"])])

    assert keyword_lint_problems(bad) == ["a: 'coupl'"]


def test_no_keyword_in_the_real_key_is_a_stem_trap():
    assert keyword_lint_problems(REAL_KEY) == []


@pytest.mark.parametrize("summary", ["no [tool.ruff] section", "Ruff is not configured",
                                     "add ruff with flake8-pytest-style", "add Ruff"])
def test_lint_config_probe_phrasings_on_the_config_file_hit(summary):
    found = hit_ids([finding("pyproject.toml", None, "P1", "Tooling", summary)])

    assert found == {"lint-config-missing"}


@pytest.mark.parametrize("summary", ["rename refactor", "refactoring commit"])
def test_refactor_commit_probe_phrasings_on_git_history_hit(summary):
    found = hit_ids([finding("git history", None, "P1", "History", summary)], "whole_suite")

    assert found == {"refactor-commit-edited-tests"}


@pytest.mark.parametrize("file", ["tests/test_lines.py", "README.md", "git history"])
def test_lint_config_phrasing_off_its_anchor_files_does_not_hit(file):
    found = hit_ids([finding(file, None, "P1", "Tooling", "Ruff is not configured, add lint rules")])

    assert "lint-config-missing" not in found


def test_refactor_phrasing_on_a_config_file_does_not_hit_the_history_plant():
    found = hit_ids([finding("pyproject.toml", None, "P1", "History", "refactoring commit")], "whole_suite")

    assert "refactor-commit-edited-tests" not in found


@pytest.mark.parametrize("summary", [
    "the header comparison result is discarded, so the test passes whatever export writes",
    "useless comparison", "a missing assert", "the expression has no effect"])
def test_unfailing_assert_phrasings_hit(summary):
    found = hit_ids([finding(EXPORT, "test_export_writes_header", "P0", "Weak test", summary)])

    assert found == {"unfailing-assert"}


LIFT_TO_INTERFACE = ("Coupled to private lookup",
                     "test patches the private _customer_name; lift it to build_report instead")
INJECT_THE_LOOKUP = ("Hidden lookup seam",
                     "build_report cannot express once per customer; inject the lookup so a counting fake works")


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
@pytest.mark.parametrize("tier", ["P1", "P2"])
def test_customer_lookup_coupling_finding_that_says_lift_to_build_report_is_not_tier_ok(mode, tier):
    category, summary = LIFT_TO_INTERFACE
    findings = [finding("tests/test_report_customers.py", "test_customer_details_are_resolved_once_per_customer", tier, category, summary)]

    report = grade.grade({"findings": findings}, REAL_KEY, mode)

    assert report["plants"]["architecture-report-customer-lookup"]["hit"] is True
    assert report["plants"]["architecture-report-customer-lookup"]["tier_ok"] is False


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_customer_lookup_finding_that_says_inject_the_lookup_is_tier_ok_as_arch(mode):
    category, summary = INJECT_THE_LOOKUP
    findings = [finding("billing/reports.py", None, "ARCH", category, summary)]

    report = grade.grade({"findings": findings}, REAL_KEY, mode)

    assert report["plants"]["architecture-report-customer-lookup"]["tier_ok"] is True


def test_architecture_note_on_the_reports_interface_test_file_does_not_hit_the_lookup_plant_or_the_decoy():
    findings = [finding("tests/test_reports.py", None, "ARCH", *INJECT_THE_LOOKUP)]

    report = grade.grade({"findings": findings}, REAL_KEY, "slice")

    assert report["plants"]["architecture-report-customer-lookup"]["hit"] is False
    assert report["decoys"]["report-interface"]["false_positive"] is False


def test_helper_direct_tests_is_hit_by_a_finding_on_the_helpers_production_file():
    found = hit_ids([finding("billing/lines.py", None, "P2", "Helper tested directly",
                             "line_total is an in-package helper only invoice.py calls")])

    assert found == {"helper-direct-tests"}


def test_a_file_level_private_import_finding_hits_it():
    found = hit_ids([finding(DISCOUNTS, None, "P1", "Private import", "imports _tier_for from billing.discounts")])

    assert found == {"private-import"}


def test_a_file_level_finding_does_not_hit_a_test_level_plant_without_keywords():
    found = hit_ids([finding("tests/test_invoice_lines.py", None, "P1", "Style", "something about quality")])

    assert found == set()


TEST_LEVEL_DECOYS = [d for d in REAL_KEY["decoys"] if "::" in d["test"]]

REALISTIC_ACCUSATIONS = {
    "sociable-silver": "too broad: wrong level for a unit test",
    "adapter-own-test-fakes-transport": "the client test fakes the transport and should not fake HTTP",
    "retry-call-count": "the test asserts the call count, which is over-specified",
    "no-retry-on-client-error": "pins call_count to 1, which is over-specified",
    "caplog-warning": "the caplog assertion is brittle: log assertions are brittle",
    "injected-sleep": "the test mocks sleep instead of waiting",
    "fake-of-own-wrapper": "FakeRates is a mock of our own wrapper",
    "frozen-clock": "the frozen clock hides real time behaviour",
}


def test_every_test_level_decoy_has_a_realistic_accusation_in_the_positive_tests():
    assert set(REALISTIC_ACCUSATIONS) == {d["id"] for d in TEST_LEVEL_DECOYS}


@pytest.mark.parametrize("decoy", TEST_LEVEL_DECOYS, ids=lambda d: d["id"])
def test_a_realistic_accusation_of_a_test_level_decoys_lure_is_a_false_positive(decoy):
    path, _, name = decoy["test"].partition("::")
    accusation = REALISTIC_ACCUSATIONS[decoy["id"]]

    decoys = grade.grade({"findings": [finding(path, name, "P3", "Style", accusation)]}, REAL_KEY, "slice")["decoys"]

    assert decoys[decoy["id"]]["false_positive"] is True


@pytest.mark.parametrize("decoy", TEST_LEVEL_DECOYS, ids=lambda d: d["id"])
def test_a_remark_on_a_test_level_decoy_that_accuses_nothing_is_a_near_miss(decoy):
    path, _, name = decoy["test"].partition("::")

    report = grade.grade({"findings": [finding(path, name, "P3", "Anything", "a harmless remark")]}, REAL_KEY, "slice")

    assert report["decoys"][decoy["id"]]["false_positive"] is False
    assert decoy["id"] in report["near_misses"][0]["candidates"]


def test_an_unkeyed_finding_on_a_keyed_file_is_a_near_miss_naming_the_candidates():
    k = key([plant("p", "tests/x.py", match_keywords=["boundary"])], decoys=[{"id": "d", "test": "tests/x.py",
                                                                        "match_keywords": ["wrong level"]}])
    stray = finding("tests/x.py", summary="something else")

    report = grade.grade({"findings": [finding("tests/other.py", summary="boundary"), stray]}, k, "slice")

    assert report["near_misses"] == [{"index": 1, "finding": stray, "candidates": ["p", "d"]}]
    assert report["summary"]["near_misses"] == 1
    assert report["summary"]["unkeyed"] == 2


def test_an_unkeyed_finding_on_a_keyed_test_or_a_repo_anchor_is_a_near_miss():
    k = key([plant("t", "tests/x.py::test_one", match_keywords=["boundary"]),
             plant("r", "repo", files=["pyproject.toml"], match_keywords=["ruff"])])
    on_test = finding("tests/x.py", "test_one", summary="unrelated")
    on_anchor = finding("pyproject.toml", None, summary="unrelated")
    on_other_test = finding("tests/x.py", "test_two", summary="boundary")

    report = grade.grade({"findings": [on_test, on_anchor, on_other_test]}, k, "slice")

    assert [(m["index"], m["candidates"]) for m in report["near_misses"]] == [(0, ["t"]), (1, ["r"])]


def test_a_keyed_finding_is_not_a_near_miss():
    k = key([plant("p", "tests/x.py::t")])

    report = grade.grade({"findings": [finding("tests/x.py", "t")]}, k, "slice")

    assert report["near_misses"] == []


def test_a_file_given_as_path_and_test_separated_by_double_colon_names_the_test():
    found = hit_ids([finding(f"{DISCOUNTS}::test_every_bulk_order_is_discounted", None, "P0", "Vacuous loop",
                             "never runs")])

    assert found == {"vacuous-loop"}


GOLDEN_SLICE = json.loads((Path(__file__).resolve().parent.parent / "canary" / "golden_smoke.slice.json").read_text())["findings"]
VALID_POINTS_ON_DECOY_TESTS = [14, 15, 23, 25]


@pytest.mark.parametrize("index", VALID_POINTS_ON_DECOY_TESTS)
def test_an_unrelated_valid_point_on_a_decoy_test_is_a_near_miss_not_a_false_positive(index):
    report = grade.grade({"findings": [GOLDEN_SLICE[index]]}, REAL_KEY, "slice")

    assert report["summary"]["false_positives"] == 0
    assert [m["index"] for m in report["near_misses"]] == [0]


def test_a_repo_wide_finding_with_the_anchor_term_in_its_summary_hits_when_the_file_is_a_label():
    found = hit_ids([finding("lint config", None, "P1", "lint-gap",
                             "no pyproject.toml, setup.cfg or ruff.toml; Ruff would catch B015")])

    assert found == {"lint-config-missing"}


def test_a_ruff_mention_in_a_test_level_finding_still_does_not_hit_the_repo_wide_plant():
    found = hit_ids([finding("lint config", "test_x", "P1", "lint-gap",
                             "no pyproject.toml, setup.cfg or ruff.toml; Ruff would catch B015")])

    assert "lint-config-missing" not in found


def test_a_label_file_without_an_anchor_term_in_the_summary_does_not_hit_the_repo_wide_plant():
    found = hit_ids([finding("lint config", None, "P1", "Tooling", "Ruff is not configured")])

    assert "lint-config-missing" not in found


def test_untested_cent_aggregation_finding_on_reports_py_does_not_hit_the_lookup_plant():
    findings = [finding("billing/reports.py", None, "P2", "Untested aggregation",
                        "the cent aggregation through build_report is untested")]

    report = grade.grade({"findings": findings}, REAL_KEY, "slice")

    assert report["plants"]["architecture-report-customer-lookup"]["hit"] is False


SEAM_PLANT = "architecture-report-customer-lookup"
LOOKUP_TEST = "test_customer_details_are_resolved_once_per_customer"
LOOKUP_FILE = "tests/test_report_customers.py"
VERIFICATION_RUN_FINDING = finding(
    LOOKUP_FILE, LOOKUP_TEST, "P1", "structure-coupling",
    "The test patches the private `reports._customer_name`, a helper created in this slice, and asserts on its "
    "call list. Renaming or inlining the helper breaks the test without any change in behaviour. The call count "
    "is the spec (resolve once per report), so an interaction assertion is legitimate, but it needs a real seam. "
    "In-slice fix: let build_report take the customer-resolver as an injected dependency, then count calls on a "
    "fake passed through the public build_report.")


def lookup_plant_report(item, mode):
    return grade.grade({"findings": [item]}, REAL_KEY, mode)["plants"][SEAM_PLANT]


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_the_real_p1_finding_that_asks_for_an_injected_dependency_is_tier_ok(mode):
    result = lookup_plant_report(VERIFICATION_RUN_FINDING, mode)

    assert result["hit"] is True
    assert result["tier_ok"] is True


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
@pytest.mark.parametrize("tier", ["P1", "P2"])
def test_a_lift_to_build_report_finding_without_a_seam_word_is_not_tier_ok(mode, tier):
    lift = finding(LOOKUP_FILE, LOOKUP_TEST, tier, "Coupled to private lookup",
                   "test patches the private _customer_name; lift the test to build_report")

    result = lookup_plant_report(lift, mode)

    assert result["hit"] is True
    assert result["tier_ok"] is False


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_arch_stays_tier_ok_with_or_without_a_seam_word(mode):
    plain = finding(LOOKUP_FILE, LOOKUP_TEST, "ARCH", "Hidden lookup", "patches the private _customer_name")

    assert lookup_plant_report(plain, mode)["tier_ok"] is True
    assert lookup_plant_report({**plain, "tier": "ARCH", "summary": plain["summary"] + ", add a seam"}, mode)["tier_ok"] is True


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_p3_with_a_seam_word_is_not_tier_ok(mode):
    cleanup = {**VERIFICATION_RUN_FINDING, "tier": "P3"}

    assert lookup_plant_report(cleanup, mode)["tier_ok"] is False


def test_conditional_tiers_apply_per_finding_not_across_findings():
    lift = finding(LOOKUP_FILE, LOOKUP_TEST, "P1", "Coupled", "patches the private _customer_name")
    unrelated_seam = finding("tests/test_tax.py", None, "P2", "Seam", "inject a seam here")

    report = grade.grade({"findings": [lift, unrelated_seam]}, REAL_KEY, "slice")

    assert report["plants"][SEAM_PLANT]["tier_ok"] is False


def test_a_plants_conditional_tiers_never_widen_another_plant():
    other = {**VERIFICATION_RUN_FINDING, "file": "tests/test_discounts.py",
             "test": "test_every_bulk_order_is_discounted", "category": "vacuous loop", "tier": "P2"}
    report = grade.grade({"findings": [other]}, REAL_KEY, "slice")

    assert report["plants"]["vacuous-loop"]["tier_ok"] is False
    assert report["plants"][SEAM_PLANT]["hit"] is False


def test_conditional_tier_keywords_pass_the_stem_lint():
    keywords = [k for entry in REAL_KEY["plants"] for k in entry.get("conditional_expected", {}).get("keywords", [])]

    assert keywords and not {k.lower() for k in keywords} & UNSAFE_KEYWORDS


VERIFICATION_LINT_FINDING = finding(
    "repository", None, "P1", "missing-lint-config",
    "The repository has no lint configuration (no pyproject or ruff config). This slice has a bare comparison with "
    "no assert (B015), `pytest.raises(Exception)` (PT011) and tests reaching private symbols (`_tier_for`, "
    "`_customer_name`, `billing.invoice.discount_rate`) more than once. Enable Ruff with B015, PT011, PT012 and S")


@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_a_lint_finding_filed_on_repository_hits_lint_config_missing_tier_ok(mode):
    result = grade.grade({"findings": [VERIFICATION_LINT_FINDING]}, REAL_KEY, mode)["plants"]["lint-config-missing"]

    assert result["hit"] is True
    assert result["tier_ok"] is True


def test_a_test_level_finding_that_mentions_pyproject_never_hits_lint_config_missing():
    found = hit_ids([finding("tests/test_tax.py", "test_progressive_tax", "P1", "Tooling",
                             "no pyproject, enable Ruff lint rules")])

    assert "lint-config-missing" not in found


def test_a_refactor_commit_finding_that_says_repository_hits_only_the_refactor_history_plant():
    found = hit_ids([finding("git history", None, "P1", "History",
                             "the repository history shows a refactor commit that had to edit tests")], "whole_suite")

    assert found == {"refactor-commit-edited-tests"}


UNPINNED_IDENTITY_FINDING = finding(
    "tests/test_reports.py", None, "P1", "missing-coverage",
    "Commit ed38f2c changed `_customer_name` from `customer.strip()` to the identity function, and no test changed. "
    "Invoices for ' acme' and 'acme' now produce two report rows where before they produced one, and no test pins "
    "either behaviour. test_report_customers mocks the function with `str`, so it hides the difference. A")
FIXTURE_COMMIT_DELETES_TESTS_FINDING = finding(
    "git history", None, "P3", "commit-hygiene",
    "Commit e9250f4 ('Resolve each customer once per monthly report') also quietly deletes "
    "tests/test_report_totals.py: a test of the private `_aggregate` and a mock of `_format_rows`. They were "
    "replaced by build_report tests, which is the right direction, but deleting tests belongs in its own commit "
    "that names the tests re")


@pytest.mark.parametrize("noisy", [UNPINNED_IDENTITY_FINDING, FIXTURE_COMMIT_DELETES_TESTS_FINDING],
                         ids=["identity-lookup", "deleted-report-totals"])
@pytest.mark.parametrize("mode", ["slice", "whole_suite"])
def test_comments_on_our_own_fixture_commits_are_known_noise_not_unkeyed(noisy, mode):
    report = grade.grade({"findings": [noisy]}, REAL_KEY, mode)

    assert report["known_noise_count"] == 1
    assert report["unkeyed"] == []


@pytest.mark.parametrize("realistic, expected_plant, expected_decoy", [
    (finding("git history", None, "P1", "History", "Refactor: rename rounding helper had to edit tests"),
     "refactor-commit-edited-tests", None),
    (finding("tests/test_report_customers.py", "test_customer_details_are_resolved_once_per_customer", "ARCH",
             "Hidden lookup", "patches the private _customer_name; inject the lookup"),
     "architecture-report-customer-lookup", None),
    (finding("billing/reports.py", None, "ARCH", "Hidden lookup", "_customer_name is hard-wired; inject the lookup"),
     "architecture-report-customer-lookup", None),
    (finding("tests/test_reports.py", None, "P2", "wrong level", "build_report tests are too broad, integration style"),
     None, "report-interface"),
], ids=["refactor-history", "lookup-test", "lookup-production", "report-interface-accusation"])
def test_noise_never_swallows_a_finding_that_should_hit_a_plant_or_decoy(realistic, expected_plant, expected_decoy):
    report = grade.grade({"findings": [realistic]}, REAL_KEY, "whole_suite")

    assert report["known_noise_count"] == 0
    hit = {pid for pid, p in report["plants"].items() if p["hit"]}
    false_positive = {did for did, d in report["decoys"].items() if d["false_positive"]}
    assert (hit, false_positive) == ({expected_plant} - {None}, {expected_decoy} - {None})

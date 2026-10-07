import json
import subprocess
import sys
from pathlib import Path

import pytest

import summarise


def report(plants, decoys=None, unkeyed=0, known_noise=0, mode="slice"):
    return {
        "mode": mode,
        "plants": {pid: {"hit": hit, "tier_ok": ok, "tiers_seen": []} for pid, (hit, ok) in plants.items()},
        "decoys": {did: {"false_positive": fp} for did, fp in (decoys or {}).items()},
        "unkeyed": [{}] * unkeyed,
        "known_noise_count": known_noise,
    }


def test_plant_hit_and_tier_ok_rates_are_fractions_of_reports():
    reports = [report({"a": (True, True)}), report({"a": (True, False)}),
               report({"a": (False, False)}), report({"a": (True, True)})]

    rates = summarise.summarise(reports)["plants"]["a"]

    assert rates == {"hit_rate": 0.75, "tier_ok_rate": 0.5}


def test_decoy_false_positive_rate_and_unkeyed_counts():
    reports = [report({}, {"d": True}, unkeyed=3, known_noise=1), report({}, {"d": False}, unkeyed=1)]

    summary = summarise.summarise(reports)

    assert summary["decoys"]["d"] == {"false_positive_rate": 0.5}
    assert summary["unkeyed"] == {"per_run": [3, 1], "mean": 2.0}
    assert summary["known_noise"] == {"per_run": [1, 0], "mean": 0.5}
    assert summary["runs"] == 2


def write_reports(tmp_path, reports):
    paths = []
    for index, one in enumerate(reports):
        path = tmp_path / f"r{index}.json"
        path.write_text(json.dumps(one))
        paths.append(str(path))
    return paths


def test_cli_reads_report_files_and_prints_json(tmp_path, capsys):
    paths = write_reports(tmp_path, [report({"a": (hit, hit)}) for hit in (True, False)])

    code = summarise.main(paths)

    assert code == 0
    assert json.loads(capsys.readouterr().out)["plants"]["a"]["hit_rate"] == 0.5


def test_summary_records_the_mode_of_its_reports():
    assert summarise.summarise([report({"a": (True, True)}, mode="whole_suite")])["mode"] == "whole_suite"


def test_mixed_modes_are_rejected():
    reports = [report({"a": (True, True)}, mode="slice"), report({"a": (True, True)}, mode="whole_suite")]

    with pytest.raises(summarise.InvalidReports, match="mixed modes"):
        summarise.summarise(reports)


def test_no_reports_is_rejected():
    with pytest.raises(summarise.InvalidReports, match="no reports"):
        summarise.summarise([])


def test_cli_exits_2_with_a_clear_message_on_empty_input_and_mixed_modes(tmp_path, capsys):
    mixed = write_reports(tmp_path, [report({}, mode="slice"), report({}, mode="whole_suite")])

    codes = [summarise.main([]), summarise.main(mixed)]

    assert codes == [2, 2]
    err = capsys.readouterr().err
    assert "no reports" in err and "mixed modes" in err


def test_running_summarise_py_as_a_script_wires_main(tmp_path):
    paths = write_reports(tmp_path, [report({"a": (True, True)})])
    script = Path(__file__).resolve().parent.parent / "summarise.py"

    completed = subprocess.run([sys.executable, str(script), *paths], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["runs"] == 1

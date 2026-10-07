import json
import subprocess
import sys
from pathlib import Path

import summarise


def report(plants, decoys=None, unkeyed=0, known_noise=0):
    return {
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


def test_cli_reads_report_files_and_prints_json(tmp_path):
    paths = []
    for index, hit in enumerate((True, False)):
        path = tmp_path / f"r{index}.json"
        path.write_text(json.dumps(report({"a": (hit, hit)})))
        paths.append(str(path))
    script = Path(__file__).resolve().parent.parent / "summarise.py"

    completed = subprocess.run([sys.executable, str(script), *paths], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["plants"]["a"]["hit_rate"] == 0.5

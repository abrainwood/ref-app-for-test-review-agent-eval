import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import prove

import prove

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "answer_key.json").read_text())
FIXTURE_SOURCE = os.environ.get("REF_APP_REPO", "https://github.com/abrainwood/ref-app-for-test-review-agent-eval.git")
DELIBERATELY_ABSENT = {"tests/test_calculator.py::test_divide_by_zero"}

pytestmark = pytest.mark.integration


def _run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="module")
def collected(tmp_path_factory):
    checkout = tmp_path_factory.mktemp("fixture")
    _run(["git", "clone", "--quiet", "--no-checkout", FIXTURE_SOURCE, str(checkout)], cwd=checkout.parent)
    _run(["git", "checkout", "--quiet", KEY["fixture_sha"]], cwd=checkout)
    listing = _run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=checkout)
    return {line for line in listing.splitlines() if "::" in line}


def key_targets():
    entries = KEY["plants"] + KEY["decoys"]
    targets = set()
    for entry in entries:
        if entry["test"] != "repo" and not entry["test"].startswith("git:"):
            targets.update(entry.get("tests", [entry["test"]]))
        for proof in prove.proofs_of(entry):
            targets.update(proof["expect"])
    return targets - DELIBERATELY_ABSENT


def exists_in(target, collected):
    return target in collected or any(nodeid.startswith(f"{target}::") for nodeid in collected)


def test_every_plant_decoy_and_proof_target_exists_in_the_fixture_at_the_pinned_sha(collected):
    missing = sorted(t for t in key_targets() if not exists_in(t, collected))

    assert missing == []


def test_the_deliberately_absent_target_is_really_absent(collected):
    assert not (DELIBERATELY_ABSENT & collected)

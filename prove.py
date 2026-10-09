import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ANSWER_KEY = Path(__file__).parent / "answer_key.json"
COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache")


OUTCOME_BY_EXIT_CODE = {0: "pass", 1: "fail", 2: "fail"}


class EditTargetMissing(Exception):
    pass


def pytest_outcome(workdir, target):
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
        cwd=workdir, capture_output=True, text=True,
    )
    return OUTCOME_BY_EXIT_CODE.get(completed.returncode, "error")


def apply_edits(workdir, edits):
    for edit in edits:
        path = workdir / edit["file"]
        text = path.read_text()
        if edit["find"] not in text:
            raise EditTargetMissing(f"{edit['file']}: {edit['find']!r}")
        path.write_text(text.replace(edit["find"], edit["replace"]))


def proofs_of(entry):
    proof = entry["proof"]
    if proof is None:
        return []
    return proof if isinstance(proof, list) else [proof]


def run_proof(fixture, proof):
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "fixture"
        shutil.copytree(fixture, workdir, ignore=COPY_IGNORE)
        apply_edits(workdir, proof["edits"])
        return [(target, wanted, pytest_outcome(workdir, target))
                for target, wanted in proof["expect"].items()]


def main(fixture):
    key = json.loads(ANSWER_KEY.read_text())
    mismatches = 0
    baseline = run_proof(fixture, {"edits": [], "expect": {"tests": "pass"}})
    for entry in [{"id": "baseline", "proof": None}] + key["plants"] + key["decoys"]:
        results = baseline if entry["id"] == "baseline" else [
            result for proof in proofs_of(entry) for result in run_proof(fixture, proof)]
        for target, wanted, got in results:
            verdict = "ok" if wanted == got else "MISMATCH"
            mismatches += verdict != "ok"
            print(f"{verdict:8} {entry['id']:36} {target} expected={wanted} got={got}")
    print(f"{mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve()))

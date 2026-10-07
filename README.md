# Answer key: ref-app test-review eval

This orphan branch holds the grading data for the fixture on `main`. Keep it off any clone handed to the agent under evaluation: clone the fixture with `git clone --single-branch --branch main`.

- `answer_key.json` - every planted defect (`plants`) and every legitimate pattern that must not be flagged (`decoys`), with the acceptable report tier per review mode:
  - `slice` - review of the diff since the commit titled `slice_base_subject`, with that commit as the base ref. Pre-existing plants should be `OBSERVED` or omitted.
  - `whole_suite` - review of the entire suite, including git history.
- `prove.py` - mechanical evidence for each claim. Each `proof` copies the fixture, applies edits, and runs the named tests:
  - `mutation` breaks behaviour. Lying plants must stay green; decoys must go red.
  - `refactor` preserves behaviour. Coupled plants must go red while the control tests stay green.
  - `isolation` runs the test alone.
  - Plants with `"proof": null` are style or hermeticity defects that no mutation can show; the `category` field states the defect.

Run: `python3 prove.py <path-to-fixture-checkout>` - exits non-zero on any mismatch or missing edit target. pytest exit codes 0 = pass, 1 and 2 (failures, collection errors from a rename) = fail; anything else (3, 4 no such target, 5 nothing collected) = error, which never matches an expectation.

The fixture's billing rules are in `SPEC.md` on `main`. The `pasted-expected-value` plant is a real per-line rounding bug that contradicts SPEC.md, and its test pins it.


## Harness-agnostic grading contract

Any agent, any harness:

1. Clone the fixture (`main`) at the pinned sha. Keep this branch out of that clone.
2. Take the section of `task_prompt.md` for the mode (`## Mode: slice` or `## Mode: whole_suite`) and fill the placeholders: `{base_ref}` (slice only - the commit titled `slice_base_subject`), `{schema_path}` (path to `findings.schema.json`, copied somewhere readable), `{findings_path}` (where the agent must write its JSON).
3. Run the reviewer on the fixture checkout and collect the findings JSON, shaped like `findings.schema.json`.
4. Grade it, after the run: `python3 grade.py findings.json --mode slice|whole_suite` prints a JSON report (per plant `hit`/`tier_ok`/`tiers_seen`, per decoy `false_positive`, `unkeyed`, `known_noise_count`, `summary`).
5. Aggregate repeated runs of one arm: `python3 summarise.py report1.json report2.json ...` prints per-plant hit and tier-ok rates, per-decoy false-positive rates, and unkeyed and near-miss counts per run. Compare arms yourself.

Matching rules (`grade.py`):

- Findings are normalised first: `./x`, absolute paths ending in the repo-relative path, `x.py:7` and backslashes all match `x.py`; `test_x()`, `file.py::test_x`, `Class::test_x` and `test_x[param]` all match `test_x`.
- Keywords match whole words/phrases, case-insensitively, in category + summary (`important` does not hit `import`, `FakeRates` does not hit `fake`). List inflections explicitly (`coupling`, `coupled`), never stems; the key lint rejects stems.
- plant `test` = `path::name` (or `tests`: a list of such nodeids for a defect spanning several tests): finding `file` is the path and finding `test` is the name. If the plant has `match_keywords`, one must also appear in the finding's category + summary. Optional `files` lists extra acceptable files (e.g. production placement); a finding there needs a keyword. A keyworded plant is also hit by a finding with `test: null` on its own file that carries a keyword.
- plant `test` = a file path: finding `file` equals it (or an extra `files` entry) and, if the plant has `match_keywords`, a keyword appears.
- plant `test` = `repo` or `git:...`: `files` anchors it (`pyproject.toml`/`ruff.toml`/`setup.cfg`/`repo`; `git history`/`git log`/`git`). Only findings with `"test": null` that name an anchor (as the `file`, or as a whole word in the summary, e.g. `file: "lint config"` with a summary naming `pyproject.toml`), with a keyword in category + summary, hit it. A test-level finding never hits it. The anchor makes broad keywords (`ruff`, `lint`, `refactor`, `rename`) safe.
- Most specific match wins: a finding feeds only the most specific level it matches (test, then file, then repo). A finding on a test-level plant never also feeds a file-level or repo-wide plant.
- Decoys use the same rules, and every decoy carries `match_keywords` naming the accusation that its lure is a defect (e.g. `asserts the call count` + `over-specified`, `should not fake`, `frozen`, `should not use caplog`). A finding on a decoy test is a false positive only if it accuses the lure; an unrelated valid point on that test (an unasserted URL, a missing no-sleep-after-last-attempt check, a duplicate, an opaque assertion) is a `near_misses` entry with no penalty. This reverses the earlier rule that any finding on a test-level decoy was a false positive: the smoke run showed such findings were valid, and penalising them punished good reviews. Keywords must stay discriminating: `tests/test_grade.py` runs the four real smoke findings (14, 15, 23, 25) against the key.
- A hit is tier-correct when the finding tier is accepted for the mode; with no hit, the plant passes only if `OMITTED` is accepted.
- Every plant and decoy in the report carries `matched`: the indexes (into the findings list) of the findings that matched it, so a mis-match is visible.
- `near_misses` (count in `summary.near_misses`): unkeyed findings that land on a keyed test, file or anchor but fail the keyword check, with the candidate plant/decoy ids. Read these before tuning keywords.
- Extra keys in a finding (e.g. `line`) are ignored with a WARNING; missing required keys or wrong types are rejected. `file: "x.py::test_x"` with `test: null` is read as file plus test.
- A finding matching no plant, decoy or `known_noise` entry is `unkeyed`. Triage each unkeyed finding:
  - a real defect nobody keyed -> add it as a plant;
  - harmless -> add it to `known_noise`;
  - it describes an existing plant but the matcher missed it -> fix the matcher or keywords of that plant, not a new plant.
- `tests/test_grade.py` lints the key: every plant's own category at its own target hits exactly that plant and no decoy; no keyword is a known stem or generic word. `tests/test_key_against_fixture.py` clones the fixture at `fixture_sha` (source: `$REF_APP_REPO` or GitHub) and asserts every plant, decoy and proof nodeid exists (`test_divide_by_zero` is commented out on purpose). Integration tests are marked `integration`; `-m 'not integration'` runs the fast set.

`canary/golden_smoke.slice.json` is the 38 findings of a real smoke run; `tests/test_golden.py` pins the hand-checked labels (no decoy false positives, which plants it hits and at what tier, which findings stay unkeyed).

`canary/` holds findings files that prove the grader discriminates: `perfect_findings.<mode>.json` must score every plant tier-ok with no false positives or unkeyed findings; `known_bad_findings.json` must not. Both are checked by `tests/` (`python3 -m pytest tests`).

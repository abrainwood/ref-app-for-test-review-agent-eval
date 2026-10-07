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

Run: `python3 prove.py <path-to-fixture-checkout>` - exits non-zero on any mismatch or missing edit target.

The fixture's billing rules are in `SPEC.md` on `main`. The `pasted-expected-value` plant is a real per-line rounding bug that contradicts SPEC.md, and its test pins it.


## Harness-agnostic grading contract

Any agent, any harness:

1. Clone the fixture (`main`) at the pinned sha. Keep this branch out of that clone.
2. Take the section of `task_prompt.md` for the mode (`## Mode: slice` or `## Mode: whole_suite`) and fill the placeholders: `{base_ref}` (slice only - the commit titled `slice_base_subject`), `{schema_path}` (path to `findings.schema.json`, copied somewhere readable), `{findings_path}` (where the agent must write its JSON).
3. Run the reviewer on the fixture checkout and collect the findings JSON, shaped like `findings.schema.json`.
4. Grade it, after the run: `python3 grade.py findings.json --mode slice|whole_suite` prints a JSON report (per plant `hit`/`tier_ok`/`tiers_seen`, per decoy `false_positive`, `unkeyed`, `known_noise_count`, `summary`).
5. Aggregate repeated runs of one arm: `python3 summarise.py report1.json report2.json ...` prints per-plant hit and tier-ok rates, per-decoy false-positive rates and unkeyed counts. Compare arms yourself.

Matching rules (`grade.py`):

- Findings are normalised first: `./x`, absolute paths ending in the repo-relative path, `x.py:7` and backslashes all match `x.py`; `test_x()`, `file.py::test_x`, `Class::test_x` and `test_x[param]` all match `test_x`.
- plant `test` = `path::name` (or `tests`: a list of such nodeids for a defect spanning several tests): finding `file` is the path and finding `test` is the name. If the plant has `match_keywords`, one must also appear (case-insensitive) in the finding's category + summary. Optional `files` lists extra acceptable files (e.g. production placement); a finding there needs a keyword.
- plant `test` = a file path: finding `file` equals it (or an extra `files` entry) and, if the plant has `match_keywords`, a keyword appears.
- plant `test` = `repo` or `git:...`: only findings with `"test": null`, with a keyword in category + summary. Keywords are specific phrases, not generic words like "history" or "ruff".
- Most specific match wins: a finding feeds only the most specific level it matches (test, then file, then repo). A finding on a test-level plant never also feeds a file-level or repo-wide plant.
- Decoys use the same rules; `match_keywords` name the wrong accusation, so a legitimate finding elsewhere in a decoy's file is not a false positive. A match is a false positive.
- A hit is tier-correct when the finding tier is accepted for the mode; with no hit, the plant passes only if `OMITTED` is accepted.
- Every plant and decoy in the report carries `matched`: the indexes (into the findings list) of the findings that matched it, so a mis-match is visible.
- A finding matching no plant, decoy or `known_noise` entry is `unkeyed`. Triage each unkeyed finding:
  - a real defect nobody keyed -> add it as a plant;
  - harmless -> add it to `known_noise`;
  - it describes an existing plant but the matcher missed it -> fix the matcher or keywords of that plant, not a new plant.
- `tests/test_grade.py` lints the key: every plant's own category at its own target hits exactly that plant and no decoy.

`canary/` holds findings files that prove the grader discriminates: `perfect_findings.<mode>.json` must score every plant tier-ok with no false positives or unkeyed findings; `known_bad_findings.json` must not. Both are checked by `tests/` (`python3 -m pytest tests`).

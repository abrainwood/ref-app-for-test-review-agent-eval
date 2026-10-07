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

- plant `test` = `path::name`: finding `file` equals `path` and finding `test` equals `name` (or the full nodeid).
- plant `test` = a file path: finding `file` equals it and, if the plant has `match_keywords`, any keyword appears (case-insensitive) in the finding's category + summary.
- plant `test` = `repo` or `git:...`: any finding whose category + summary contains a `match_keywords` entry.
- A hit is tier-correct when the finding tier is accepted for the mode; with no hit, the plant passes only if `OMITTED` is accepted.
- Decoys match by the same rules (no keywords for file-level decoys); a match is a false positive.
- A finding matching no plant, decoy or `known_noise` entry is `unkeyed`. Triage each: add it as a plant (a real defect) or to `known_noise` (counted, not a defect).

`canary/` holds findings files that prove the grader discriminates: `perfect_findings.<mode>.json` must score every plant tier-ok with no false positives or unkeyed findings; `known_bad_findings.json` must not. Both are checked by `tests/` (`python3 -m pytest tests`).

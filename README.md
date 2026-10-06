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

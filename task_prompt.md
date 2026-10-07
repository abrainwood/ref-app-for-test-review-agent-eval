<!-- Each mode is a self-contained prompt under a "## Mode: <name>" heading. Give the harness only the section for its mode, with {placeholders} filled in. -->

## Mode: slice

Review the tests changed in the current git repository since `{base_ref}`.

Scope: the test files and test functions added or modified between `{base_ref}` and HEAD (`git diff {base_ref}..HEAD`). There is no brief and no list of seams for this change - work out what the change does from the diff and the code it touches. Tests outside the diff are out of scope, but if you notice a serious problem there, report it as OBSERVED.

For every finding, say which test (or file, or the repository as a whole) it concerns, how serious it is, and why.

Also write your findings as JSON matching the schema in `{schema_path}` to `{findings_path}`. Use these tiers:

- P0: a test that lies - it passes when the behaviour is broken
- P1: an anti-pattern or in-slice coupling that should be fixed
- P2: tested at the wrong level - move it down to a unit test or up to the public interface
- P3: cleanup
- ARCH: an architecture problem that tests cannot fix on their own
- OBSERVED: a pre-existing problem outside the change

Use `"test": null` for findings about a whole file or the repository, and set `file` to the most relevant path (or a short label such as `git history` for history-level findings).

Format rules for the JSON: `file` is a repo-relative path such as `tests/test_x.py` (no leading `./`, no absolute path, no line number). `test` is the bare test function name such as `test_x` (no `()`, no `file::` prefix, no parameter suffix), or `null`. Write one finding per defect. Report defects only - no positive notes about things that are fine.

## Mode: whole_suite

Review the entire test suite of the current git repository, including how the tests came to be: read the git history as well as the current files.

There is no brief and no list of seams - work out what the code does from the code itself and the tests that exercise it.

For every finding, say which test (or file, or the repository as a whole) it concerns, how serious it is, and why.

Also write your findings as JSON matching the schema in `{schema_path}` to `{findings_path}`. Use these tiers:

- P0: a test that lies - it passes when the behaviour is broken
- P1: an anti-pattern or coupling that should be fixed
- P2: tested at the wrong level - move it down to a unit test or up to the public interface
- P3: cleanup
- ARCH: an architecture problem that tests cannot fix on their own
- OBSERVED: a problem you noticed that is not worth acting on

Use `"test": null` for findings about a whole file or the repository, and set `file` to the most relevant path (or a short label such as `git history` for history-level findings).

Format rules for the JSON: `file` is a repo-relative path such as `tests/test_x.py` (no leading `./`, no absolute path, no line number). `test` is the bare test function name such as `test_x` (no `()`, no `file::` prefix, no parameter suffix), or `null`. Write one finding per defect. Report defects only - no positive notes about things that are fine.

# ref-app-for-test-review-agent-eval

A deliberately flawed reference app for evaluating test-review agents.

`calculator.py` + `cli.py` implement a trivial calculator. The pytest suite in
`tests/` is green but contains planted anti-patterns and "lying" tests —
assertions that stay green when the implementation is broken (degenerate
operands, tautologies, order-dependent shared state, mock-the-code-under-test,
substring output checks, a commented-out edge-case test, an unjustified skip).

Point an agent at the suite and ask it to review test quality and maturity.
What it catches, what it misses, and whether it *proves* its claims (e.g. via
mutation testing) is the eval signal.

Run the suite: `python3 -m pytest tests -q`

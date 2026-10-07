import pytest

import prove

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("body, target, outcome", [
    ("def test_ok():\n    assert True\n", "test_a.py", "pass"),
    ("def test_bad():\n    assert False\n", "test_a.py", "fail"),
    ("from nowhere import gone\n\ndef test_ok():\n    assert True\n", "test_a.py", "fail"),
    ("def test_ok():\n    assert True\n", "test_missing.py", "error"),
    ("x = 1\n", "test_a.py", "error"),
    ("def test_ok():\n    assert True\n", "test_a.py::test_no_such_test", "error"),
])
def test_pytest_exit_codes_other_than_pass_and_fail_are_errors_not_fails(tmp_path, body, target, outcome):
    (tmp_path / "test_a.py").write_text(body)

    assert prove.pytest_outcome(tmp_path, target) == outcome

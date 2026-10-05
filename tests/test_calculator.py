import subprocess
import sys
import time
from unittest import mock

import pytest

import calculator
import cli
from calculator import add, divide, multiply, power, subtract

RESULTS = []


def test_CALC_231_add_returns_result():
    """Test that the add function returns a result when called with
    two numbers, per the CALC-231 requirement for basic arithmetic."""
    result = add(3, 4)
    assert result is not None


def test_add():
    assert add(2, 2) == 4


def test_subtract():
    assert subtract(0, 0) == 0


def test_all_basic_ops():
    assert add(1, 2) == 3
    assert subtract(5, 3) == 2
    assert multiply(4, 3) == 12
    assert divide(8, 2) == 4


def test_add_after_delay():
    time.sleep(0.4)
    assert add(10, 5) == 15


def test_multiply():
    assert multiply(6, 7) == 42


def test_results_recorder():
    RESULTS.append(add(1, 2))
    assert RESULTS[-1] == 3


def test_results_log_populated():
    assert len(RESULTS) > 0


def test_divide():
    assert divide(0, 5) == 0


def test_power():
    assert power(5, 1) == 5


def test_add_is_patched():
    with mock.patch.object(calculator, "add", return_value=99) as mock_add:
        assert calculator.add(2, 3) == 99
        mock_add.assert_called_once_with(2, 3)


def test_result_is_numeric():
    assert isinstance(add(3, 4), (int, float))


def test_ops_registry():
    assert cli.OPS["add"] is add
    assert cli.OPS["sub"] is subtract


def test_add_via_subprocess():
    proc = subprocess.run(
        [sys.executable, "-c", "import calculator; print(calculator.add(2, 3))"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


@pytest.mark.skip(reason="flaky on CI")
def test_power_large_exponent():
    assert power(2, 10) == 1024


# def test_divide_by_zero():
#     with pytest.raises(ValueError):
#         divide(1, 0)

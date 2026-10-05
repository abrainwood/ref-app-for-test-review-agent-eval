import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "cli.py", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_e2e_add():
    proc = run_cli("add", "1", "2")
    assert "3.0" in proc.stdout


def test_e2e_sub():
    proc = run_cli("sub", "10", "4")
    assert "6.0" in proc.stdout


def test_e2e_mul():
    proc = run_cli("mul", "3", "3")
    assert "9.0" in proc.stdout


def test_e2e_div_produces_output():
    proc = run_cli("div", "8", "2")
    assert proc.stdout.strip() != ""


def test_e2e_exit_code():
    proc = run_cli("add", "5", "5")
    assert proc.returncode == 0


def test_e2e_usage_error():
    proc = run_cli()
    assert proc.returncode == 2
    assert "usage" in proc.stderr.lower()

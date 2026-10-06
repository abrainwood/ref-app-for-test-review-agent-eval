import io
import json
import logging
import urllib.error

import pytest

from rates.client import ExchangeRateClient, RateUnavailable

BASE_URL = "https://rates.example.test"


def http_error(status):
    return urllib.error.HTTPError(f"{BASE_URL}/rates/EUR", status, "error", {}, None)


class ScriptedOpener:
    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, url, timeout):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(json.dumps({"rate": outcome}).encode())


def client_with(opener, sleeps=None, max_attempts=3):
    return ExchangeRateClient(BASE_URL, max_attempts=max_attempts, opener=opener,
                              sleep=(sleeps if sleeps is not None else []).append)


def test_returns_rate_from_response():
    assert client_with(ScriptedOpener(0.92)).rate("EUR") == 0.92


def test_retries_transient_failures_until_success():
    opener = ScriptedOpener(http_error(503), http_error(429), 0.92)
    assert client_with(opener).rate("EUR") == 0.92


def test_gives_up_after_max_attempts():
    opener = ScriptedOpener(http_error(503), http_error(503), http_error(503), 0.92)
    with pytest.raises(RateUnavailable, match="status=503"):
        client_with(opener).rate("EUR")
    assert opener.calls == 3


def test_backoff_doubles_between_attempts():
    sleeps = []
    opener = ScriptedOpener(http_error(500), http_error(500), http_error(500), 0.92)
    client_with(opener, sleeps, max_attempts=4).rate("EUR")
    assert sleeps == [0.5, 1.0, 2.0]


def test_client_error_is_not_retried():
    opener = ScriptedOpener(http_error(404), 0.92)
    with pytest.raises(RateUnavailable, match="status=404"):
        client_with(opener).rate("EUR")
    assert opener.calls == 1


def test_exhausted_retries_log_a_warning_with_status_and_url(caplog):
    opener = ScriptedOpener(http_error(502), http_error(502), http_error(502))
    with caplog.at_level(logging.WARNING, logger="rates.client"), pytest.raises(RateUnavailable):
        client_with(opener).rate("EUR")
    assert [(r.levelno, "status=502" in r.getMessage(), f"{BASE_URL}/rates/EUR" in r.getMessage())
            for r in caplog.records] == [(logging.WARNING, True, True)]

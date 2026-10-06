import json
import logging
import time
import urllib.error
import urllib.request

LOGGER = logging.getLogger(__name__)
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
REQUEST_TIMEOUT_SECONDS = 5


class RateUnavailable(Exception):
    pass


class ExchangeRateClient:
    def __init__(self, base_url, max_attempts=3, backoff_seconds=0.5,
                 opener=urllib.request.urlopen, sleep=time.sleep):
        self._base_url = base_url
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._opener = opener
        self._sleep = sleep

    def rate(self, currency):
        url = f"{self._base_url}/rates/{currency}"
        status = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with self._opener(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    return float(json.load(response)["rate"])
            except urllib.error.HTTPError as error:
                if error.code not in RETRYABLE_STATUSES:
                    raise RateUnavailable(f"status={error.code} url={url}") from error
                status = error.code
            if attempt < self._max_attempts:
                self._sleep(self._backoff_seconds * 2 ** (attempt - 1))
        LOGGER.warning("exchange rate unavailable after %d attempts: status=%s url=%s",
                       self._max_attempts, status, url)
        raise RateUnavailable(f"status={status} url={url}")

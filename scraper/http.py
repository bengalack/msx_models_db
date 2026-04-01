"""HTTP helpers for the scraper."""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

_RETRY_CODES = (502, 503)
_MAX_RETRIES = 5
_RETRY_DELAY = 2.0


def fetch_with_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: int = 30,
) -> requests.Response:
    """GET *url*, retrying on 502/503 up to 5 times with a 2-second delay.

    Raises ``requests.HTTPError`` if the final attempt still returns an error
    status, or on any other non-retryable HTTP error code.
    """
    resp: requests.Response | None = None
    for attempt in range(_MAX_RETRIES + 1):
        resp = session.get(url, timeout=timeout)
        if resp.status_code in _RETRY_CODES and attempt < _MAX_RETRIES:
            log.warning(
                "HTTP %d for %s — retrying in %.0fs (attempt %d/%d)",
                resp.status_code,
                url,
                _RETRY_DELAY,
                attempt + 1,
                _MAX_RETRIES,
            )
            time.sleep(_RETRY_DELAY)
            continue
        resp.raise_for_status()
        return resp
    # Final attempt exhausted — raise on the last response.
    assert resp is not None
    resp.raise_for_status()
    return resp  # pragma: no cover

"""Tests for scraper.http — fetch_with_retry behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
import requests

from scraper.http import _MAX_RETRIES, _RETRY_DELAY, fetch_with_retry


def _make_response(status_code: int) -> MagicMock:
    """Return a mock requests.Response with the given status code."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if status_code < 400:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.HTTPError(
            response=resp,
        )
    return resp


URL = "https://example.com/resource"


# ── Success (no retries needed) ──────────────────────────────────────────────


class TestSuccess:

    def test_200_returns_response(self):
        session = MagicMock()
        session.get.return_value = _make_response(200)

        resp = fetch_with_retry(session, URL)

        assert resp.status_code == 200
        session.get.assert_called_once_with(URL, timeout=30)

    def test_passes_timeout_kwarg(self):
        session = MagicMock()
        session.get.return_value = _make_response(200)

        fetch_with_retry(session, URL, timeout=10)

        session.get.assert_called_once_with(URL, timeout=10)


# ── Retry on 502 / 503 ────────────────────────────────────────────────────────


class TestRetry:

    @patch("scraper.http.time.sleep")
    def test_retries_on_502_then_succeeds(self, mock_sleep):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(502),
            _make_response(200),
        ]

        resp = fetch_with_retry(session, URL)

        assert resp.status_code == 200
        assert session.get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_DELAY)

    @patch("scraper.http.time.sleep")
    def test_retries_on_503_then_succeeds(self, mock_sleep):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(503),
            _make_response(200),
        ]

        resp = fetch_with_retry(session, URL)

        assert resp.status_code == 200
        assert session.get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_DELAY)

    @patch("scraper.http.time.sleep")
    def test_retries_up_to_max_retries_then_raises(self, mock_sleep):
        session = MagicMock()
        # All attempts return 502.
        session.get.side_effect = [_make_response(502)] * (_MAX_RETRIES + 1)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, URL)

        assert session.get.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES

    @patch("scraper.http.time.sleep")
    def test_sleep_uses_correct_delay(self, mock_sleep):
        session = MagicMock()
        session.get.side_effect = [
            _make_response(503),
            _make_response(503),
            _make_response(200),
        ]

        fetch_with_retry(session, URL)

        mock_sleep.assert_called_with(_RETRY_DELAY)
        assert mock_sleep.call_count == 2

    @patch("scraper.http.time.sleep")
    def test_retry_warning_logged(self, mock_sleep, caplog):
        import logging

        session = MagicMock()
        session.get.side_effect = [
            _make_response(502),
            _make_response(200),
        ]

        with caplog.at_level(logging.WARNING, logger="scraper.http"):
            fetch_with_retry(session, URL)

        assert len(caplog.records) == 1
        assert "502" in caplog.records[0].message
        assert caplog.records[0].levelname == "WARNING"

    @patch("scraper.http.time.sleep")
    def test_all_retries_log_warnings(self, mock_sleep, caplog):
        import logging

        session = MagicMock()
        session.get.side_effect = [_make_response(503)] * (_MAX_RETRIES + 1)

        with caplog.at_level(logging.WARNING, logger="scraper.http"):
            with pytest.raises(requests.HTTPError):
                fetch_with_retry(session, URL)

        assert len(caplog.records) == _MAX_RETRIES

    @patch("scraper.http.time.sleep")
    def test_succeeds_on_last_retry(self, mock_sleep):
        """Succeeds on the final allowed attempt (attempt index == _MAX_RETRIES)."""
        session = MagicMock()
        session.get.side_effect = (
            [_make_response(502)] * _MAX_RETRIES + [_make_response(200)]
        )

        resp = fetch_with_retry(session, URL)

        assert resp.status_code == 200
        assert session.get.call_count == _MAX_RETRIES + 1


# ── Non-retryable errors ─────────────────────────────────────────────────────


class TestNonRetryable:

    @patch("scraper.http.time.sleep")
    def test_404_raises_immediately_no_retry(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(404)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, URL)

        session.get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("scraper.http.time.sleep")
    def test_500_raises_immediately_no_retry(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(500)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, URL)

        session.get.assert_called_once()
        mock_sleep.assert_not_called()

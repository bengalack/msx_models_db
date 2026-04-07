"""Unit tests for scraper/msxorg.py — graceful error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from scraper.msxorg import fetch_all, list_model_pages


class TestListModelPagesGraceful:
    """Category page fetch failures are logged and skipped; other categories continue."""

    def test_single_category_403_returns_empty(self):
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        pages = list_model_pages(session, delay=0)
        assert pages == []

    def test_partial_category_failure_still_returns_others(self):
        """If one category fails, pages from successful ones are still returned."""
        good_html = (
            b"<html><body>"
            b'<div id="mw-pages"><a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a></div>'
            b"</body></html>"
        )
        good_resp = MagicMock()
        good_resp.content = good_html
        good_resp.raise_for_status = MagicMock()

        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = Exception("403 Forbidden")

        # Three categories; first fails, second succeeds, third fails
        session = MagicMock()
        session.get.side_effect = [bad_resp, good_resp, bad_resp]

        pages = list_model_pages(session, delay=0)
        # At least the one good page was collected
        assert len(pages) >= 1
        assert any(p["title"] == "Sony HB-75P" for p in pages)


class TestFetchAllGraceful:
    """fetch_all returns [] (not raises) when list_model_pages fails entirely."""

    def test_network_error_returns_empty_not_raises(self):
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        models = fetch_all(session=session, delay=0)
        assert models == []

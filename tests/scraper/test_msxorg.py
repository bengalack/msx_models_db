"""Unit tests for scraper/msxorg.py — graceful error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from scraper.mirror import MirrorPageSource
from scraper.msxorg import fetch_all, list_model_pages


_GOOD_CATEGORY_HTML = (
    b"<html><body>"
    b'<div id="mw-pages"><a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a></div>'
    b"</body></html>"
)

_GOOD_MODEL_HTML = b"""
<html><body>
<table class="wikitable">
  <tr><th>Brand</th><td>Sony</td></tr>
  <tr><th>Model</th><td>HB-75P</td></tr>
  <tr><th>Year</th><td>1985</td></tr>
  <tr><th>Region</th><td>Europe</td></tr>
</table>
</body></html>
"""


class _StubSource:
    """Minimal PageSource stub for testing list_model_pages."""

    def __init__(self, category_results: list[bytes | None]):
        self._cats = iter(category_results)

    def fetch_category(self, standard: str, url: str) -> bytes | None:
        return next(self._cats, None)

    def fetch_page(self, title: str, url: str) -> bytes | None:  # pragma: no cover
        return None


class TestListModelPagesGraceful:
    """Category page fetch failures are logged and skipped; other categories continue."""

    def test_single_category_none_returns_empty(self):
        # All categories return None (e.g. 403 on live, or missing file in mirror)
        source = _StubSource([None, None, None])
        pages = list_model_pages(source, delay=0)
        assert pages == []

    def test_partial_category_failure_still_returns_others(self):
        """If one category returns None, pages from successful ones are still returned."""
        # Three categories: first fails, second succeeds, third fails
        source = _StubSource([None, _GOOD_CATEGORY_HTML, None])
        pages = list_model_pages(source, delay=0)
        assert len(pages) >= 1
        assert any(p["title"] == "Sony HB-75P" for p in pages)


class TestFetchAllGraceful:
    """fetch_all with a LivePageSource that errors returns [] gracefully."""

    def test_network_error_returns_empty_not_raises(self):
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        models = fetch_all(session=session, delay=0)
        assert models == []


# ---------------------------------------------------------------------------
# MirrorPageSource integration with fetch_all
# ---------------------------------------------------------------------------

class TestFetchAllWithMirror:
    """fetch_all reads from a local MirrorPageSource."""

    _CATEGORY_HTML = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
        b"</div></body></html>"
    )
    _MODEL_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sony</td></tr>
      <tr><th>Model</th><td>HB-75P</td></tr>
      <tr><th>Year</th><td>1985</td></tr>
      <tr><th>Region</th><td>Europe</td></tr>
    </table></body></html>
    """

    def test_reads_models_from_mirror(self, tmp_path):
        # Write category and model files using the expected filename convention
        (tmp_path / "Category_MSX2 Computers - MSX Wiki.html").write_bytes(self._CATEGORY_HTML)
        (tmp_path / "Category_MSX2+ Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX turbo R Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._MODEL_HTML)

        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert len(models) == 1
        assert models[0]["manufacturer"] == "Sony"

    def test_missing_category_file_skipped(self, tmp_path):
        # No category files written at all → zero models, no exception
        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert models == []

    def test_missing_model_file_skipped(self, tmp_path):
        # Category present, model file absent → skip that model
        (tmp_path / "Category_MSX2 Computers - MSX Wiki.html").write_bytes(self._CATEGORY_HTML)
        (tmp_path / "Category_MSX2+ Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX turbo R Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        # Model file deliberately not written

        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert models == []

    def test_no_http_calls_with_mirror(self, tmp_path, monkeypatch):
        """No requests.Session.get calls are made when using a MirrorPageSource."""
        import requests
        original_get = requests.Session.get

        def should_not_be_called(*args, **kwargs):
            raise AssertionError("HTTP request made during mirror mode")

        monkeypatch.setattr(requests.Session, "get", should_not_be_called)
        source = MirrorPageSource(tmp_path)
        fetch_all(source=source, delay=0)  # no exception = no HTTP calls

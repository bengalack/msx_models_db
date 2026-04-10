"""Unit tests for scraper/msxorg.py — graceful error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from scraper.mirror import MirrorPageSource
from scraper.msxorg import _parse_vdp, fetch_all, list_model_pages, parse_model_page


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


# ---------------------------------------------------------------------------
# _parse_vdp — pick highest when multiple VDPs listed
# ---------------------------------------------------------------------------

class TestParseVdp:
    def test_single_v9938(self):
        assert _parse_vdp("Yamaha V9938") == "V9938"

    def test_single_v9958(self):
        assert _parse_vdp("Yamaha V9958") == "V9958"

    def test_multiple_picks_highest(self):
        assert _parse_vdp("V9938 / V9958") == "V9958"

    def test_multiple_reversed_order_still_picks_highest(self):
        assert _parse_vdp("V9958 / V9938") == "V9958"

    def test_tms_is_lowest(self):
        assert _parse_vdp("TMS9918A / V9938") == "V9938"

    def test_no_match_returns_none(self):
        assert _parse_vdp("no vdp here") is None


# ---------------------------------------------------------------------------
# list_model_pages — pick highest generation for multi-category models
# ---------------------------------------------------------------------------

class TestListModelPagesHighestGeneration:
    """A model in multiple categories gets the highest generation standard."""

    _MSX2_CAT = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/1chipMSX" title="1chipMSX">1chipMSX</a>'
        b"</div></body></html>"
    )
    _MSX2PLUS_CAT = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/1chipMSX" title="1chipMSX">1chipMSX</a>'
        b"</div></body></html>"
    )
    _EMPTY_CAT = b"<html><body><div id='mw-pages'></div></body></html>"

    def test_model_in_both_msx2_and_msx2plus_gets_msx2plus(self):
        # MSX2 category first, then MSX2+ — model should end up as MSX2+
        source = _StubSource([self._MSX2_CAT, self._MSX2PLUS_CAT, self._EMPTY_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX2+"

    def test_model_only_in_msx2_stays_msx2(self):
        source = _StubSource([self._MSX2_CAT, self._EMPTY_CAT, self._EMPTY_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX2"

    def test_model_only_in_turbor_gets_turbor(self):
        source = _StubSource([self._EMPTY_CAT, self._EMPTY_CAT, self._MSX2_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "turbo R"


# ---------------------------------------------------------------------------
# parse_model_page — split combined models on " / "
# ---------------------------------------------------------------------------

class TestParseModelPageSplit:
    """Model field with ' / ' produces one entry per variant."""

    _COMBINED_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sakhr</td></tr>
      <tr><th>Model</th><td>AX-350II / AX-350IIF</td></tr>
      <tr><th>Year</th><td>1987</td></tr>
    </table></body></html>
    """
    _SINGLE_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sony</td></tr>
      <tr><th>Model</th><td>HB-75P</td></tr>
    </table></body></html>
    """

    def test_combined_model_splits_into_two(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert len(results) == 2
        assert results[0]["model"] == "AX-350II"
        assert results[1]["model"] == "AX-350IIF"

    def test_split_entries_share_manufacturer(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert all(r["manufacturer"] == "Sakhr" for r in results)

    def test_split_entries_share_fields(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert all(r["year"] == 1987 for r in results)
        assert all(r["generation"] == "MSX2" for r in results)

    def test_single_model_returns_one_entry(self):
        results = parse_model_page(self._SINGLE_HTML, "MSX2", "Sony HB-75P")
        assert len(results) == 1
        assert results[0]["model"] == "HB-75P"

    def test_triple_split(self):
        html = b"""
        <html><body><table class="wikitable">
          <tr><th>Brand</th><td>Sanyo</td></tr>
          <tr><th>Model</th><td>PHC-23J / PHC-23J(B) / PHC-23(GR)</td></tr>
        </table></body></html>
        """
        results = parse_model_page(html, "MSX2", "Sanyo PHC-23J")
        assert len(results) == 3
        assert [r["model"] for r in results] == ["PHC-23J", "PHC-23J(B)", "PHC-23(GR)"]

    def test_no_specs_table_returns_empty(self):
        html = b"<html><body><p>No table here.</p></body></html>"
        results = parse_model_page(html, "MSX2", "Missing")
        assert results == []


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

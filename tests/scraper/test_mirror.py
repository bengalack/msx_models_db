"""Unit tests for scraper/mirror.py — PageSource implementations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scraper.mirror import FallbackPageSource, LivePageSource, MirrorPageSource, slug_to_filename as _slug_to_filename


# ---------------------------------------------------------------------------
# _slug_to_filename
# ---------------------------------------------------------------------------

class TestSlugToFilename:
    def test_model_page(self):
        assert _slug_to_filename("https://www.msx.org/wiki/Sony_HB-F9S") == \
            "Sony HB-F9S - MSX Wiki.html"

    def test_category_page(self):
        assert _slug_to_filename("https://www.msx.org/wiki/Category:MSX2_Computers") == \
            "Category_MSX2 Computers - MSX Wiki.html"

    def test_percent_encoded_plus(self):
        assert _slug_to_filename("https://www.msx.org/wiki/CIEL_Expert_2%2B_Turbo") == \
            "CIEL Expert 2+ Turbo - MSX Wiki.html"

    def test_msx2plus_category(self):
        assert _slug_to_filename("https://www.msx.org/wiki/Category:MSX2%2B_Computers") == \
            "Category_MSX2+ Computers - MSX Wiki.html"

    def test_turbo_r_category(self):
        assert _slug_to_filename("https://www.msx.org/wiki/Category:MSX_turbo_R_Computers") == \
            "Category_MSX turbo R Computers - MSX Wiki.html"

    def test_simple_slug_no_underscores(self):
        assert _slug_to_filename("https://www.msx.org/wiki/MSX2") == \
            "MSX2 - MSX Wiki.html"


# ---------------------------------------------------------------------------
# MirrorPageSource
# ---------------------------------------------------------------------------

class TestMirrorPageSource:
    def test_fetch_category_returns_bytes_when_present(self, tmp_path):
        fname = "Category_MSX2 Computers - MSX Wiki.html"
        (tmp_path / fname).write_bytes(b"<html>cat</html>")
        src = MirrorPageSource(tmp_path)
        result = src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers")
        assert result == b"<html>cat</html>"

    def test_fetch_category_returns_none_when_missing(self, tmp_path):
        src = MirrorPageSource(tmp_path)
        result = src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers")
        assert result is None

    def test_fetch_page_returns_bytes_when_present(self, tmp_path):
        (tmp_path / "Sony HB-F9S - MSX Wiki.html").write_bytes(b"<html>model</html>")
        src = MirrorPageSource(tmp_path)
        result = src.fetch_page("Sony HB-F9S", "https://www.msx.org/wiki/Sony_HB-F9S")
        assert result == b"<html>model</html>"

    def test_fetch_page_returns_none_when_missing(self, tmp_path):
        src = MirrorPageSource(tmp_path)
        result = src.fetch_page("Sony HB-F9S", "https://www.msx.org/wiki/Sony_HB-F9S")
        assert result is None

    def test_nonexistent_dir_returns_none_not_raises(self, tmp_path):
        src = MirrorPageSource(tmp_path / "does_not_exist")
        assert src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers") is None
        assert src.fetch_page("Sony HB-F9S", "https://www.msx.org/wiki/Sony_HB-F9S") is None

    def test_fetch_category_warns_on_missing_file(self, tmp_path, caplog):
        import logging
        src = MirrorPageSource(tmp_path)
        with caplog.at_level(logging.WARNING, logger="scraper.mirror"):
            src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers")
        assert any("Mirror file not found" in r.message for r in caplog.records)

    def test_fetch_page_warns_on_missing_file(self, tmp_path, caplog):
        import logging
        src = MirrorPageSource(tmp_path)
        with caplog.at_level(logging.WARNING, logger="scraper.mirror"):
            src.fetch_page("Sony HB-F9S", "https://www.msx.org/wiki/Sony_HB-F9S")
        assert any("Mirror file not found" in r.message for r in caplog.records)

    def test_nonexistent_dir_logs_error(self, tmp_path, caplog):
        import logging
        with caplog.at_level(logging.ERROR, logger="scraper.mirror"):
            MirrorPageSource(tmp_path / "does_not_exist")
        assert any("Mirror directory not found" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# LivePageSource
# ---------------------------------------------------------------------------

class TestLivePageSource:
    def test_fetch_category_returns_content_on_success(self):
        session = MagicMock()
        resp = MagicMock()
        resp.content = b"<html>ok</html>"
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp
        src = LivePageSource(session)
        result = src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers")
        assert result == b"<html>ok</html>"

    def test_fetch_category_returns_none_on_http_error(self):
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        src = LivePageSource(session)
        result = src.fetch_category("MSX2", "https://www.msx.org/wiki/Category:MSX2_Computers")
        assert result is None

    def test_fetch_page_returns_none_on_http_error(self):
        session = MagicMock()
        session.get.side_effect = Exception("503 Service Unavailable")
        src = LivePageSource(session)
        result = src.fetch_page("Sony HB-F9S", "https://www.msx.org/wiki/Sony_HB-F9S")
        assert result is None


# ---------------------------------------------------------------------------
# FallbackPageSource
# ---------------------------------------------------------------------------

class TestFallbackPageSource:
    _CAT_URL = "https://www.msx.org/wiki/Category:MSX2_Computers"
    _PAGE_URL = "https://www.msx.org/wiki/Sony_HB-F9S"

    def _live(self, category_result, page_result=None):
        src = MagicMock(spec=LivePageSource)
        src.fetch_category.return_value = category_result
        src.fetch_page.return_value = page_result
        return src

    def _mirror(self, category_result, page_result=None):
        src = MagicMock(spec=MirrorPageSource)
        src.fetch_category.return_value = category_result
        src.fetch_page.return_value = page_result
        return src

    def test_returns_live_content_when_live_succeeds(self):
        live = self._live(b"live-cat", b"live-page")
        mirror = self._mirror(b"mirror-cat", b"mirror-page")
        src = FallbackPageSource(live, mirror)
        assert src.fetch_category("MSX2", self._CAT_URL) == b"live-cat"
        assert src.fetch_page("Sony HB-F9S", self._PAGE_URL) == b"live-page"
        mirror.fetch_category.assert_not_called()
        mirror.fetch_page.assert_not_called()

    def test_falls_back_to_mirror_when_live_category_fails(self):
        live = self._live(None)
        mirror = self._mirror(b"mirror-cat")
        src = FallbackPageSource(live, mirror)
        result = src.fetch_category("MSX2", self._CAT_URL)
        assert result == b"mirror-cat"
        mirror.fetch_category.assert_called_once()

    def test_falls_back_to_mirror_when_live_page_fails(self):
        live = self._live(b"live-cat", None)
        mirror = self._mirror(b"mirror-cat", b"mirror-page")
        src = FallbackPageSource(live, mirror)
        assert src.fetch_page("Sony HB-F9S", self._PAGE_URL) == b"mirror-page"

    def test_returns_none_when_both_fail(self):
        live = self._live(None, None)
        mirror = self._mirror(None, None)
        src = FallbackPageSource(live, mirror)
        assert src.fetch_category("MSX2", self._CAT_URL) is None
        assert src.fetch_page("Sony HB-F9S", self._PAGE_URL) is None


# ---------------------------------------------------------------------------
# MirrorPageSource — pagination
# ---------------------------------------------------------------------------

class TestMirrorPageSourcePagination:
    """MirrorPageSource.fetch_category resolves _pageN filenames for page > 1."""

    def test_page1_reads_standard_filename(self, tmp_path):
        content = b"<html><body></body></html>"
        (tmp_path / "Category_MSX1 Computers - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers",
            page=1,
        )
        assert result == content

    def test_page2_reads_page2_filename(self, tmp_path):
        content = b"<html><body>page2</body></html>"
        (tmp_path / "Category_MSX1 Computers_page2 - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        # URL is the live pagefrom URL — mirror strips query string
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=Sony+HX-10",
            page=2,
        )
        assert result == content

    def test_page3_reads_page3_filename(self, tmp_path):
        content = b"<html><body>page3</body></html>"
        (tmp_path / "Category_MSX1 Computers_page3 - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=Z",
            page=3,
        )
        assert result == content

    def test_page2_missing_returns_none(self, tmp_path):
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=X",
            page=2,
        )
        assert result is None

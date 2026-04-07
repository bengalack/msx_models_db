"""Unit tests for scraper/mirror.py — PageSource implementations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scraper.mirror import LivePageSource, MirrorPageSource, _slug_to_filename


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

"""Unit tests for scraper/openmsx_source.py — XMLSource implementations."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scraper.openmsx_source import (
    SKIP_PREFIXES,
    FallbackXMLSource,
    LiveXMLSource,
    MirrorXMLSource,
)


# ---------------------------------------------------------------------------
# MirrorXMLSource — list_files
# ---------------------------------------------------------------------------

class TestMirrorXMLSourceListFiles:
    def test_returns_xml_filenames(self, tmp_path):
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        (tmp_path / "Panasonic_FS-A1WX.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        assert set(src.list_files()) == {"Sony_HB-F9S.xml", "Panasonic_FS-A1WX.xml"}

    def test_skips_non_xml_files(self, tmp_path):
        (tmp_path / "readme.txt").write_bytes(b"text")
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        assert src.list_files() == ["Sony_HB-F9S.xml"]

    def test_skips_boosted_prefix(self, tmp_path):
        (tmp_path / "Boosted_Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        names = src.list_files()
        assert "Sony_HB-F9S.xml" in names
        assert "Boosted_Sony_HB-F9S.xml" not in names

    def test_skips_all_configured_prefixes(self, tmp_path):
        for prefix in SKIP_PREFIXES:
            (tmp_path / f"{prefix}test.xml").write_bytes(b"<machine/>")
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        assert src.list_files() == ["Sony_HB-F9S.xml"]

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        src = MirrorXMLSource(tmp_path / "no-such-dir")
        assert src.list_files() == []

    def test_nonexistent_dir_logs_error(self, tmp_path, caplog):
        with caplog.at_level(logging.ERROR, logger="scraper.openmsx_source"):
            MirrorXMLSource(tmp_path / "no-such-dir")
        assert "not found" in caplog.text.lower()

    def test_applies_exclude_list_by_filename(self, tmp_path):
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        (tmp_path / "Panasonic_FS-A1WX.xml").write_bytes(b"<machine/>")

        exclude = MagicMock()
        exclude.is_excluded_by_filename.side_effect = lambda n: n == "Sony_HB-F9S.xml"

        src = MirrorXMLSource(tmp_path)
        names = src.list_files(exclude_list=exclude)
        assert "Panasonic_FS-A1WX.xml" in names
        assert "Sony_HB-F9S.xml" not in names

    def test_returns_sorted_names(self, tmp_path):
        (tmp_path / "Zylog_Z80.xml").write_bytes(b"<machine/>")
        (tmp_path / "Alpha_A1.xml").write_bytes(b"<machine/>")
        (tmp_path / "Micro_M1.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        names = src.list_files()
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# MirrorXMLSource — fetch_file
# ---------------------------------------------------------------------------

class TestMirrorXMLSourceFetchFile:
    def test_returns_bytes_when_present(self, tmp_path):
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(b"<machine/>")
        src = MirrorXMLSource(tmp_path)
        assert src.fetch_file("Sony_HB-F9S.xml") == b"<machine/>"

    def test_returns_none_when_file_missing(self, tmp_path):
        src = MirrorXMLSource(tmp_path)
        assert src.fetch_file("Nonexistent.xml") is None

    def test_returns_none_when_dir_missing(self, tmp_path):
        src = MirrorXMLSource(tmp_path / "no-such-dir")
        assert src.fetch_file("Sony_HB-F9S.xml") is None

    def test_missing_file_logs_warning(self, tmp_path, caplog):
        src = MirrorXMLSource(tmp_path)
        with caplog.at_level(logging.WARNING, logger="scraper.openmsx_source"):
            src.fetch_file("Nonexistent.xml")
        assert "not found" in caplog.text.lower()


# ---------------------------------------------------------------------------
# FallbackXMLSource
# ---------------------------------------------------------------------------

class TestFallbackXMLSource:
    def test_list_files_uses_live_when_success(self):
        live = MagicMock(spec=LiveXMLSource)
        live.list_files.return_value = ["Sony_HB-F9S.xml"]
        mirror = MagicMock(spec=MirrorXMLSource)
        src = FallbackXMLSource(live, mirror)
        assert src.list_files() == ["Sony_HB-F9S.xml"]
        mirror.list_files.assert_not_called()

    def test_list_files_falls_back_to_mirror_on_exception(self):
        live = MagicMock(spec=LiveXMLSource)
        live.list_files.side_effect = Exception("network error")
        mirror = MagicMock(spec=MirrorXMLSource)
        mirror.list_files.return_value = ["Sony_HB-F9S.xml"]
        src = FallbackXMLSource(live, mirror)
        assert src.list_files() == ["Sony_HB-F9S.xml"]

    def test_fetch_file_uses_live_when_success(self):
        live = MagicMock(spec=LiveXMLSource)
        live.fetch_file.return_value = b"<machine/>"
        mirror = MagicMock(spec=MirrorXMLSource)
        src = FallbackXMLSource(live, mirror)
        assert src.fetch_file("Sony_HB-F9S.xml") == b"<machine/>"
        mirror.fetch_file.assert_not_called()

    def test_fetch_file_falls_back_to_mirror_when_live_returns_none(self):
        live = MagicMock(spec=LiveXMLSource)
        live.fetch_file.return_value = None
        mirror = MagicMock(spec=MirrorXMLSource)
        mirror.fetch_file.return_value = b"<machine/>"
        src = FallbackXMLSource(live, mirror)
        assert src.fetch_file("Sony_HB-F9S.xml") == b"<machine/>"

    def test_fetch_file_returns_none_when_both_fail(self):
        live = MagicMock(spec=LiveXMLSource)
        live.fetch_file.return_value = None
        mirror = MagicMock(spec=MirrorXMLSource)
        mirror.fetch_file.return_value = None
        src = FallbackXMLSource(live, mirror)
        assert src.fetch_file("Sony_HB-F9S.xml") is None

    def test_list_files_passes_exclude_list_to_live(self):
        live = MagicMock(spec=LiveXMLSource)
        live.list_files.return_value = []
        mirror = MagicMock(spec=MirrorXMLSource)
        exclude = MagicMock()
        src = FallbackXMLSource(live, mirror)
        src.list_files(exclude_list=exclude)
        live.list_files.assert_called_once_with(exclude)

    def test_list_files_passes_exclude_list_to_mirror_on_fallback(self):
        live = MagicMock(spec=LiveXMLSource)
        live.list_files.side_effect = Exception("fail")
        mirror = MagicMock(spec=MirrorXMLSource)
        mirror.list_files.return_value = []
        exclude = MagicMock()
        src = FallbackXMLSource(live, mirror)
        src.list_files(exclude_list=exclude)
        mirror.list_files.assert_called_once_with(exclude)


# ---------------------------------------------------------------------------
# fetch_all integration with MirrorXMLSource
# ---------------------------------------------------------------------------

class TestFetchAllWithMirrorSource:
    """fetch_all accepts a MirrorXMLSource and parses models from it."""

    _XML = (
        b"<machine>"
        b"<info>"
        b"<manufacturer>Sony</manufacturer>"
        b"<code>HB-F9S</code>"
        b"<type>MSX2</type>"
        b"<release_year>1987</release_year>"
        b"<region>jp</region>"
        b"</info>"
        b"<devices/>"
        b"</machine>"
    )

    def test_fetch_all_with_mirror_returns_models(self, tmp_path):
        from scraper.openmsx import fetch_all
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(self._XML)
        src = MirrorXMLSource(tmp_path)
        models = fetch_all(source=src, delay=0)
        assert len(models) == 1
        assert models[0]["model"] == "HB-F9S"
        assert models[0]["manufacturer"] == "Sony"

    def test_fetch_all_with_mirror_no_session_needed(self, tmp_path):
        """No requests.Session is created when source is given."""
        from scraper.openmsx import fetch_all
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(self._XML)
        src = MirrorXMLSource(tmp_path)
        models = fetch_all(source=src, delay=0)
        assert isinstance(models, list)

    def test_fetch_all_skips_missing_file(self, tmp_path):
        """If fetch_file returns None the model is skipped, others continue."""
        from scraper.openmsx import fetch_all
        (tmp_path / "Sony_HB-F9S.xml").write_bytes(self._XML)
        src = MirrorXMLSource(tmp_path)
        # Patch fetch_file to return None for the first call
        original_fetch = src.fetch_file
        calls = []
        def patched_fetch(name):
            calls.append(name)
            return None if not calls[1:] else original_fetch(name)
        src.fetch_file = patched_fetch
        models = fetch_all(source=src, delay=0)
        assert models == []

    def test_fetch_all_with_empty_mirror_returns_empty(self, tmp_path):
        from scraper.openmsx import fetch_all
        src = MirrorXMLSource(tmp_path)
        models = fetch_all(source=src, delay=0)
        assert models == []

    def test_fetch_all_with_nonexistent_mirror_returns_empty(self, tmp_path):
        from scraper.openmsx import fetch_all
        src = MirrorXMLSource(tmp_path / "no-such-dir")
        models = fetch_all(source=src, delay=0)
        assert models == []

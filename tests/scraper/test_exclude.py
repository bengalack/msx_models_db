"""Tests for scraper.exclude — ExcludeList match logic and load/validate."""

from __future__ import annotations

import json

import pytest
from scraper.exclude import ExcludeList, load_excludes


# ── ExcludeList.is_excluded ───────────────────────────────────────────────


class TestIsExcluded:

    def _make(self, *rules: dict) -> ExcludeList:
        return ExcludeList(rules=list(rules))

    def test_exact_match(self):
        el = self._make({"manufacturer": "Sony", "model": "HB-75P"})
        assert el.is_excluded("Sony", "HB-75P")

    def test_exact_no_match_different_manufacturer(self):
        el = self._make({"manufacturer": "Sony", "model": "HB-75P"})
        assert not el.is_excluded("Philips", "HB-75P")

    def test_exact_no_match_different_model(self):
        el = self._make({"manufacturer": "Sony", "model": "HB-75P"})
        assert not el.is_excluded("Sony", "HB-F1XDJ")

    def test_empty_string_matches_empty_field(self):
        el = self._make({"manufacturer": "", "model": "SomeName"})
        assert el.is_excluded("", "SomeName")

    def test_empty_string_matches_none_field(self):
        el = self._make({"manufacturer": "", "model": "SomeName"})
        assert el.is_excluded(None, "SomeName")

    def test_empty_string_does_not_match_nonempty(self):
        el = self._make({"manufacturer": "", "model": "SomeName"})
        assert not el.is_excluded("Sony", "SomeName")

    def test_wildcard_model_matches_any(self):
        el = self._make({"manufacturer": "Sony", "model": "*"})
        assert el.is_excluded("Sony", "HB-75P")
        assert el.is_excluded("Sony", "HB-F1XDJ")
        assert el.is_excluded("Sony", "")
        assert el.is_excluded("Sony", None)

    def test_wildcard_model_does_not_match_other_manufacturer(self):
        el = self._make({"manufacturer": "Sony", "model": "*"})
        assert not el.is_excluded("Philips", "HB-75P")

    def test_wildcard_manufacturer_matches_any(self):
        el = self._make({"manufacturer": "*", "model": "HB-75P"})
        assert el.is_excluded("Sony", "HB-75P")
        assert el.is_excluded("Philips", "HB-75P")

    def test_full_wildcard_matches_everything(self):
        el = self._make({"manufacturer": "*", "model": "*"})
        assert el.is_excluded("Sony", "HB-75P")
        assert el.is_excluded("", "")
        assert el.is_excluded(None, None)

    def test_case_sensitive_no_match(self):
        el = self._make({"manufacturer": "sony", "model": "hb-75p"})
        assert not el.is_excluded("Sony", "HB-75P")

    def test_filename_rule_is_ignored(self):
        """is_excluded should skip filename-mode rules."""
        el = self._make({"filename": "Sony_HB-75P.xml"})
        assert not el.is_excluded("Sony", "HB-75P")

    def test_empty_rule_list_never_excludes(self):
        el = ExcludeList()
        assert not el.is_excluded("Sony", "HB-75P")


# ── ExcludeList.is_excluded_by_filename ──────────────────────────────────


class TestIsExcludedByFilename:

    def _make(self, *rules: dict) -> ExcludeList:
        return ExcludeList(rules=list(rules))

    def test_exact_filename_match(self):
        el = self._make({"filename": "Sony_HB-75P.xml"})
        assert el.is_excluded_by_filename("Sony_HB-75P.xml")

    def test_no_match_different_filename(self):
        el = self._make({"filename": "Sony_HB-75P.xml"})
        assert not el.is_excluded_by_filename("Philips_NMS8280.xml")

    def test_manufacturer_model_rule_is_ignored(self):
        """is_excluded_by_filename should skip manufacturer+model rules."""
        el = self._make({"manufacturer": "Sony", "model": "HB-75P"})
        assert not el.is_excluded_by_filename("Sony_HB-75P.xml")

    def test_empty_rule_list_never_excludes(self):
        el = ExcludeList()
        assert not el.is_excluded_by_filename("Sony_HB-75P.xml")


# ── ExcludeList.dead_rules ───────────────────────────────────────────────


class TestDeadRules:

    def test_all_rules_dead_on_fresh_list(self):
        el = ExcludeList(rules=[
            {"manufacturer": "Sony", "model": "HB-75P"},
            {"filename": "Foo.xml"},
        ])
        assert el.dead_rules() == [0, 1]

    def test_matched_rule_not_dead(self):
        el = ExcludeList(rules=[
            {"manufacturer": "Sony", "model": "HB-75P"},
            {"manufacturer": "Philips", "model": "NMS8280"},
        ])
        el.is_excluded("Sony", "HB-75P")
        dead = el.dead_rules()
        assert 0 not in dead
        assert 1 in dead

    def test_empty_list_has_no_dead_rules(self):
        el = ExcludeList()
        assert el.dead_rules() == []


# ── load_excludes ─────────────────────────────────────────────────────────


class TestLoadExcludes:

    def test_missing_file_returns_empty(self, tmp_path):
        el = load_excludes(tmp_path / "missing.json")
        assert el.rules == []

    def test_empty_array_returns_empty_list(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text("[]")
        el = load_excludes(path)
        assert el.rules == []
        assert not el.is_excluded("Sony", "HB-75P")

    def test_valid_rules_loaded(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps([
            {"manufacturer": "Sony", "model": "HB-75P"},
            {"filename": "Boosted_MSX2_JP.xml"},
        ]))
        el = load_excludes(path)
        assert len(el.rules) == 2
        assert el.is_excluded("Sony", "HB-75P")
        assert el.is_excluded_by_filename("Boosted_MSX2_JP.xml")

    def test_malformed_json_raises_value_error(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text("{bad json")
        with pytest.raises(ValueError, match="Failed to parse"):
            load_excludes(path)

    def test_not_an_array_raises_value_error(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps({"manufacturer": "Sony", "model": "HB-75P"}))
        with pytest.raises(ValueError, match="must contain a JSON array"):
            load_excludes(path)

    def test_non_dict_entry_raises_value_error(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps(["not_a_dict"]))
        with pytest.raises(ValueError, match="entry 0 must be a JSON object"):
            load_excludes(path)

    def test_unknown_keys_raise_value_error(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps([{"typo_field": "x"}]))
        with pytest.raises(ValueError, match="unrecognised keys"):
            load_excludes(path)

    def test_non_string_value_raises_value_error(self, tmp_path):
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps([{"manufacturer": "Sony", "model": 123}]))
        with pytest.raises(ValueError, match="must be a string"):
            load_excludes(path)

    def test_all_wildcard_emits_warning(self, tmp_path, caplog):
        import logging
        path = tmp_path / "exclude.json"
        path.write_text(json.dumps([{"manufacturer": "*", "model": "*"}]))
        with caplog.at_level(logging.WARNING):
            el = load_excludes(path)
        assert any("All-wildcard" in r.message for r in caplog.records)
        assert len(el.rules) == 1


# ── openMSX scraper wiring ────────────────────────────────────────────────


class TestOpenMSXWiring:
    """Tests for ExcludeList wired into openmsx.list_machine_files and fetch_all."""

    # Minimal valid MSX2 XML for parse_machine_xml
    _XML = b"""<?xml version="1.0" ?>
<msxconfig>
  <info>
    <manufacturer>Sony</manufacturer>
    <code>HB-75P</code>
    <type>MSX2</type>
    <release_year>1985</release_year>
    <region>eu</region>
  </info>
  <devices/>
</msxconfig>"""

    def test_filename_excluded_before_fetch(self):
        from scraper.openmsx import list_machine_files
        from unittest.mock import MagicMock

        el = ExcludeList(rules=[{"filename": "Sony_HB-75P.xml"}])
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"type": "file", "name": "Sony_HB-75P.xml", "download_url": "http://x/Sony_HB-75P.xml"},
            {"type": "file", "name": "Philips_NMS8250.xml", "download_url": "http://x/Philips_NMS8250.xml"},
        ]
        entries = list_machine_files(session, exclude_list=el)
        names = [e["name"] for e in entries]
        assert "Sony_HB-75P.xml" not in names
        assert "Philips_NMS8250.xml" in names

    def test_model_excluded_post_parse(self):
        from scraper.openmsx import parse_machine_xml
        el = ExcludeList(rules=[{"manufacturer": "Sony", "model": "HB-75P"}])
        result = parse_machine_xml(self._XML, "Sony_HB-75P.xml")
        assert result is not None
        assert el.is_excluded(result.get("manufacturer"), result.get("model"))

    def test_non_excluded_model_passes(self):
        from scraper.openmsx import parse_machine_xml
        el = ExcludeList(rules=[{"manufacturer": "Philips", "model": "NMS8250"}])
        result = parse_machine_xml(self._XML, "Sony_HB-75P.xml")
        assert result is not None
        assert not el.is_excluded(result.get("manufacturer"), result.get("model"))

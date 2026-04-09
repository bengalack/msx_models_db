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

    # ── glob / wildcard patterns ──────────────────────────────────────────

    def test_glob_star_matches_prefix(self):
        el = self._make({"filename": "C-BIOS*"})
        assert el.is_excluded_by_filename("C-BIOS_MSX2_EU.xml")
        assert el.is_excluded_by_filename("C-BIOS_MSX2+_JP.xml")

    def test_glob_star_no_match_different_prefix(self):
        el = self._make({"filename": "C-BIOS*"})
        assert not el.is_excluded_by_filename("Sony_HB-F9S.xml")

    def test_glob_star_matches_any_xml(self):
        el = self._make({"filename": "*.xml"})
        assert el.is_excluded_by_filename("Sony_HB-F9S.xml")
        assert el.is_excluded_by_filename("Boosted_MSX2_JP.xml")

    def test_glob_star_extension_does_not_match_html(self):
        el = self._make({"filename": "*.xml"})
        assert not el.is_excluded_by_filename("Sony HB-75P - MSX Wiki.html")

    def test_glob_question_mark_single_char(self):
        el = self._make({"filename": "Sony_HB-75?.xml"})
        assert el.is_excluded_by_filename("Sony_HB-75P.xml")
        assert not el.is_excluded_by_filename("Sony_HB-750XX.xml")

    def test_glob_partial_pattern_with_prefix_and_extension(self):
        el = self._make({"filename": "Boosted_*.xml"})
        assert el.is_excluded_by_filename("Boosted_MSX2_JP.xml")
        assert not el.is_excluded_by_filename("Sony_HB-F9S.xml")

    def test_glob_html_wildcard_for_msxorg_mirror(self):
        """Glob patterns work on msx.org mirror HTML filenames too."""
        el = self._make({"filename": "AGE Labs*.html"})
        assert el.is_excluded_by_filename("AGE Labs GR8BIT - MSX Wiki.html")
        assert not el.is_excluded_by_filename("Sony HB-75P - MSX Wiki.html")

    def test_glob_multiple_rules_first_match_wins(self):
        el = self._make({"filename": "Sony*"}, {"filename": "Philips*"})
        assert el.is_excluded_by_filename("Sony_HB-F9S.xml")
        assert el.is_excluded_by_filename("Philips_NMS8250.xml")
        assert not el.is_excluded_by_filename("Panasonic_FS-A1WX.xml")


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

    def test_wildcard_filename_rule_matched_is_not_dead(self):
        el = ExcludeList(rules=[{"filename": "C-BIOS*"}])
        el.is_excluded_by_filename("C-BIOS_MSX2_EU.xml")
        assert el.dead_rules() == []

    def test_wildcard_filename_rule_unmatched_is_dead(self):
        el = ExcludeList(rules=[{"filename": "C-BIOS*"}])
        el.is_excluded_by_filename("Sony_HB-F9S.xml")
        assert el.dead_rules() == [0]


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


# ── msx.org scraper wiring ────────────────────────────────────────────────


class TestMsxOrgWiring:
    """Tests for ExcludeList wired into msxorg.fetch_all.

    Covers both the pre-fetch filename check (fires before fetch_page is called)
    and the post-parse manufacturer+model check (fires after parse_model_page).
    """

    # Category page listing one model
    _CATEGORY_HTML = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
        b"</div></body></html>"
    )
    # Model page with a parseable specs table (Brand + Model minimum)
    _GOOD_MODEL_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sony</td></tr>
      <tr><th>Model</th><td>HB-75P</td></tr>
    </table></body></html>
    """
    # Model page with no specs table — triggers "No specs table found" warning
    _NO_SPECS_HTML = b"<html><body><h1>Sony HB-75P</h1><p>No table here.</p></body></html>"

    def _write_all_categories(self, tmp_path, html: bytes = None):
        """Write all three category files so list_model_pages can enumerate them."""
        cats = [
            "Category_MSX2 Computers",
            "Category_MSX2+ Computers",
            "Category_MSX turbo R Computers",
        ]
        for cat in cats:
            content = html if html is not None else b"<html><body></body></html>"
            (tmp_path / f"{cat} - MSX Wiki.html").write_bytes(content)

    # ── pre-fetch filename check ──────────────────────────────────────────

    def test_filename_exclude_suppresses_no_specs_warning(self, tmp_path, caplog):
        """Model with no specs table emits no warning when excluded by filename."""
        import logging
        from scraper.exclude import ExcludeList
        from scraper.mirror import MirrorPageSource
        from scraper.msxorg import fetch_all

        self._write_all_categories(tmp_path, self._CATEGORY_HTML)
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._NO_SPECS_HTML)

        el = ExcludeList(rules=[{"filename": "Sony HB-75P*"}])
        source = MirrorPageSource(tmp_path)

        with caplog.at_level(logging.WARNING):
            models = fetch_all(source=source, delay=0, exclude_list=el)

        assert models == []
        assert not any("No specs table" in r.message for r in caplog.records)

    def test_no_specs_warning_emitted_without_exclude(self, tmp_path, caplog):
        """Model with no specs table emits WARNING when no exclude rule applies."""
        import logging
        from scraper.mirror import MirrorPageSource
        from scraper.msxorg import fetch_all

        self._write_all_categories(tmp_path, self._CATEGORY_HTML)
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._NO_SPECS_HTML)

        source = MirrorPageSource(tmp_path)
        with caplog.at_level(logging.WARNING):
            models = fetch_all(source=source, delay=0)

        assert models == []
        assert any("No specs table" in r.message for r in caplog.records)

    def test_filename_exclude_prevents_fetch_page_call(self, tmp_path):
        """fetch_page is never called for a filename-excluded model."""
        from scraper.exclude import ExcludeList
        from scraper.msxorg import fetch_all

        fetch_page_calls: list[str] = []

        class TrackingSource:
            def fetch_category(self, standard, url):
                return self._CATEGORY_HTML

            def fetch_page(self, title, url):
                fetch_page_calls.append(title)
                return None

        # Bind category HTML via closure
        TrackingSource._CATEGORY_HTML = self._CATEGORY_HTML

        el = ExcludeList(rules=[{"filename": "Sony HB-75P - MSX Wiki.html"}])
        fetch_all(source=TrackingSource(), delay=0, exclude_list=el)

        assert "Sony HB-75P" not in fetch_page_calls

    def test_filename_glob_exclude_prevents_fetch_page_call(self, tmp_path):
        """Glob pattern filename rule also prevents fetch_page from being called."""
        from scraper.exclude import ExcludeList
        from scraper.msxorg import fetch_all

        fetch_page_calls: list[str] = []

        class TrackingSource:
            _CATEGORY_HTML = self._CATEGORY_HTML

            def fetch_category(self, standard, url):
                return self._CATEGORY_HTML

            def fetch_page(self, title, url):
                fetch_page_calls.append(title)
                return None

        el = ExcludeList(rules=[{"filename": "Sony*"}])
        fetch_all(source=TrackingSource(), delay=0, exclude_list=el)

        assert fetch_page_calls == []

    # ── post-parse manufacturer+model check ──────────────────────────────

    def test_manufacturer_model_exclude_removes_parsed_model(self, tmp_path):
        """Model that parses successfully is removed by a manufacturer+model rule."""
        from scraper.exclude import ExcludeList
        from scraper.mirror import MirrorPageSource
        from scraper.msxorg import fetch_all

        self._write_all_categories(tmp_path, self._CATEGORY_HTML)
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._GOOD_MODEL_HTML)

        el = ExcludeList(rules=[{"manufacturer": "Sony", "model": "HB-75P"}])
        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0, exclude_list=el)
        assert models == []

    def test_non_matching_exclude_does_not_remove_model(self, tmp_path):
        """An exclude rule that does not match leaves the model in the output."""
        from scraper.exclude import ExcludeList
        from scraper.mirror import MirrorPageSource
        from scraper.msxorg import fetch_all

        self._write_all_categories(tmp_path, self._CATEGORY_HTML)
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._GOOD_MODEL_HTML)

        el = ExcludeList(rules=[{"manufacturer": "Philips", "model": "NMS 8250"}])
        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0, exclude_list=el)
        assert len(models) == 1
        assert models[0]["manufacturer"] == "Sony"

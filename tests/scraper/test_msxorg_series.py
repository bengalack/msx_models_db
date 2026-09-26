"""Tests for scraper/msxorg_series.py — per-variant data from msx.org series pages.

Fixtures are inline text/HTML modelled on the real series pages; the tests own
them, so no mirror file is needed.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from scraper.msxorg_series import (
    build_variant_specs,
    choose_slotmap_table,
    expand_region_codes,
    resolve_value,
    series_slug,
    variant_row,
)

HB10 = ["HB-10", "HB-10B", "HB-10D", "HB-10P"]
HX10 = ["HX-10S", "HX-10SA", "HX-10D", "HX-10DP", "HX-10P"]


# ── resolve_value ───────────────────────────────────────────────────────────

class TestResolveValue:
    def test_shared_value_is_used_as_is(self):
        assert resolve_value("64kB in slot 2", "HB-10B", HB10) == "64kB in slot 2"

    def test_label_colon_form(self):
        text = "HB-10: Japan HB-10B: United Kingdom HB-10D: Germany HB-10P: Netherlands and Spain"
        assert resolve_value(text, "HB-10B", HB10) == "United Kingdom"
        assert resolve_value(text, "HB-10P", HB10) == "Netherlands and Spain"

    def test_label_colon_typo_still_ends_the_previous_segment(self):
        """msx.org wrote 'HB-22I:' for HX-22I; HX-22GB must not swallow it."""
        text = "HX-22: Japan HX-22GB: United Kingdom HB-22I: Italy"
        variants = ["HX-22", "HX-22CH", "HX-22GB", "HX-22I"]
        assert resolve_value(text, "HX-22GB", variants) == "United Kingdom"

    def test_label_colon_variant_not_listed_is_unresolved(self):
        text = "HX-22: Japan HX-22GB: United Kingdom"
        assert resolve_value(text, "HX-22CH", ["HX-22", "HX-22CH", "HX-22GB"]) is None

    def test_leading_label_form(self):
        text = '(HB-101) QWERTY/JP50on - (HB-101P) QWERTY with a "£" key'
        assert resolve_value(text, "HB-101P", ["HB-101", "HB-101P"]) == 'QWERTY with a "£" key'

    def test_trailing_qualifier_form(self):
        text = "16kB in slot 0 (HB-10) or 64kB in slot 3 (other models)"
        assert resolve_value(text, "HB-10", HB10) == "16kB in slot 0"
        assert resolve_value(text, "HB-10D", HB10) == "64kB in slot 3"

    def test_trailing_qualifier_with_several_names(self):
        text = "Texas Instruments TMS9918A (HX-10S, HX-10D) or TMS9929A (HX-10P)"
        assert resolve_value(text, "HX-10D", HX10) == "Texas Instruments TMS9918A"
        assert resolve_value(text, "HX-10P", HX10) == "TMS9929A"

    def test_whole_token_matching(self):
        """HX-10S must not match inside HX-10SA."""
        text = "16kB (HX-10SA) or 64kB (HX-10S)"
        assert resolve_value(text, "HX-10S", HX10) == "64kB"
        assert resolve_value(text, "HX-10SA", HX10) == "16kB"

    def test_in_variant_form(self):
        text = "Gate array Toshiba TCX-1010 in HX-21, TCX-1012 in HX-21F"
        variants = ["HX-21", "HX-21F"]
        assert resolve_value(text, "HX-21", variants) == "Gate array Toshiba TCX-1010"
        assert resolve_value(text, "HX-21F", variants) == "TCX-1012"

    def test_named_variants_without_this_one_is_unresolved(self):
        """Never hand one variant's value to another."""
        text = "TMS9918A (HX-10S, HX-10D) or TMS9929A (HX-10P)"
        assert resolve_value(text, "HX-10DP", HX10) is None

    @pytest.mark.parametrize("text,region,expected", [
        ("1984-10-16 in Japan - 1985 in Spain - 1986 in Argentina", "Spain", "1985"),
        ("1984-10-16 in Japan - 1985 in Spain - 1986 in Argentina", "Argentina", "1986"),
        ("1984-10-16 (Japan) 1985 (France)", "France", "1985"),
        ("1984-10-16 (Japan) 1985 (Europe)", "United Kingdom", "1985"),  # European country -> Europe
    ])
    def test_region_qualified_form(self, text, region, expected):
        variants = ["HX-20", "HX-20E"]
        assert resolve_value(text, "HX-20E", variants, region=region) == expected

    def test_region_qualified_without_matching_region_is_unresolved(self):
        text = "1984-10-16 in Japan - 1985 in Spain"
        assert resolve_value(text, "HX-20I", ["HX-20", "HX-20I"], region="Italy") is None


# ── variant table, region codes ─────────────────────────────────────────────

_VARIANT_TABLE = """
<html><body>
<table>
<tr><th>Product</th><th>Region</th><th>Keyboard</th></tr>
<tr><td>Sony HB-75</td><td>JP</td><td>QWERTY/JP50on</td></tr>
<tr><td>Sony HB-75B</td><td>UK</td><td>QWERTY with £ key</td></tr>
<tr><td>Sony HB-75P</td><td>Europe</td><td>QWERTY with £ key</td></tr>
</table>
</body></html>
"""


class TestVariantRow:
    def test_row_for_variant(self):
        soup = BeautifulSoup(_VARIANT_TABLE, "lxml")
        row = variant_row(soup, "HB-75B", ["HB-75", "HB-75B", "HB-75P"])
        assert row["Region"] == "UK"
        assert row["Keyboard"] == "QWERTY with £ key"

    def test_missing_variant_gives_empty_row(self):
        soup = BeautifulSoup(_VARIANT_TABLE, "lxml")
        assert variant_row(soup, "HB-75F", ["HB-75", "HB-75B", "HB-75F", "HB-75P"]) == {}


class TestExpandRegionCodes:
    @pytest.mark.parametrize("raw,expected", [
        ("JP", "Japan"),
        ("UK", "United Kingdom"),
        ("BE, NL", "Belgium, Netherlands"),
        ("Europe", "Europe"),   # already a name
        ("XX", "XX"),           # unknown code kept
    ])
    def test_codes(self, raw, expected):
        assert expand_region_codes(raw) == expected


# ── series link ─────────────────────────────────────────────────────────────

class TestSeriesSlug:
    def test_link_labelled_series(self):
        html = ('<div id="bodyContent"><p>see <a href="/wiki/Category:Sony_HB-75">HB-75 series</a>'
                ' for the technical details</p></div>')
        assert series_slug(BeautifulSoup(html, "lxml")) == "Sony_HB-75"

    def test_plain_category_link_is_not_a_series(self):
        html = '<div id="bodyContent"><a href="/wiki/Category:Sony">Sony</a></div>'
        assert series_slug(BeautifulSoup(html, "lxml")) is None


# ── slot map choice ─────────────────────────────────────────────────────────

def _slot_section(heading_id: str, cell: str) -> str:
    return (f'<h2><span id="{heading_id}" class="mw-headline">x</span></h2>'
            '<table><tr><td></td><th>Slot 0</th></tr>'
            f'<tr><th>Page 0000h~3FFFh</th><td>{cell}</td></tr></table>')


class TestChooseSlotmapTable:
    @staticmethod
    def _soup(*sections: str) -> BeautifulSoup:
        return BeautifulSoup("<html><body>" + "".join(sections) + "</body></html>", "lxml")

    @staticmethod
    def _cell(table) -> str:
        return table.find_all("td")[-1].get_text(strip=True)

    def test_heading_naming_the_variant_wins(self):
        soup = self._soup(_slot_section("Slot_Map_for_HB-75_model", "A"),
                          _slot_section("Slot_Map_for_other_models", "B"))
        variants = ["HB-75", "HB-75P"]
        assert self._cell(choose_slotmap_table(soup, "HB-75", variants, "")) == "A"
        assert self._cell(choose_slotmap_table(soup, "HB-75P", variants, "")) == "B"

    def test_heading_matching_the_ram_size(self):
        soup = self._soup(_slot_section("Slot_Map_for_16kB_model", "A"),
                          _slot_section("Slot_Map_for_64kB_models", "B"))
        assert self._cell(choose_slotmap_table(soup, "HB-10B", HB10, "64kB in slot 3")) == "B"
        assert self._cell(choose_slotmap_table(soup, "HB-10", HB10, "16kB in slot 0")) == "A"

    def test_falls_back_to_first(self):
        soup = self._soup(_slot_section("Slot_Map", "A"))
        assert self._cell(choose_slotmap_table(soup, "HB-201P", ["HB-201", "HB-201P"], "")) == "A"

    def test_no_slot_map(self):
        assert choose_slotmap_table(self._soup(), "HB-75", ["HB-75"], "") is None


# ── build_variant_specs (end to end on one series page) ─────────────────────

_SERIES_PAGE = """
<html><body><div id="bodyContent">
<table>
<tr><th>Product</th><th>Region</th><th>Keyboard</th></tr>
<tr><td>Sony HB-10</td><td>JP</td><td>QWERTY/JP50on</td></tr>
<tr><td>Sony HB-10D</td><td>DE</td><td>QWERTZ</td></tr>
</table>
<table>
<tr><th>Brand</th><td>Sony</td></tr>
<tr><th>Model</th><td>HB-10 / HB-10D</td></tr>
<tr><th>Year</th><td>Late 1985 (HB-10) or 1986 (other models)</td></tr>
<tr><th>Region</th><td>See table above</td></tr>
<tr><th>RAM</th><td>16kB in slot 0 (HB-10) or 64kB in slot 3 (other models)</td></tr>
<tr><th>Video</th><td>Texas Instruments TMS9118NL (HB-10) or Toshiba T6950 (other models)</td></tr>
<tr><th>Chipset</th><td>Yamaha S3527</td></tr>
<tr><th>Keyboard layout</th><td>see table above</td></tr>
</table>
""" + _slot_section("Slot_Map_for_16kB_model", "16kB RAM") + _slot_section("Slot_Map_for_64kB_models", "64kB RAM") + """
</div>
<div id="mw-pages"><a href="/wiki/Sony_HB-10">Sony HB-10</a><a href="/wiki/Sony_HB-10D">Sony HB-10D</a></div>
</body></html>
"""


class TestBuildVariantSpecs:
    def test_specs_for_one_variant(self):
        soup = BeautifulSoup(_SERIES_PAGE, "lxml")
        specs, table = build_variant_specs(soup, "Sony HB-10D", page_title="Sony HB-10D")
        assert specs["Brand"] == "Sony"
        assert specs["Model"] == "HB-10D"
        assert specs["Year"] == "1986"
        assert specs["Region"] == "Germany"
        assert specs["RAM"] == "64kB in slot 3"
        assert specs["Video"] == "Toshiba T6950"
        assert specs["Chipset"] == "Yamaha S3527"
        assert specs["Keyboard layout"] == "QWERTZ"
        assert "64kB RAM" in table.get_text()

    def test_other_variant_of_the_same_series(self):
        soup = BeautifulSoup(_SERIES_PAGE, "lxml")
        specs, table = build_variant_specs(soup, "Sony HB-10", page_title="Sony HB-10")
        assert (specs["Year"], specs["Region"], specs["RAM"]) == ("Late 1985", "Japan", "16kB in slot 0")
        assert "16kB RAM" in table.get_text()

    def test_unresolved_field_is_left_out(self):
        html = _SERIES_PAGE.replace("(other models)</td></tr>\n<tr><th>Video",
                                    "(HB-10X)</td></tr>\n<tr><th>Video")
        soup = BeautifulSoup(html, "lxml")
        specs, _ = build_variant_specs(soup, "Sony HB-10D", page_title="Sony HB-10D")
        assert "RAM" not in specs

    def test_variant_table_region_beats_a_family_wide_list(self):
        """HX-20: specs Region lists every market; the variant table has each variant's own."""
        html = (_SERIES_PAGE
                .replace("<tr><th>Region</th><td>See table above</td></tr>",
                         "<tr><th>Region</th><td>Japan, Germany</td></tr>")
                .replace("<tr><th>Year</th><td>Late 1985 (HB-10) or 1986 (other models)</td></tr>",
                         "<tr><th>Year</th><td>1985 in Japan - 1986 in Germany</td></tr>"))
        soup = BeautifulSoup(html, "lxml")
        specs, _ = build_variant_specs(soup, "Sony HB-10D", page_title="Sony HB-10D")
        assert specs["Region"] == "Germany"
        assert specs["Year"] == "1986"      # region-qualified year uses the variant's region

    def test_no_specs_table(self):
        soup = BeautifulSoup("<html><body><p>nothing</p></body></html>", "lxml")
        assert build_variant_specs(soup, "Sony HB-10D", page_title="Sony HB-10D") == (None, None)

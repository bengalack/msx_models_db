"""Unit tests for scraper/msxorg_slotmap.py."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from scraper.msxorg_slotmap import (
    _ABSENT,
    _EMPTY_PAGE,
    _ALL_KEYS,
    _classify_cell_text,
    _CART_SENTINEL,
    _flatten_table,
    _page_from_label,
    _parse_col_label,
    parse_msxorg_slotmap,
    parse_slotmap_from_soup,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _table(html: str) -> BeautifulSoup:
    """Return the first <table> tag from the given HTML fragment."""
    return _soup(html).find("table")


# ── _page_from_label ──────────────────────────────────────────────────────

class TestPageFromLabel:
    def test_c000_is_page3(self):
        assert _page_from_label("Page C000h~FFFFh") == 3

    def test_8000_is_page2(self):
        assert _page_from_label("Page 8000h~BFFFh") == 2

    def test_4000_is_page1(self):
        assert _page_from_label("Page 4000h~7FFFh") == 1

    def test_0000_is_page0(self):
        assert _page_from_label("Page 0000h~3FFFh") == 0

    def test_bank_prefix_also_works(self):
        # 1chipMSX uses "Bank" instead of "Page"
        assert _page_from_label("Bank C000h~FFFFh") == 3

    def test_empty_string_returns_none(self):
        assert _page_from_label("") is None

    def test_non_page_text_returns_none(self):
        assert _page_from_label("Slot 0") is None

    def test_lowercase_hex(self):
        assert _page_from_label("page c000h~ffffh") == 3


# ── _parse_col_label ──────────────────────────────────────────────────────

class TestParseColLabel:
    def test_nn_ms_ss(self):
        assert _parse_col_label("0-0") == (0, 0)
        assert _parse_col_label("3-3") == (3, 3)
        assert _parse_col_label("0-1") == (0, 1)
        assert _parse_col_label("3-1") == (3, 1)

    def test_slot_nn_ms_ss(self):
        assert _parse_col_label("Slot 0-0") == (0, 0)
        assert _parse_col_label("Slot 3-2") == (3, 2)

    def test_slot_n_nonexpanded(self):
        assert _parse_col_label("Slot 0") == (0, 0)
        assert _parse_col_label("Slot 1") == (1, 0)
        assert _parse_col_label("Slot 2") == (2, 0)
        assert _parse_col_label("Slot 3") == (3, 0)

    def test_bare_digit(self):
        assert _parse_col_label("1") == (1, 0)

    def test_asterisk_suffix_stripped(self):
        # "3-3*" appears for marked slots in 1chipMSX
        assert _parse_col_label("3-3*") == (3, 3)
        assert _parse_col_label("Slot 3-3*") == (3, 3)

    def test_non_breaking_hyphen(self):
        # U+2011 non-breaking hyphen used on some msx.org pages
        assert _parse_col_label("0\u20111") == (0, 1)

    def test_outer_group_header_returns_none(self):
        assert _parse_col_label("") is None
        assert _parse_col_label("Slot") is None
        assert _parse_col_label("   ") is None


# ── _flatten_table ────────────────────────────────────────────────────────

class TestFlattenTable:
    def test_simple_2x2(self):
        table = _table(
            "<table>"
            "<tr><td>A</td><td>B</td></tr>"
            "<tr><td>C</td><td>D</td></tr>"
            "</table>"
        )
        grid = _flatten_table(table)
        assert grid == [["A", "B"], ["C", "D"]]

    def test_rowspan(self):
        table = _table(
            "<table>"
            "<tr><td rowspan='2'>X</td><td>A</td></tr>"
            "<tr><td>B</td></tr>"
            "</table>"
        )
        grid = _flatten_table(table)
        assert grid[0][0] == "X"
        assert grid[0][1] == "A"
        assert grid[1][0] == "X"   # rowspan carries over
        assert grid[1][1] == "B"

    def test_colspan(self):
        table = _table(
            "<table>"
            "<tr><th colspan='3'>Header</th></tr>"
            "<tr><td>A</td><td>B</td><td>C</td></tr>"
            "</table>"
        )
        grid = _flatten_table(table)
        assert grid[0] == ["Header", "Header", "Header"]
        assert grid[1] == ["A", "B", "C"]

    def test_mixed_rowspan_colspan(self):
        # Corner cell occupies 2 header rows
        table = _table(
            "<table>"
            "<tr><td rowspan='2'></td><th colspan='2'>Slot 0</th></tr>"
            "<tr><th>0-0</th><th>0-1</th></tr>"
            "<tr><th>P3</th><td>MAIN</td><td>SUB</td></tr>"
            "</table>"
        )
        grid = _flatten_table(table)
        # Row 0: corner, 'Slot 0', 'Slot 0'
        assert grid[0][1] == "Slot 0"
        # Row 1: corner (rowspan), '0-0', '0-1'
        assert grid[1][0] == ""
        assert grid[1][1] == "0-0"
        assert grid[1][2] == "0-1"
        # Row 2: 'P3', 'MAIN', 'SUB'
        assert grid[2][1] == "MAIN"
        assert grid[2][2] == "SUB"


# ── _classify_cell_text ───────────────────────────────────────────────────

class TestClassifyCellText:
    def test_blank_returns_none(self):
        assert _classify_cell_text("") is None
        assert _classify_cell_text("   ") is None

    def test_cartridge_slot(self):
        assert _classify_cell_text("Cartridge Slot 1") == _CART_SENTINEL
        assert _classify_cell_text("Cartridge Slot 2") == _CART_SENTINEL
        assert _classify_cell_text("Mini Cartridge Slot") == _CART_SENTINEL
        assert _classify_cell_text("Module Slot") == _CART_SENTINEL
        assert _classify_cell_text("Slot CN904") == _CART_SENTINEL

    def test_expansion_bus(self):
        assert _classify_cell_text("Expansion Bus") == "EXP"

    def test_panasonic_mapper(self):
        assert _classify_cell_text("Panasonic mapper") == "PM"
        assert _classify_cell_text("Panasonic RAM") == "PM"

    def test_memory_mapper(self):
        assert _classify_cell_text("256kB Memory Mapper") == "MM"
        assert _classify_cell_text("Memory Mapper") == "MM"
        assert _classify_cell_text("128kB Memory Mapper") == "MM"
        assert _classify_cell_text("1MB Memory Mapper") == "MM"
        assert _classify_cell_text("4MB Memory Mapper") == "MM"
        # "64kB Memory RAM" — has "memory" + size → MM
        assert _classify_cell_text("64kB Memory RAM") == "MM"

    def test_plain_ram(self):
        assert _classify_cell_text("64kB Plain RAM") == "RAM"
        assert _classify_cell_text("64kB RAM") == "RAM"

    def test_main_rom(self):
        assert _classify_cell_text("Main-ROM") == "MAIN"
        assert _classify_cell_text("Main ROM") == "MAIN"

    def test_sub_rom(self):
        assert _classify_cell_text("Sub-ROM") == "SUB"
        assert _classify_cell_text("Sub ROM") == "SUB"

    def test_disk(self):
        assert _classify_cell_text("Disk ROM") == "DSK"

    def test_msx_music(self):
        assert _classify_cell_text("MSX-Music") == "MUS"
        assert _classify_cell_text("MSX Music") == "MUS"
        assert _classify_cell_text("FM Voicing") == "MUS"

    def test_kanji(self):
        assert _classify_cell_text("Kanji driver") == "KAN"
        assert _classify_cell_text("Kanji driver 1") == "KAN"

    def test_hangul(self):
        assert _classify_cell_text("Hangul driver") == "HAN"

    def test_msx_je(self):
        assert _classify_cell_text("MSX-JE") == "JE"

    def test_modem(self):
        assert _classify_cell_text("MSX Modem ROM") == "MOD"
        assert _classify_cell_text("Modem") == "MOD"

    def test_bunsetsu(self):
        assert _classify_cell_text("Bunsetsu Henkan Jukugo") == "BUN"

    def test_firmware_catchall(self):
        assert _classify_cell_text("Opening ROM") == "FW"
        assert _classify_cell_text("BASIC Kun") == "FW"
        assert _classify_cell_text("Word-Pro 1") == "FW"
        assert _classify_cell_text("Deskpac 1") == "FW"
        assert _classify_cell_text("MSX Jusho") == "FW"
        assert _classify_cell_text("Set-Up RTC") == "FW"
        assert _classify_cell_text("MSX Serial/ Opening ROM") == "FW"

    def test_unknown_returns_none(self):
        assert _classify_cell_text("Something Completely Unknown") is None


# ── parse_msxorg_slotmap ──────────────────────────────────────────────────

def _make_page(slot_map_html: str = "", extra_sections: str = "") -> bytes:
    """Build a minimal msx.org-style wiki HTML page."""
    slot_section = (
        f'<h2><span id="Slot_Map" class="mw-headline">Slot Map</span></h2>'
        f"{slot_map_html}"
    ) if slot_map_html else ""
    return (
        "<html><body>"
        + slot_section
        + extra_sections
        + "</body></html>"
    ).encode()


# Helper: build a minimal but parseable 5-row slot map table.
# Slots: 0=non-exp, 1=non-exp(cart), 2=non-exp, 3-0/1/2/3=expanded
_MINIMAL_5ROW_TABLE = """
<table>
<tr>
  <td></td>
  <th>Slot 0</th><th rowspan="5"></th>
  <th>Slot 1</th><th rowspan="5"></th>
  <th>Slot 2</th><th rowspan="5"></th>
  <th>Slot 3-0</th><th>Slot 3-1</th><th>Slot 3-2</th><th>Slot 3-3</th>
</tr>
<tr>
  <th>Page C000h~FFFFh</th>
  <td rowspan="4">Main-ROM</td>
  <td rowspan="4">Cartridge Slot 1</td>
  <td rowspan="4">256kB Memory Mapper</td>
  <td></td><td></td><td></td><td>Sub-ROM</td>
</tr>
<tr>
  <th>Page 8000h~BFFFh</th>
  <td></td><td>Disk ROM</td><td></td><td></td>
</tr>
<tr>
  <th>Page 4000h~7FFFh</th>
  <td></td><td></td><td></td><td></td>
</tr>
<tr>
  <th>Page 0000h~3FFFh</th>
  <td></td><td></td><td></td><td></td>
</tr>
</table>
"""


class TestParseMsxorgSlotmap:

    def test_no_slot_map_returns_none(self):
        html = b"<html><body><h2>Connections</h2></body></html>"
        assert parse_msxorg_slotmap(html) is None

    def test_heading_without_table_returns_none(self):
        html = (
            b'<html><body>'
            b'<h2><span id="Slot_Map" class="mw-headline">Slot Map</span></h2>'
            b'<p>No table here.</p>'
            b'</body></html>'
        )
        assert parse_msxorg_slotmap(html) is None

    def test_result_has_all_64_keys(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        assert set(result.keys()) == set(_ALL_KEYS)

    def test_nonexpanded_slot_has_absent_subslots_1_to_3(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Slot 0 is non-expanded: sub-slots 1-3 must be ⌧
        for ss in (1, 2, 3):
            for p in range(4):
                assert result[f"slotmap_0_{ss}_{p}"] == _ABSENT, (
                    f"slotmap_0_{ss}_{p} should be ⌧"
                )

    def test_nonexpanded_slot_subslot0_has_device(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Slot 0, sub-slot 0: Main-ROM spans all 4 pages → MAIN
        for p in range(4):
            assert result[f"slotmap_0_0_{p}"] == "MAIN"

    def test_cartridge_slot_gets_cs1(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Slot 1 is non-expanded, content = "Cartridge Slot 1" → CS1 all pages
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"

    def test_memory_mapper_cell(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        for p in range(4):
            assert result[f"slotmap_2_0_{p}"] == "MM"

    def test_expanded_slot3_devices(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # "Sub-ROM" appears only on page 3 (C000h) in sub-slot 3
        assert result["slotmap_3_3_3"] == "SUB"
        # "Disk ROM" appears on page 2 (8000h) in sub-slot 1
        assert result["slotmap_3_1_2"] == "DSK"

    def test_expanded_slot3_empty_pages_are_bullet(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Slot 3-0 has no content in any page → all •
        for p in range(4):
            assert result[f"slotmap_3_0_{p}"] == _EMPTY_PAGE

    def test_multi_slot_map_uses_first(self):
        """Pages with multiple Slot_Map headings (e.g. 1chipMSX) use the first."""
        second_table = """
        <h2><span id="Slot_Map_for_the_upgraded_configuration"
                  class="mw-headline">Slot Map (upgraded)</span></h2>
        <table>
        <tr>
          <td></td><th>Slot 0</th>
        </tr>
        <tr>
          <th>Page C000h~FFFFh</th><td>Disk ROM</td>
        </tr>
        <tr><th>Page 8000h~BFFFh</th><td></td></tr>
        <tr><th>Page 4000h~7FFFh</th><td></td></tr>
        <tr><th>Page 0000h~3FFFh</th><td></td></tr>
        </table>
        """
        html = _make_page(_MINIMAL_5ROW_TABLE, extra_sections=second_table)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # First table has MAIN in slot 0; second has DSK — first wins
        assert result["slotmap_0_0_3"] == "MAIN"


# ── Integration: parse_slotmap_from_soup ─────────────────────────────────

class TestParseSlotmapFromSoup:

    def test_returns_none_when_no_heading(self):
        soup = BeautifulSoup(b"<html><body></body></html>", "lxml")
        assert parse_slotmap_from_soup(soup) is None

    def test_returns_dict_when_heading_and_table_present(self):
        html = _make_page(_MINIMAL_5ROW_TABLE)
        soup = BeautifulSoup(html, "lxml")
        result = parse_slotmap_from_soup(soup)
        assert result is not None
        assert len(result) == 64

    def test_result_matches_parse_msxorg_slotmap(self):
        """parse_slotmap_from_soup and parse_msxorg_slotmap must agree."""
        html = _make_page(_MINIMAL_5ROW_TABLE)
        from_soup = parse_slotmap_from_soup(BeautifulSoup(html, "lxml"))
        from_bytes = parse_msxorg_slotmap(html)
        assert from_soup == from_bytes


# ── 6-row table (expanded slot 0) ────────────────────────────────────────

_SIX_ROW_TABLE = """
<table>
<tr>
  <td rowspan="2"></td>
  <th colspan="4">Slot</th>
  <td rowspan="6"></td>
  <th rowspan="6"></th>
  <td rowspan="6"></td>
  <th rowspan="6"></th>
  <td rowspan="6"></td>
  <th colspan="4">Slot</th>
</tr>
<tr>
  <th>0-0</th><th>0&#x2011;1</th><th>0-2</th><th>0-3</th>
  <th rowspan="5"></th><th>Slot 1</th>
  <th rowspan="5"></th><th>Slot 2</th>
  <th rowspan="5"></th>
  <th>3-0</th><th>3-1</th><th>3-2</th><th>3-3</th>
</tr>
<tr>
  <th>Page C000h~FFFFh</th>
  <td></td><td></td><td></td><td></td>
  <td rowspan="4">Cartridge Slot 1</td>
  <td rowspan="4">256kB Memory Mapper</td>
  <td></td><td>Kanji driver</td><td rowspan="4">64kB RAM</td><td></td>
</tr>
<tr>
  <th>Page 8000h~BFFFh</th>
  <td></td><td></td><td></td><td></td>
  <td></td><td></td><td></td>
</tr>
<tr>
  <th>Page 4000h~7FFFh</th>
  <td rowspan="2">Main-ROM</td><td></td><td>MSX-Music</td><td>Disk ROM</td>
  <td></td><td></td><td></td>
</tr>
<tr>
  <th>Page 0000h~3FFFh</th>
  <td>Sub-ROM</td><td></td><td></td>
  <td></td><td></td><td></td>
</tr>
</table>
"""


class TestSixRowTable:

    def test_expanded_slot0_subslots_all_present(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Expanded slot 0 → all 4 sub-slots should be • (no devices) or filled
        for ss in range(4):
            for p in range(4):
                assert result[f"slotmap_0_{ss}_{p}"] != _ABSENT

    def test_main_rom_in_slot0_ss0(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Main-ROM spans pages 0 and 1 (4000h and 0000h) in sub-slot 0
        assert result["slotmap_0_0_1"] == "MAIN"   # page 1 (4000h)
        assert result["slotmap_0_0_0"] == "MAIN"   # page 0 (0000h)

    def test_subrom_in_slot0_ss1(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        assert result["slotmap_0_1_0"] == "SUB"     # page 0 (0000h)

    def test_msx_music_in_slot0_ss2(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        assert result["slotmap_0_2_1"] == "MUS"     # page 1 (4000h)

    def test_disk_in_slot0_ss3(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        assert result["slotmap_0_3_1"] == "DSK"     # page 1 (4000h)

    def test_cartridge_slot1_in_slot1(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"

    def test_mm_in_slot2(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        for p in range(4):
            assert result[f"slotmap_2_0_{p}"] == "MM"

    def test_kanji_in_slot3_1(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Kanji driver appears only on page 3 (C000h) in slot 3-1
        assert result["slotmap_3_1_3"] == "KAN"

    def test_slot3_subslots_1_to_3_not_absent(self):
        html = _make_page(_SIX_ROW_TABLE)
        result = parse_msxorg_slotmap(html)
        assert result is not None
        # Slot 3 is expanded — no sub-slot should be ⌧
        for ss in range(4):
            for p in range(4):
                assert result[f"slotmap_3_{ss}_{p}"] != _ABSENT

"""Unit tests for scraper/slotmap.py — slot map extractor."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from scraper.slotmap import (
    _pages_for_mem,
    extract_slotmap,
    load_sha1_index,
    match_lut,
)

# ---------------------------------------------------------------------------
# LUT fixture (subset of the real slotmap-lut.json)
# ---------------------------------------------------------------------------

LUT_RULES: list[dict] = [
    {"element": "ROM", "id_pattern": "MSX BIOS with BASIC ROM|Main ROM", "abbr": "MAIN", "tooltip": "MSX BIOS with BASIC ROM"},
    {"element": "ROM", "id_pattern": "Sub.ROM", "abbr": "SUB", "tooltip": "Sub ROM"},
    {"element": "ROM", "id_pattern": "Kanji", "abbr": "KNJ", "tooltip": "Kanji driver"},
    {"element": "ROM", "id_pattern": "MSX-JE", "abbr": "JE", "tooltip": "MSX-JE"},
    {"element": "ROM", "id_pattern": "Firmware|Arabic ROM|SWP ROM|.*Cockpit.*|Desk Pac.*", "abbr": "FW", "tooltip": "Firmware"},
    {"element": "WD2793|TC8566AF", "id_pattern": None, "abbr": "DSK", "tooltip": "Disk ROM"},
    {"element": "MSX-MUSIC|FMPAC", "id_pattern": None, "abbr": "MUS", "tooltip": "MSX Music"},
    {"element": "MSX-RS232", "id_pattern": None, "abbr": "RS2", "tooltip": "RS-232C Interface"},
    {"element": "MemoryMapper", "id_pattern": None, "abbr": "MM", "tooltip": "Memory Mapper"},
    {"element": "PanasonicRAM", "id_pattern": None, "abbr": "PM", "tooltip": "Panasonic Mapper"},
    {"element": "RAM", "id_pattern": None, "abbr": "RAM", "tooltip": "RAM (no memory mapper)"},
    {"element": "__expansion_bus__", "id_pattern": None, "abbr": "EXP", "tooltip": "Expansion Bus"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS1",  "tooltip": "Cartridge slot 1"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS2",  "tooltip": "Cartridge slot 2"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS3",  "tooltip": "Cartridge slot 3"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS4",  "tooltip": "Cartridge slot 4"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS1!", "tooltip": "Cartridge slot 1 (in subslot \u2014 non-standard)"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS2!", "tooltip": "Cartridge slot 2 (in subslot \u2014 non-standard)"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS3!", "tooltip": "Cartridge slot 3 (in subslot \u2014 non-standard)"},
    {"element": "__cartridge__", "id_pattern": None, "abbr": "CS4!", "tooltip": "Cartridge slot 4 (in subslot \u2014 non-standard)"},
    {"element": "__sentinel__", "id_pattern": None, "abbr": "\u2327", "tooltip": "Sub-slot absent (not expanded)"},
]


# ---------------------------------------------------------------------------
# Helper: build root from XML string
# ---------------------------------------------------------------------------

def _root(xml: str) -> etree._Element:
    parser = etree.XMLParser(recover=True)
    return etree.fromstring(xml.encode(), parser=parser)


# ---------------------------------------------------------------------------
# _pages_for_mem
# ---------------------------------------------------------------------------

class TestPagesForMem:
    def test_full_slot_covers_all_pages(self):
        assert _pages_for_mem(0x0000, 0x10000) == [0, 1, 2, 3]

    def test_page_0_only(self):
        assert _pages_for_mem(0x0000, 0x4000) == [0]

    def test_page_1_only(self):
        assert _pages_for_mem(0x4000, 0x4000) == [1]

    def test_pages_1_and_2(self):
        assert _pages_for_mem(0x4000, 0x8000) == [1, 2]

    def test_8kb_straddling_page_boundary(self):
        # 0x2000-0x5FFF covers pages 0 and 1
        assert _pages_for_mem(0x2000, 0x4000) == [0, 1]

    def test_small_range_in_page_3(self):
        assert _pages_for_mem(0xC000, 0x4000) == [3]

    def test_zero_size_covers_nothing(self):
        assert _pages_for_mem(0x0000, 0) == []


# ---------------------------------------------------------------------------
# match_lut
# ---------------------------------------------------------------------------

class TestMatchLut:
    def test_rom_main_bios_matched(self):
        assert match_lut("ROM", "MSX BIOS with BASIC ROM", LUT_RULES) == "MAIN"

    def test_rom_sub_rom_matched(self):
        assert match_lut("ROM", "MSX Sub ROM", LUT_RULES) == "SUB"

    def test_rom_kanji_matched(self):
        assert match_lut("ROM", "Kanji ROM", LUT_RULES) == "KNJ"

    def test_rom_msx_je_matched(self):
        assert match_lut("ROM", "HB-F1XV MSX-JE", LUT_RULES) == "JE"

    def test_wD2793_matched(self):
        assert match_lut("WD2793", "Memory Mapped FDC", LUT_RULES) == "DSK"

    def test_tc8566af_matched(self):
        assert match_lut("TC8566AF", None, LUT_RULES) == "DSK"

    def test_msx_music_matched(self):
        assert match_lut("MSX-MUSIC", "MSX Music", LUT_RULES) == "MUS"

    def test_fmpac_matched(self):
        assert match_lut("FMPAC", None, LUT_RULES) == "MUS"

    def test_memory_mapper_matched(self):
        assert match_lut("MemoryMapper", "Main RAM", LUT_RULES) == "MM"

    def test_panasonic_ram_matched(self):
        assert match_lut("PanasonicRAM", "Main RAM", LUT_RULES) == "PM"

    def test_ram_matched(self):
        assert match_lut("RAM", "RAM", LUT_RULES) == "RAM"

    def test_unknown_element_returns_none(self):
        assert match_lut("FutureTech", "Something", LUT_RULES) is None

    def test_secondary_never_matched(self):
        # "secondary" is structural and must be skipped
        assert match_lut("secondary", None, LUT_RULES) is None

    def test_sentinel_never_matched(self):
        assert match_lut("__sentinel__", None, LUT_RULES) is None

    def test_cartridge_never_matched(self):
        assert match_lut("__cartridge__", None, LUT_RULES) is None

    def test_id_pattern_case_insensitive(self):
        assert match_lut("ROM", "msx bios with basic rom", LUT_RULES) == "MAIN"

    def test_first_rule_wins_when_multiple_match(self):
        # "MSX BIOS with BASIC ROM" matches both Main ROM pattern and MAIN pattern — MAIN wins first
        assert match_lut("ROM", "MSX BIOS with BASIC ROM", LUT_RULES) == "MAIN"


# ---------------------------------------------------------------------------
# extract_slotmap — core extractor (Chunk 1, no mirrors)
# ---------------------------------------------------------------------------

# Reference XML: Sony HB-F1XV-like structure
HB_F1XV_XML = """
<msxconfig>
  <info>
    <manufacturer>Sony</manufacturer>
    <code>HB-F1XV</code>
    <type>MSX2+</type>
  </info>
  <devices>
    <primary slot="0">
      <secondary slot="0">
        <ROM id="MSX BIOS with BASIC ROM">
          <mem base="0x0000" size="0x8000"/>
        </ROM>
      </secondary>
      <secondary slot="1"/>
      <secondary slot="2"/>
      <secondary slot="3">
        <ROM id="HB-F1XV MSX-JE">
          <mem base="0x0000" size="0x10000"/>
        </ROM>
      </secondary>
    </primary>
    <primary external="true" slot="1"/>
    <primary external="true" slot="2"/>
    <primary slot="3">
      <secondary slot="0">
        <MemoryMapper id="Main RAM">
          <mem base="0x0000" size="0x10000"/>
        </MemoryMapper>
      </secondary>
      <secondary slot="1">
        <ROM id="MSX Sub ROM">
          <mem base="0x0000" size="0x4000"/>
        </ROM>
        <ROM id="MSX Kanji Driver with BASIC">
          <mem base="0x4000" size="0x8000"/>
        </ROM>
      </secondary>
      <secondary slot="2">
        <WD2793 id="Memory Mapped FDC">
          <mem base="0x4000" size="0x4000"/>
        </WD2793>
      </secondary>
      <secondary slot="3">
        <MSX-MUSIC id="MSX Music">
          <mem base="0x4000" size="0x4000"/>
        </MSX-MUSIC>
      </secondary>
    </primary>
  </devices>
</msxconfig>
"""


class TestExtractSlotmapAllKeys:
    def test_all_64_keys_present(self):
        root = _root(HB_F1XV_XML)
        result = extract_slotmap(root, LUT_RULES)
        assert len(result) == 64
        for ms in range(4):
            for ss in range(4):
                for p in range(4):
                    assert f"slotmap_{ms}_{ss}_{p}" in result

    def test_no_devices_returns_all_absent(self):
        root = _root("<msxconfig><info/></msxconfig>")
        result = extract_slotmap(root, LUT_RULES)
        assert len(result) == 64
        assert all(v == "\u2327" for v in result.values())


class TestExtractSlotmapHBF1XV:
    """Verify the Sony HB-F1XV reference layout."""

    def setup_method(self):
        self.result = extract_slotmap(_root(HB_F1XV_XML), LUT_RULES)

    # Slot 0-0: MAIN in pages 0-1; pages 2-3 empty (no device in expanded slot)
    def test_slot_0_0_page_0_main(self):
        assert self.result["slotmap_0_0_0"] == "MAIN"

    def test_slot_0_0_page_1_main(self):
        assert self.result["slotmap_0_0_1"] == "MAIN"

    def test_slot_0_0_pages_2_3_empty(self):
        assert self.result["slotmap_0_0_2"] == "\u2022"
        assert self.result["slotmap_0_0_3"] == "\u2022"

    # Slot 0-1, 0-2: explicitly empty secondaries → EXP (physical expansion connector)
    def test_slot_0_1_all_exp(self):
        for p in range(4):
            assert self.result[f"slotmap_0_1_{p}"] == "EXP"

    def test_slot_0_2_all_exp(self):
        for p in range(4):
            assert self.result[f"slotmap_0_2_{p}"] == "EXP"

    # Slot 0-3: JE covers all 4 pages (0x0000, 0x10000)
    def test_slot_0_3_je_all_pages(self):
        for p in range(4):
            assert self.result[f"slotmap_0_3_{p}"] == "JE"

    # Slot 1: external → CS1 in sub-slot 0; SS1-3 ⌧ (absent, no secondary expansion)
    def test_slot_1_cartridge(self):
        for p in range(4):
            assert self.result[f"slotmap_1_0_{p}"] == "CS1"
        for ss in range(1, 4):
            for p in range(4):
                assert self.result[f"slotmap_1_{ss}_{p}"] == "\u2327"

    # Slot 2: external → CS2
    def test_slot_2_cartridge(self):
        for p in range(4):
            assert self.result[f"slotmap_2_0_{p}"] == "CS2"

    # Slot 3-0: MM covers all 4 pages
    def test_slot_3_0_mm(self):
        for p in range(4):
            assert self.result[f"slotmap_3_0_{p}"] == "MM"

    # Slot 3-1: SUB in page 0, KNJ in pages 1-2
    def test_slot_3_1_sub_page_0(self):
        assert self.result["slotmap_3_1_0"] == "SUB"

    def test_slot_3_1_knj_pages_1_2(self):
        assert self.result["slotmap_3_1_1"] == "KNJ"
        assert self.result["slotmap_3_1_2"] == "KNJ"

    def test_slot_3_1_page_3_empty(self):
        assert self.result["slotmap_3_1_3"] == "\u2022"

    # Slot 3-2: DSK in page 1; other pages empty (expanded slot, no device)
    def test_slot_3_2_dsk_page_1(self):
        assert self.result["slotmap_3_2_1"] == "DSK"
        assert self.result["slotmap_3_2_0"] == "\u2022"
        assert self.result["slotmap_3_2_2"] == "\u2022"
        assert self.result["slotmap_3_2_3"] == "\u2022"

    # Slot 3-3: MUS in page 1; other pages empty (expanded slot, no device)
    def test_slot_3_3_mus_page_1(self):
        assert self.result["slotmap_3_3_1"] == "MUS"
        assert self.result["slotmap_3_3_0"] == "\u2022"
        assert self.result["slotmap_3_3_2"] == "\u2022"
        assert self.result["slotmap_3_3_3"] == "\u2022"


class TestExtractSlotmapEdgeCases:
    def test_non_expanded_primary_classifies_direct_children(self):
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        assert result["slotmap_0_0_0"] == "MAIN"
        assert result["slotmap_0_0_1"] == "MAIN"
        # SS0 pages 2-3: • (non-expanded, page is real but no device)
        assert result["slotmap_0_0_2"] == "\u2022"
        assert result["slotmap_0_0_3"] == "\u2022"
        # Sub-slots 1-3: ⌧ (absent — no secondary expansion)
        for ss in range(1, 4):
            for p in range(4):
                assert result[f"slotmap_0_{ss}_{p}"] == "\u2327"

    def test_empty_secondary_slot_is_exp(self):
        # Explicitly-empty secondary (no children) → EXP (expansion connector).
        # Secondaries 2 and 3 are absent from XML → filled implicitly → •.
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0"/>
            <secondary slot="1">
              <MemoryMapper id="Main RAM"><mem base="0x0000" size="0x10000"/></MemoryMapper>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Explicitly-empty secondary 0 → EXP
        for p in range(4):
            assert result[f"slotmap_0_0_{p}"] == "EXP"
        # Secondary 1 has a device → MM
        for p in range(4):
            assert result[f"slotmap_0_1_{p}"] == "MM"
        # Secondaries 2 and 3 absent from XML → implicitly filled → •
        for ss in (2, 3):
            for p in range(4):
                assert result[f"slotmap_0_{ss}_{p}"] == "\u2022"

    def test_unknown_device_warns_and_uses_tag(self, capsys):
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <FutureTech id="Some Widget">
              <mem base="0x0000" size="0x4000"/>
            </FutureTech>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES, filename="test.xml")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "FutureTech" in captured.err
        assert result["slotmap_0_0_0"] == "FutureTech"

    def test_overlap_warns_and_first_wins(self, capsys):
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
            <MemoryMapper id="Main RAM">
              <mem base="0x0000" size="0x4000"/>
            </MemoryMapper>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES, filename="test.xml")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "overlap" in captured.err.lower()
        # First device (MAIN) wins
        assert result["slotmap_0_0_0"] == "MAIN"

    def test_device_without_mem_is_skipped(self):
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM"/>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Device skipped (no mem); non-expanded primary: SS0 all •, SS1-3 ⌧
        for p in range(4):
            assert result[f"slotmap_0_0_{p}"] == "\u2022"
        for ss in range(1, 4):
            for p in range(4):
                assert result[f"slotmap_0_{ss}_{p}"] == "\u2327"

    def test_primary_without_slot_attr_skipped(self):
        xml = """
        <msxconfig><devices>
          <primary>
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Primary skipped entirely — all 64 cells remain ⌧
        assert all(v == "\u2327" for v in result.values())

    def test_explicit_empty_secondary_is_exp_not_empty_page(self):
        """Regression: Pioneer UC-V102 pattern — explicitly-listed empty secondary
        slots represent physical expansion connectors, not merely 'nothing mapped'.
        They must emit EXP rather than •.

        Pattern:
          <secondary slot="0"> <WD2793...> </secondary>   ← device present → DSK
          <secondary slot="1"/>  <!-- Only available internally... -->   → EXP
          <secondary slot="2"/>  <!-- Only available internally... -->   → EXP
          <secondary slot="3"/>  <!-- Only available internally... -->   → EXP
        """
        xml = """
        <msxconfig><devices>
          <primary slot="3">
            <secondary slot="0">
              <WD2793 id="Memory Mapped FDC">
                <mem base="0x4000" size="0x4000"/>
              </WD2793>
            </secondary>
            <secondary slot="1"/>
            <secondary slot="2"/>
            <secondary slot="3"/>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Secondary 0 has a device
        assert result["slotmap_3_0_1"] == "DSK"
        # Explicitly-empty secondaries → EXP
        for ss in (1, 2, 3):
            for p in range(4):
                assert result[f"slotmap_3_{ss}_{p}"] == "EXP", \
                    f"slotmap_3_{ss}_{p}: expected EXP, got {result[f'slotmap_3_{ss}_{p}']!r}"

    def test_cartridge_numbering_is_sequential_not_slot_index(self):
        """CS numbering starts at 1 and increments per cartridge found, regardless of slot index."""
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
          </primary>
          <primary external="true" slot="3"/>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Cartridge at slot index 3 → CS1 (first cartridge found)
        for p in range(4):
            assert result[f"slotmap_3_0_{p}"] == "CS1"

    def test_cartridge_numbering_multiple_non_contiguous(self):
        """Two cartridge slots at indices 0 and 3 → CS1 and CS2."""
        xml = """
        <msxconfig><devices>
          <primary external="true" slot="0"/>
          <primary slot="1">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
          </primary>
          <primary external="true" slot="3"/>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        for p in range(4):
            assert result[f"slotmap_0_0_{p}"] == "CS1"
        for p in range(4):
            assert result[f"slotmap_3_0_{p}"] == "CS2"


# ---------------------------------------------------------------------------
# Mirror detection — Method 1: rom_visibility (T-025)
# ---------------------------------------------------------------------------

class TestMirrorMethod1RomVisibility:
    def test_pages_outside_visibility_become_mirror(self):
        # WD2793 with mem=full slot but rom_visibility=page 1 only
        xml = """
        <msxconfig><devices>
          <primary slot="3">
            <secondary slot="2">
              <WD2793 id="Memory Mapped FDC">
                <mem base="0x0000" size="0x10000"/>
                <rom_visibility base="0x4000" size="0x4000"/>
              </WD2793>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        assert result["slotmap_3_2_1"] == "DSK"      # visible page
        assert result["slotmap_3_2_0"] == "DSK*"     # mirror
        assert result["slotmap_3_2_2"] == "DSK*"     # mirror
        assert result["slotmap_3_2_3"] == "DSK*"     # mirror

    def test_full_visibility_no_mirrors(self):
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <mem base="0x0000" size="0x8000"/>
                <rom_visibility base="0x0000" size="0x8000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        assert result["slotmap_0_0_0"] == "MAIN"
        assert result["slotmap_0_0_1"] == "MAIN"
        assert result["slotmap_0_0_2"] == "\u2022"  # expanded slot, no device on page 2


# ---------------------------------------------------------------------------
# Mirror detection — Method 2: ROM file size (T-026)
# ---------------------------------------------------------------------------

class TestMirrorMethod2RomFileSize:
    def _make_sha1_index(self, sha1: str, rel_path: str) -> dict[str, Path]:
        return {sha1.lower(): Path(rel_path)}

    def test_file_smaller_than_mem_produces_mirror_pages(self, tmp_path):
        # 16 KB file mapped to 64 KB (4 pages) → pages 1-3 are mirrors
        rom_file = tmp_path / "sub.rom"
        rom_file.write_bytes(b"\x00" * 0x4000)  # 16 KB

        sha1 = "aabbcc"
        sha1_index = {sha1: Path("sub.rom")}

        xml = f"""
        <msxconfig><devices>
          <primary slot="3">
            <secondary slot="0">
              <ROM id="MSX Sub ROM">
                <rom><sha1>{sha1}</sha1></rom>
                <mem base="0x0000" size="0x10000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(
            _root(xml), LUT_RULES,
            sha1_index=sha1_index,
            systemroms_root=tmp_path,
        )
        assert result["slotmap_3_0_0"] == "SUB"
        assert result["slotmap_3_0_1"] == "SUB*"
        assert result["slotmap_3_0_2"] == "SUB*"
        assert result["slotmap_3_0_3"] == "SUB*"

    def test_file_equal_to_mem_no_mirrors(self, tmp_path):
        rom_file = tmp_path / "main.rom"
        rom_file.write_bytes(b"\x00" * 0x8000)  # 32 KB = mem size

        sha1 = "aabbcc"
        sha1_index = {sha1: Path("main.rom")}

        xml = f"""
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <rom><sha1>{sha1}</sha1></rom>
                <mem base="0x0000" size="0x8000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(
            _root(xml), LUT_RULES,
            sha1_index=sha1_index,
            systemroms_root=tmp_path,
        )
        assert result["slotmap_0_0_0"] == "MAIN"
        assert result["slotmap_0_0_1"] == "MAIN"
        assert result["slotmap_0_0_2"] == "\u2022"  # expanded slot, no device on page 2

    def test_sha1_not_found_warns_and_skips(self, capsys, tmp_path):
        sha1_index = {}  # empty — SHA1 won't be found
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <rom><sha1>deadbeef</sha1></rom>
                <mem base="0x0000" size="0x10000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(
            _root(xml), LUT_RULES, filename="test.xml",
            sha1_index=sha1_index,
            systemroms_root=tmp_path,
        )
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "SHA1 not found" in captured.err
        # Cells still filled with plain abbr (no mirror annotation)
        assert result["slotmap_0_0_0"] == "MAIN"

    def test_missing_systemroms_no_exception(self):
        # sha1_index is None (systemroms not available)
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <rom><sha1>aabbcc</sha1></rom>
                <mem base="0x0000" size="0x10000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES, sha1_index=None)
        # No exception; plain abbr (no mirror)
        assert result["slotmap_0_0_0"] == "MAIN"

    def test_rom_file_absent_from_disk_warns_and_skips(self, capsys, tmp_path):
        sha1_index = {"aabbcc": Path("missing.rom")}
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <rom><sha1>aabbcc</sha1></rom>
                <mem base="0x0000" size="0x10000"/>
              </ROM>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(
            _root(xml), LUT_RULES, filename="test.xml",
            sha1_index=sha1_index,
            systemroms_root=tmp_path,
        )
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "not found" in captured.err.lower()
        assert result["slotmap_0_0_0"] == "MAIN"

    def test_fdc_device_with_embedded_rom_smaller_than_mem_produces_mirror(self, tmp_path):
        # WD2793 with a 0x4000 (16 KB) ROM mapped to mem size 0x8000 (2 pages).
        # Reproduces the National FS-5000F2 disk controller layout:
        #   page 1 (0x4000-0x7FFF) — real ROM content → DSK
        #   page 2 (0x8000-0xBFFF) — mirror (ROM file exhausted) → DSK*
        rom_file = tmp_path / "disk.rom"
        rom_file.write_bytes(b"\x00" * 0x4000)  # 16 KB

        sha1 = "cafebabe"
        sha1_index = {sha1: Path("disk.rom")}

        xml = f"""
        <msxconfig><devices>
          <primary slot="3">
            <secondary slot="3">
              <WD2793 id="Memory Mapped FDC">
                <connectionstyle>National</connectionstyle>
                <drives>2</drives>
                <rom>
                  <filename>disk.rom</filename>
                  <sha1>{sha1}</sha1>
                </rom>
                <mem base="0x4000" size="0x8000"/>
              </WD2793>
            </secondary>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(
            _root(xml), LUT_RULES,
            sha1_index=sha1_index,
            systemroms_root=tmp_path,
        )
        assert result["slotmap_3_3_1"] == "DSK"   # page 1: real ROM
        assert result["slotmap_3_3_2"] == "DSK*"  # page 2: mirror


# ---------------------------------------------------------------------------
# Mirror detection — Method 3: <Mirror> element two-pass (T-027)
# ---------------------------------------------------------------------------

class TestMirrorMethod3Element:
    def test_mirror_element_annotates_host_page(self):
        # Sony HB-10P-like: slot 0 page 3 mirrors RAM from slot 3
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
            <Mirror id="Main RAM mirror">
              <mem base="0xc000" size="0x4000"/>
              <ps>3</ps>
            </Mirror>
          </primary>
          <primary slot="3">
            <RAM id="Main RAM">
              <mem base="0x0000" size="0x10000"/>
            </RAM>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        assert result["slotmap_0_0_0"] == "MAIN"
        assert result["slotmap_0_0_1"] == "MAIN"
        assert result["slotmap_0_0_2"] == "\u2022"  # non-expanded primary, no device on page 2
        assert result["slotmap_0_0_3"] == "RAM*"
        # Source slot intact
        for p in range(4):
            assert result[f"slotmap_3_0_{p}"] == "RAM"

    def test_mirror_in_secondary_annotates_correct_host(self):
        # Victor HC-95A-like: Mirror in slot 0-1 pointing to ps=3
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <secondary slot="0">
              <ROM id="MSX BIOS with BASIC ROM">
                <mem base="0x0000" size="0x8000"/>
              </ROM>
            </secondary>
            <secondary slot="1">
              <MSX-RS232 id="MSX RS-232">
                <mem base="0x4000" size="0x3FF8"/>
              </MSX-RS232>
              <Mirror id="FDC registers">
                <mem base="0x7FF8" size="0x8"/>
                <ps>3</ps>
              </Mirror>
            </secondary>
          </primary>
          <primary slot="3">
            <WD2793 id="Memory Mapped FDC">
              <mem base="0x4000" size="0x4000"/>
            </WD2793>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES)
        # Mirror is at 0x7FF8 in slot 0-1 (page 1 range), origin is DSK from slot 3
        assert result["slotmap_0_1_1"] == "DSK*"
        # RS-232 also in page 1
        assert result["slotmap_3_0_1"] == "DSK"

    def test_mirror_with_unknown_origin_warns_and_skips(self, capsys):
        # Mirror pointing to a slot that has no classified devices
        xml = """
        <msxconfig><devices>
          <primary slot="0">
            <ROM id="MSX BIOS with BASIC ROM">
              <mem base="0x0000" size="0x8000"/>
            </ROM>
            <Mirror id="ghost mirror">
              <mem base="0xc000" size="0x4000"/>
              <ps>2</ps>
              <ss>3</ss>
            </Mirror>
          </primary>
        </devices></msxconfig>
        """
        result = extract_slotmap(_root(xml), LUT_RULES, filename="test.xml")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "Mirror origin" in captured.err
        # Page 3 in slot 0: • (mirror skipped, non-expanded primary, no device)
        assert result["slotmap_0_0_3"] == "\u2022"


# ---------------------------------------------------------------------------
# load_sha1_index
# ---------------------------------------------------------------------------

class TestLoadSha1Index:
    def test_loads_correctly(self, tmp_path):
        index_file = tmp_path / "all_sha1s.txt"
        index_file.write_text(
            "aabbcc1122  ./sony/main.rom\n"
            "ddeeff3344  ./philips/sub.rom\n"
        )
        result = load_sha1_index(index_file)
        assert result["aabbcc1122"] == Path("sony/main.rom")
        assert result["ddeeff3344"] == Path("philips/sub.rom")

    def test_none_path_returns_empty(self):
        assert load_sha1_index(None) == {}

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_sha1_index(tmp_path / "missing.txt") == {}

    def test_sha1_keys_lowercased(self, tmp_path):
        index_file = tmp_path / "all_sha1s.txt"
        index_file.write_text("AABBCC  ./some.rom\n")
        result = load_sha1_index(index_file)
        assert "aabbcc" in result

    def test_leading_dot_slash_stripped(self, tmp_path):
        index_file = tmp_path / "all_sha1s.txt"
        index_file.write_text("aabbcc  ./subdir/file.rom\n")
        result = load_sha1_index(index_file)
        assert result["aabbcc"] == Path("subdir/file.rom")


# ---------------------------------------------------------------------------
# ToshibaTCX-200x transparent wrapper
# ---------------------------------------------------------------------------

class TestToshibaTCX200xWrapper:
    """ToshibaTCX-200x compound device with <window>-based sub-devices (HX-33/HX-34).

    The wrapper's <mem base="0x4000" size="0x8000"/> spans pages 1-2.
    Inner ROMs use <window size> for sequential packing within that range:
      rs232  (window size 0x4000 = 1 page) → page 1
      wordpro (window size 0x10000, clamped) → page 2
    """

    _XML = """\
<msxconfig>
  <devices>
    <primary slot="3">
      <secondary slot="3">
        <ToshibaTCX-200x id="Toshiba TCX-2001/2002">
          <rom id="rs232">
            <window base="0xC000" size="0x4000"/>
          </rom>
          <rom id="wordpro">
            <window base="0x10000" size="0x10000"/>
          </rom>
          <mem base="0x4000" size="0x8000"/>
        </ToshibaTCX-200x>
      </secondary>
    </primary>
  </devices>
</msxconfig>"""

    def _slotmap(self) -> dict:
        root = _root(self._XML)
        return extract_slotmap(root, LUT_RULES, filename="Toshiba_HX-33.xml")

    def test_rs232_on_page1(self):
        sm = self._slotmap()
        # First child packed at wrapper base 0x4000 → page 1
        # <rom id="rs232"> normalised to ROM; no test-LUT match → raw "ROM"
        assert sm["slotmap_3_3_1"] == "ROM"

    def test_wordpro_on_page2(self):
        sm = self._slotmap()
        # Second child packed at 0x8000 (after rs232's 0x4000 window) → page 2
        # <rom id="wordpro"> normalised to ROM; no test-LUT match → raw "ROM"
        assert sm["slotmap_3_3_2"] == "ROM"

    def test_page0_empty(self):
        sm = self._slotmap()
        # Wrapper starts at 0x4000 — page 0 (0x0000-0x3FFF) is unmapped
        assert sm["slotmap_3_3_0"] == "\u2022"

    def test_page3_empty(self):
        sm = self._slotmap()
        # Wrapper ends at 0xBFFF — page 3 (0xC000-0xFFFF) is unmapped
        assert sm["slotmap_3_3_3"] == "\u2022"

    def test_wrapper_itself_not_classified_as_device(self):
        """The ToshibaTCX-200x element must not appear as a cell value."""
        sm = self._slotmap()
        for v in sm.values():
            assert "ToshibaTCX" not in (v or "")

    def test_absent_subslots_remain_absent(self):
        sm = self._slotmap()
        # Sub-slots 0, 1, 2 of ms=3 are not in XML but slot is expanded
        for ss in (0, 1, 2):
            for p in range(4):
                assert sm[f"slotmap_3_{ss}_{p}"] == "\u2022"


# ---------------------------------------------------------------------------
# Cartridge slots in subslots (non-standard, CS{N}! suffix)
# ---------------------------------------------------------------------------

class TestSubslotCartridge:
    """secondary external='true' inside an expanded primary → CS{N}! with ! suffix."""

    _XML = """\
<msxconfig>
  <devices>
    <primary slot="0">
      <secondary external="true" slot="0"/>
      <secondary external="true" slot="1"/>
    </primary>
    <primary external="true" slot="1"/>
  </devices>
</msxconfig>"""

    def _slotmap(self):
        root = _root(self._XML)
        return extract_slotmap(root, LUT_RULES)

    def test_subslot_cartridge_gets_bang_suffix(self):
        """secondary external='true' produces CS{N}! not CS{N}."""
        sm = self._slotmap()
        for p in range(4):
            assert sm[f"slotmap_0_0_{p}"] == "CS1!"
            assert sm[f"slotmap_0_1_{p}"] == "CS2!"

    def test_primary_cartridge_after_subslot_carts_numbered_correctly(self):
        """Primary external slot gets sequential CS{N} continuing from subslot count."""
        sm = self._slotmap()
        for p in range(4):
            assert sm[f"slotmap_1_0_{p}"] == "CS3"

    def test_subslot_cartridge_not_absent(self):
        """Subslot cartridge cells must not be ⌧ or absent."""
        sm = self._slotmap()
        for p in range(4):
            assert sm[f"slotmap_0_0_{p}"] not in ("\u2327", None)

    def test_mixed_expanded_primary_with_subslot_carts(self):
        """Expanded primary can have a mix of external and internal secondaries."""
        xml = """\
<msxconfig><devices>
  <primary slot="0">
    <secondary external="true" slot="0"/>
    <secondary slot="1">
      <MemoryMapper id="Main RAM"><size>512</size><mem base="0x0000" size="0x10000"/></MemoryMapper>
    </secondary>
  </primary>
</devices></msxconfig>"""
        root = _root(xml)
        sm = extract_slotmap(root, LUT_RULES)
        for p in range(4):
            assert sm[f"slotmap_0_0_{p}"] == "CS1!"
        assert sm["slotmap_0_1_0"] == "MM"

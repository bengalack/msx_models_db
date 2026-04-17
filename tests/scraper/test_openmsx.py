"""Unit tests for scraper/openmsx.py — XML parsing and HTTP-layer functions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scraper.exclude import ExcludeList
from scraper.openmsx import (
    SKIP_PREFIXES,
    fetch_all,
    list_machine_files,
    parse_machine_xml,
)

# ---------------------------------------------------------------------------
# XML fixture helpers
# ---------------------------------------------------------------------------

def _xml(inner_info: str, inner_devices: str = "", extra_root: str = "") -> bytes:
    """Build a minimal <machine> XML from parts."""
    return (
        f"<machine>"
        f"<info>{inner_info}</info>"
        f"<devices>{inner_devices}</devices>"
        f"{extra_root}"
        f"</machine>"
    ).encode()


def _info(
    *,
    manufacturer: str = "Sony",
    code: str = "HB-75P",
    msx_type: str = "MSX2",
    year: str = "1985",
    region: str = "eu",
) -> str:
    return (
        f"<manufacturer>{manufacturer}</manufacturer>"
        f"<code>{code}</code>"
        f"<type>{msx_type}</type>"
        f"<release_year>{year}</release_year>"
        f"<region>{region}</region>"
    )


# ---------------------------------------------------------------------------
# Chunk 1 — XML parser unit tests (T-010 through T-018)
# ---------------------------------------------------------------------------


class TestParseXMLHappyPath:
    """T-010: MSX2, MSX2+, turboR happy paths."""

    def test_msx2_identity_fields(self):
        xml = _xml(_info(manufacturer="Sony", code="HB-75P", msx_type="MSX2",
                         year="1985", region="eu"))
        result = parse_machine_xml(xml, "Sony_HB-75P.xml")
        assert result is not None
        assert result["manufacturer"] == "Sony"
        assert result["model"] == "HB-75P"
        assert result["generation"] == "MSX2"
        assert result["year"] == 1985
        assert result["region"] == "Europe"

    def test_openmsx_id_derived_from_filename(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "Sony_HB-75P.xml")
        assert result is not None
        assert result["openmsx_id"] == "Sony_HB-75P"

    def test_msx2plus_standard_normalised(self):
        xml = _xml(_info(msx_type="MSX2+"))
        result = parse_machine_xml(xml, "Panasonic_FS-A1WX.xml")
        assert result is not None
        assert result["generation"] == "MSX2+"

    def test_turbor_standard_normalised(self):
        xml = _xml(_info(msx_type="MSXturboR"))
        result = parse_machine_xml(xml, "Panasonic_FS-A1ST.xml")
        assert result is not None
        assert result["generation"] == "turbo R"


class TestParseXMLSkipConditions:
    """T-011: machines that should be skipped."""

    def test_msx1_returns_none_silently(self, caplog):
        xml = _xml(_info(msx_type="MSX"))
        result = parse_machine_xml(xml, "Sony_HB-10.xml")
        assert result is None
        assert "Sony_HB-10.xml" not in caplog.text

    def test_colecovision_returns_none_silently(self, caplog):
        xml = _xml(_info(msx_type="ColecoVision"))
        result = parse_machine_xml(xml, "ColecoVision.xml")
        assert result is None

    def test_missing_manufacturer_returns_none_with_warning(self, caplog):
        xml = (
            b"<machine><info><code>HB-75P</code><type>MSX2</type></info>"
            b"<devices/></machine>"
        )
        result = parse_machine_xml(xml, "Sony_HB-75P.xml")
        assert result is None
        assert "Sony_HB-75P.xml" in caplog.text

    def test_missing_code_returns_none_with_warning(self, caplog):
        xml = (
            b"<machine><info><manufacturer>Sony</manufacturer>"
            b"<type>MSX2</type></info><devices/></machine>"
        )
        result = parse_machine_xml(xml, "Sony_HB-75P.xml")
        assert result is None
        assert "Sony_HB-75P.xml" in caplog.text

    def test_missing_info_returns_none_with_warning(self, caplog):
        xml = b"<machine><devices/></machine>"
        result = parse_machine_xml(xml, "bad.xml")
        assert result is None

    def test_missing_devices_returns_partial_record(self):
        """Machine with no <devices> still returns identity fields."""
        xml = b"<machine><info><manufacturer>Sony</manufacturer><code>HB-75P</code><type>MSX2</type></info></machine>"
        result = parse_machine_xml(xml, "Sony_HB-75P.xml")
        assert result is not None
        assert result["manufacturer"] == "Sony"
        assert "main_ram_kb" not in result
        assert "vdp" not in result


class TestParseXMLMemory:
    """T-012: memory field extraction."""

    def test_single_memory_mapper(self):
        xml = _xml(_info(), '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["main_ram_kb"] == 64
        assert result["mapper"] == "Yes"

    def test_memory_mapper_sizes_summed(self):
        devices = (
            '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>'
            '<MemoryMapper id="Extra RAM"><size>256</size></MemoryMapper>'
        )
        xml = _xml(_info(), devices)
        result = parse_machine_xml(xml, "test.xml")
        assert result["main_ram_kb"] == 320

    def test_panasonic_ram(self):
        xml = _xml(_info(msx_type="MSXturboR"),
                   '<PanasonicRAM id="Main RAM"><size>256</size></PanasonicRAM>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["main_ram_kb"] == 256
        assert result["mapper"] == "Yes"

    def test_panasonic_ram_with_memory_mapper_does_not_duplicate(self):
        xml = _xml(
            _info(msx_type="MSXturboR"),
            '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>'
            '<PanasonicRAM id="Extra RAM"><size>256</size></PanasonicRAM>',
        )
        result = parse_machine_xml(xml, "test.xml")
        assert result["mapper"] == "Yes"

    def test_plain_ram_with_size_element(self):
        xml = _xml(_info(), '<RAM id="RAM"><size>8</size></RAM>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["main_ram_kb"] == 8
        assert result["mapper"] == "No"

    def test_plain_ram_with_hex_mem_attribute(self):
        xml = _xml(_info(), '<RAM id="RAM"><mem size="0x4000"/></RAM>')
        result = parse_machine_xml(xml, "test.xml")
        # 0x4000 bytes = 16 KB
        assert result["main_ram_kb"] == 16
        assert result["mapper"] == "No"

    def test_no_ram_keys_absent(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "main_ram_kb" not in result
        assert "mapper" not in result


class TestParseXMLVideo:
    """T-013: video field extraction."""

    def test_vdp_version_extracted(self):
        xml = _xml(_info(), '<VDP id="VDP"><version>V9938</version><vram>128</vram></VDP>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["vdp"] == "V9938"
        assert result["vram_kb"] == 128

    def test_vdp_specs_populated_from_lookup(self):
        xml = _xml(_info(), '<VDP id="VDP"><version>V9958</version><vram>128</vram></VDP>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["vdp"] == "V9958"
        assert result["max_resolution"] == "512x424"
        assert result["max_colors"] == 19268
        assert result["max_sprites"] == 32

    def test_unknown_vdp_no_derived_specs(self):
        xml = _xml(_info(), '<VDP id="VDP"><version>V9999</version><vram>192</vram></VDP>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["vdp"] == "V9999"
        assert "max_resolution" not in result

    def test_missing_vdp_keys_absent(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "vdp" not in result
        assert "vram_kb" not in result


class TestParseXMLAudio:
    """T-014: audio field extraction."""

    def test_psg_present(self):
        xml = _xml(_info(), '<PSG id="PSG"/>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["psg"] == "AY-3-8910"
        assert result["audio_channels"] == 3

    def test_fm_chip_single(self):
        xml = _xml(_info(), '<MSX-MUSIC id="MSX-MUSIC"/>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["fm_chip"] == "MSX-MUSIC"

    def test_fm_chip_multiple_joined(self):
        devices = '<MSX-MUSIC id="MSX-MUSIC"/><MSX-AUDIO id="MSX-AUDIO"/>'
        xml = _xml(_info(), devices)
        result = parse_machine_xml(xml, "test.xml")
        assert "MSX-MUSIC" in result["fm_chip"]
        assert "MSX-AUDIO" in result["fm_chip"]

    def test_no_audio_keys_absent(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "psg" not in result
        assert "fm_chip" not in result


class TestParseXMLMedia:
    """T-015: media field extraction."""

    def test_floppy_drives_from_tc8566af(self):
        xml = _xml(_info(), '<TC8566AF id="TC8566AF"><drives>2</drives></TC8566AF>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["floppy_drives"] == "2"

    def test_floppy_drives_from_wd2793(self):
        xml = _xml(_info(), '<WD2793 id="WD2793"><drives>1</drives></WD2793>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["floppy_drives"] == "1"

    def test_cartridge_slots_from_external_primary(self):
        extra = (
            '<primary slot="0"/>'
            '<primary slot="1" external="true"/>'
            '<primary slot="2" external="true"/>'
        )
        xml = _xml(_info(), extra_root=extra)
        result = parse_machine_xml(xml, "test.xml")
        assert result["scraped_cart_slots"] == 2
        assert "cartridge_slots" not in result

    def test_tape_interface_present(self):
        xml = _xml(_info(), extra_root="<CassettePort/>")
        result = parse_machine_xml(xml, "test.xml")
        assert result.get("tape_interface") == "Yes"

    def test_no_floppy_key_absent(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "floppy_drives" not in result


class TestParseXMLCPU:
    """T-016: CPU extraction."""

    def test_msx2_cpu_z80(self):
        xml = _xml(_info(msx_type="MSX2"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "Z80"

    def test_msx2plus_cpu_z80(self):
        xml = _xml(_info(msx_type="MSX2+"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "Z80"

    def test_turbor_cpu_r800_with_sub_cpu(self):
        xml = _xml(_info(msx_type="MSXturboR"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "R800"
        assert result["sub_cpu"] == "Z80"

    def test_msx2_has_no_sub_cpu(self):
        xml = _xml(_info(msx_type="MSX2"))
        result = parse_machine_xml(xml, "test.xml")
        assert "sub_cpu" not in result


class TestParseXMLKeyboard:
    """T-017: keyboard layout extraction."""

    def test_known_layout_mapped_to_readable_name(self):
        xml = _xml(_info(), '<PPI id="PPI"><keyboard_type>jp_jis</keyboard_type></PPI>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["keyboard_layout"] == "Japanese (JIS)"

    def test_unknown_layout_passes_through(self):
        xml = _xml(_info(), '<PPI id="PPI"><keyboard_type>xx_unknown</keyboard_type></PPI>')
        result = parse_machine_xml(xml, "test.xml")
        assert result["keyboard_layout"] == "xx_unknown"

    def test_missing_ppi_key_absent(self):
        xml = _xml(_info())
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "keyboard_layout" not in result


class TestParseXMLRTC:
    """T-019: RTC field extraction."""

    def test_rtc_present(self):
        xml = _xml(_info(), '<RTC id="Real time clock"/>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["rtc"] == "Yes"

    def test_rtc_absent(self):
        xml = _xml(_info(), '<PSG id="PSG"/>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["rtc"] == "No"

    def test_rtc_no_devices_key_absent(self):
        xml = b"""<msxconfig>
  <info>
    <manufacturer>Sony</manufacturer>
    <code>HB-F1</code>
    <type>MSX2</type>
  </info>
</msxconfig>"""
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert "rtc" not in result


class TestParseXMLZ80Turbo:
    """T-020: Z80 turbo field extraction."""

    def test_hasturbo_true_yields_yes(self):
        xml = _xml(_info(), '<Matsushita id="Matsushita"><hasturbo>true</hasturbo></Matsushita>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["z80_turbo"] == "Yes"

    def test_hasturbo_false_yields_no(self):
        xml = _xml(_info(), '<Matsushita id="Matsushita"><hasturbo>false</hasturbo></Matsushita>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["z80_turbo"] == "No"

    def test_matsushita_without_hasturbo_yields_no(self):
        xml = _xml(_info(), '<Matsushita id="Matsushita"><sramname>foo.sram</sramname></Matsushita>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["z80_turbo"] == "No"

    def test_no_matsushita_yields_no(self):
        xml = _xml(_info(), '<PSG id="PSG"/>')
        result = parse_machine_xml(xml, "test.xml")
        assert result is not None
        assert result["z80_turbo"] == "No"


class TestParseXMLMalformed:
    """T-018: malformed XML does not abort."""

    def test_unclosed_tag_does_not_raise(self):
        # lxml recover=True should handle this
        xml = b"<machine><info><manufacturer>Sony</manufacturer><type>MSX2"
        result = parse_machine_xml(xml, "bad.xml")
        # Either None (couldn't extract useful data) or a partial dict — never an exception

    def test_empty_bytes_does_not_raise(self):
        result = parse_machine_xml(b"", "empty.xml")
        assert result is None

    def test_non_xml_bytes_does_not_raise(self):
        result = parse_machine_xml(b"not xml at all !!!", "garbage.xml")
        assert result is None


# ---------------------------------------------------------------------------
# Chunk 2 — HTTP-layer unit tests (T-020 through T-023)
# ---------------------------------------------------------------------------


def _github_api_response(names: list[str]) -> list[dict[str, Any]]:
    """Build a minimal GitHub API directory listing for the given filenames."""
    return [
        {
            "name": name,
            "type": "file",
            "download_url": f"https://raw.githubusercontent.com/openMSX/openMSX/master/share/machines/{name}",
        }
        for name in names
    ]


class TestListMachineFiles:
    """T-020 / T-021: file listing, skip prefixes, exclude list."""

    def _mock_session(self, names: list[str]) -> MagicMock:
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = _github_api_response(names)
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp
        return session

    def test_xml_files_returned(self):
        session = self._mock_session(["Sony_HB-75P.xml", "Panasonic_FS-A1.xml"])
        result = list_machine_files(session)
        names = [f["name"] for f in result]
        assert "Sony_HB-75P.xml" in names
        assert "Panasonic_FS-A1.xml" in names

    def test_non_xml_files_excluded(self):
        session = self._mock_session(["Sony_HB-75P.xml", "README.md", "config.ini"])
        result = list_machine_files(session)
        names = [f["name"] for f in result]
        assert "README.md" not in names
        assert "config.ini" not in names
        assert "Sony_HB-75P.xml" in names

    @pytest.mark.parametrize("prefix", list(SKIP_PREFIXES))
    def test_skip_prefixes_excluded(self, prefix):
        name = f"{prefix}Sony_HB-75P.xml"
        session = self._mock_session([name, "Sony_HB-75P.xml"])
        result = list_machine_files(session)
        names = [f["name"] for f in result]
        assert name not in names
        assert "Sony_HB-75P.xml" in names

    def test_exclude_list_by_filename(self):
        exclude = ExcludeList(rules=[{"filename": "Boosted_Special.xml"}])
        session = self._mock_session(["Boosted_Special.xml", "Sony_HB-75P.xml"])
        result = list_machine_files(session, exclude_list=exclude)
        names = [f["name"] for f in result]
        assert "Boosted_Special.xml" not in names
        assert "Sony_HB-75P.xml" in names

    def test_directory_entries_excluded(self):
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"name": "subdir", "type": "dir", "download_url": ""},
            {"name": "Sony_HB-75P.xml", "type": "file",
             "download_url": "https://raw.githubusercontent.com/x"},
        ]
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp
        result = list_machine_files(session)
        assert len(result) == 1
        assert result[0]["name"] == "Sony_HB-75P.xml"


class TestFetchAll:
    """T-022 / T-023: fetch_all error handling and model exclude."""

    _VALID_XML = _xml(
        _info(manufacturer="Sony", code="HB-75P", msx_type="MSX2",
              year="1985", region="eu"),
        '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>',
    )

    def _api_response(self, names: list[str]) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = _github_api_response(names)
        resp.raise_for_status = MagicMock()
        return resp

    def _xml_response(self, xml: bytes) -> MagicMock:
        resp = MagicMock()
        resp.content = xml
        resp.raise_for_status = MagicMock()
        return resp

    def _error_response(self) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception("HTTP 404")
        return resp

    def test_successful_fetch_returns_models(self):
        session = MagicMock()
        session.get.side_effect = [
            self._api_response(["Sony_HB-75P.xml"]),
            self._xml_response(self._VALID_XML),
        ]
        models = fetch_all(session=session, delay=0)
        assert len(models) == 1
        assert models[0]["manufacturer"] == "Sony"

    def test_http_error_skips_file_and_continues(self):
        valid_xml = _xml(_info(manufacturer="Panasonic", code="FS-A1", msx_type="MSX2+"))
        session = MagicMock()
        session.get.side_effect = [
            self._api_response(["bad.xml", "Panasonic_FS-A1.xml"]),
            self._error_response(),
            self._xml_response(valid_xml),
        ]
        models = fetch_all(session=session, delay=0)
        assert len(models) == 1
        assert models[0]["manufacturer"] == "Panasonic"

    def test_model_exclude_after_parse(self):
        exclude = ExcludeList(rules=[{"manufacturer": "Sony", "model": "HB-75P"}])
        session = MagicMock()
        session.get.side_effect = [
            self._api_response(["Sony_HB-75P.xml"]),
            self._xml_response(self._VALID_XML),
        ]
        models = fetch_all(session=session, delay=0, exclude_list=exclude)
        assert len(models) == 0

    def test_non_msx2_xml_not_included(self):
        msx1_xml = _xml(_info(msx_type="MSX"))
        session = MagicMock()
        session.get.side_effect = [
            self._api_response(["MSX1_machine.xml"]),
            self._xml_response(msx1_xml),
        ]
        models = fetch_all(session=session, delay=0)
        assert len(models) == 0

    def test_listing_failure_returns_empty_not_raises(self):
        """A 403/network error on the GitHub API listing returns [] gracefully."""
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        models = fetch_all(session=session, delay=0)
        assert models == []


# ---------------------------------------------------------------------------
# BIOS ROM info extraction (character_set / keyboard_type)
# ---------------------------------------------------------------------------


def _bios_bytes(charset: int = 1, kbtype: int = 1, size: int = 0x100) -> bytes:
    """Return minimal ROM bytes with charset at 0x002B and kbtype at 0x002C."""
    data = bytearray(size)
    data[0x002B] = charset
    data[0x002C] = kbtype
    return bytes(data)


def _write_rom(tmp_path: Path, data: bytes, name: str = "bios.rom") -> tuple[dict, Path, str]:
    """Write *data* to tmp_path/<name>, return (sha1_index, root, sha1_hex)."""
    rom_file = tmp_path / name
    rom_file.write_bytes(data)
    sha1_hex = hashlib.sha1(data).hexdigest()
    return {sha1_hex: Path(name)}, tmp_path, sha1_hex


def _bios_devices(sha1_hex: str, window_base: int = 0) -> str:
    window = f'<window base="{hex(window_base)}" size="0x8000"/>' if window_base else ""
    return f'<ROM id="MSX BIOS with BASIC ROM"><rom><sha1>{sha1_hex}</sha1>{window}</rom></ROM>'


class TestBiosRomExtraction:
    """BIOS ROM byte extraction → character_set and keyboard_type fields."""

    # --- Happy path ---

    def test_international_charset_and_keyboard(self, tmp_path):
        data = _bios_bytes(charset=1, kbtype=1)
        idx, root, sha1 = _write_rom(tmp_path, data)
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "International"
        assert result["keyboard_type"] == "International"

    def test_japanese_charset_and_keyboard(self, tmp_path):
        data = _bios_bytes(charset=0, kbtype=0)
        idx, root, sha1 = _write_rom(tmp_path, data)
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "Japanese"
        assert result["keyboard_type"] == "Japanese"

    def test_korean_charset(self, tmp_path):
        data = _bios_bytes(charset=2, kbtype=1)
        idx, root, sha1 = _write_rom(tmp_path, data)
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "Korean"

    @pytest.mark.parametrize("kbval,expected", [
        (0, "Japanese"), (1, "International"), (2, "French"), (3, "UK"), (4, "German"),
    ])
    def test_all_keyboard_type_values(self, tmp_path, kbval, expected):
        data = _bios_bytes(charset=1, kbtype=kbval)
        idx, root, sha1 = _write_rom(tmp_path, data)
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["keyboard_type"] == expected

    def test_lower_nibble_only(self, tmp_path):
        """Upper nibble bits must be ignored."""
        data = bytearray(0x100)
        data[0x002B] = 0xF1  # upper nibble 0xF, lower nibble 1 → International
        data[0x002C] = 0xF3  # upper nibble 0xF, lower nibble 3 → UK
        idx, root, sha1 = _write_rom(tmp_path, bytes(data))
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "International"
        assert result["keyboard_type"] == "UK"

    # --- Window offset ---

    def test_window_offset_applied(self, tmp_path):
        """With <window base="0x8000">, bytes 0x002B/0x002C are at 0x802B/0x802C."""
        data = bytearray(0x9000)
        data[0x802B] = 1  # International charset
        data[0x802C] = 3  # UK keyboard
        idx, root, sha1 = _write_rom(tmp_path, bytes(data))
        xml = _xml(_info(), _bios_devices(sha1, window_base=0x8000))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "International"
        assert result["keyboard_type"] == "UK"

    # --- Block-based (PanasonicRom / turbo R) ---

    def test_block_based_firstblock_offset(self, tmp_path):
        """firstblock=1 → BIOS starts at byte offset 8192 in the firmware file."""
        data = bytearray(8192 + 0x100)
        data[8192 + 0x002B] = 0  # Japanese charset
        data[8192 + 0x002C] = 0  # Japanese keyboard
        idx, root, sha1 = _write_rom(tmp_path, bytes(data), "firmware.rom")
        bios_devices = '<ROM id="MSX BIOS with BASIC ROM"><rom><firstblock>1</firstblock><lastblock>4</lastblock></rom></ROM>'
        pan_rom = f'<PanasonicRom id="Firmware ROM"><rom><sha1>{sha1}</sha1></rom></PanasonicRom>'
        xml = _xml(_info(msx_type="MSXturboR"), bios_devices, extra_root=pan_rom)
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "Japanese"
        assert result["keyboard_type"] == "Japanese"

    def test_block_based_firstblock_zero(self, tmp_path):
        data = _bios_bytes(charset=2, kbtype=1)
        idx, root, sha1 = _write_rom(tmp_path, data, "firmware.rom")
        bios_devices = '<ROM id="MSX BIOS with BASIC ROM"><rom><firstblock>0</firstblock><lastblock>3</lastblock></rom></ROM>'
        pan_rom = f'<PanasonicRom id="Firmware ROM"><rom><sha1>{sha1}</sha1></rom></PanasonicRom>'
        xml = _xml(_info(msx_type="MSXturboR"), bios_devices, extra_root=pan_rom)
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert result["character_set"] == "Korean"

    # --- Failure / null cases ---

    def test_no_sha1_index_sets_no_fields(self):
        xml = _xml(_info(), _bios_devices("deadbeef"))
        result = parse_machine_xml(xml, "test.xml", sha1_index=None, systemroms_root=None)
        assert "character_set" not in result
        assert "keyboard_type" not in result

    def test_sha1_not_in_index_sets_no_fields(self, tmp_path, caplog):
        xml = _xml(_info(), _bios_devices("deadbeef00000000000000000000000000000000"))
        result = parse_machine_xml(xml, "test.xml", sha1_index={}, systemroms_root=tmp_path)
        assert "character_set" not in result
        assert "keyboard_type" not in result
        assert "BIOS ROM" in caplog.text

    def test_file_not_on_disk_sets_no_fields(self, tmp_path):
        sha1 = "a" * 40
        idx = {sha1: Path("missing.rom")}
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=tmp_path)
        assert "character_set" not in result
        assert "keyboard_type" not in result

    def test_file_too_short_sets_no_fields(self, tmp_path, caplog):
        data = bytes(10)  # only 10 bytes, offsets 0x002B/0x002C unreachable
        idx, root, sha1 = _write_rom(tmp_path, data)
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert "character_set" not in result
        assert "keyboard_type" not in result
        assert "too short" in caplog.text

    def test_unknown_nibble_sets_no_field(self, tmp_path, caplog):
        data = bytearray(0x100)
        data[0x002B] = 9   # unmapped charset value
        data[0x002C] = 1   # valid keyboard value
        idx, root, sha1 = _write_rom(tmp_path, bytes(data))
        xml = _xml(_info(), _bios_devices(sha1))
        result = parse_machine_xml(xml, "test.xml", sha1_index=idx, systemroms_root=root)
        assert "character_set" not in result  # unknown → null
        assert result["keyboard_type"] == "International"  # valid field still set
        assert "Unknown character_set" in caplog.text

    def test_no_bios_rom_element_sets_no_fields(self, tmp_path):
        xml = _xml(_info(), '<PSG id="PSG"/>')
        result = parse_machine_xml(xml, "test.xml", sha1_index={}, systemroms_root=tmp_path)
        assert "character_set" not in result
        assert "keyboard_type" not in result

    def test_block_based_no_panasonic_rom_sets_no_fields(self, tmp_path, caplog):
        bios_devices = '<ROM id="MSX BIOS with BASIC ROM"><rom><firstblock>1</firstblock><lastblock>4</lastblock></rom></ROM>'
        xml = _xml(_info(msx_type="MSXturboR"), bios_devices)
        result = parse_machine_xml(xml, "test.xml", sha1_index={}, systemroms_root=tmp_path)
        assert "character_set" not in result
        assert "No <PanasonicRom>" in caplog.text

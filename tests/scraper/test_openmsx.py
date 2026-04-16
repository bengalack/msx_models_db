"""Unit tests for scraper/openmsx.py — XML parsing and HTTP-layer functions."""

from __future__ import annotations

import json
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
        assert result["cartridge_slots"] == 2

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
    """T-016: CPU and speed extraction."""

    def test_msx2_cpu_z80a(self):
        xml = _xml(_info(msx_type="MSX2"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "Z80A"
        assert result["cpu_speed_mhz"] == 3.58

    def test_msx2plus_cpu_z80a(self):
        xml = _xml(_info(msx_type="MSX2+"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "Z80A"
        assert result["cpu_speed_mhz"] == 3.58

    def test_turbor_cpu_r800_with_sub_cpu(self):
        xml = _xml(_info(msx_type="MSXturboR"))
        result = parse_machine_xml(xml, "test.xml")
        assert result["cpu"] == "R800"
        assert result["cpu_speed_mhz"] == 7.16
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

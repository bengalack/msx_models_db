"""Scrape MSX machine data from openMSX XML config files on GitHub."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests
from lxml import etree

from .exclude import ExcludeList
from .openmsx_source import (
    GITHUB_API_URL,
    SKIP_PREFIXES,
    FallbackXMLSource,
    LiveXMLSource,
    MirrorXMLSource,
    XMLSource,
)
from .slotmap import extract_slotmap, load_sha1_index

log = logging.getLogger(__name__)

RAW_BASE_URL = (
    "https://raw.githubusercontent.com/openMSX/openMSX/master/share/machines"
)

# MSX standards we care about (MSX1 is out of scope for iteration 1).
WANTED_TYPES = {"MSX2", "MSX2+", "MSXturboR"}

# openMSX region codes → human-readable region strings.
REGION_MAP: dict[str, str] = {
    "jp": "Japan",
    "kr": "Korea",
    "eu": "Europe",
    "us": "USA",
    "gb": "UK",
    "fr": "France",
    "de": "Germany",
    "es": "Spain",
    "nl": "Netherlands",
    "br": "Brazil",
    "se": "Sweden",
    "it": "Italy",
    "pt": "Portugal",
    "ru": "Russia",
    "sa": "Saudi Arabia",
    "il": "Israel",
    "kw": "Kuwait",
    "ar": "Argentina",
    "me": "Middle East",
}

# Well-known VDP → max-resolution / max-colors / max-sprites lookup.
VDP_SPECS: dict[str, dict[str, Any]] = {
    "TMS9918A":  {"max_resolution": "256x192", "max_colors": 16, "max_sprites": 32},
    "TMS9928A":  {"max_resolution": "256x192", "max_colors": 16, "max_sprites": 32},
    "TMS9929A":  {"max_resolution": "256x192", "max_colors": 16, "max_sprites": 32},
    "V9938":     {"max_resolution": "512x424", "max_colors": 256, "max_sprites": 32},
    "V9958":     {"max_resolution": "512x424", "max_colors": 19268, "max_sprites": 32},
}

# BIOS ROM byte maps (MSX System Variables — https://map.grauw.nl/resources/msxsystemvars.php)
# Both fields are encoded in the lower nibble (bits 0–3) of their respective byte.
_CHARSET_MAP: dict[int, str] = {0: "Japanese", 1: "International", 2: "Korean"}
_KBTYPE_MAP: dict[int, str] = {0: "Japanese", 1: "International", 2: "French", 3: "UK", 4: "German"}
_BIOS_BLOCK_SIZE = 8192  # openMSX PanasonicRom block size in bytes

# Default CPU for each MSX type.
CPU_DEFAULTS: dict[str, tuple[str, float]] = {
    "MSX":        ("Z80", 3.58),
    "MSX2":       ("Z80", 3.58),
    "MSX2+":      ("Z80", 3.58),
    "MSXturboR":  ("R800", 7.16),
}


def _text(el: etree._Element | None) -> str | None:
    """Return stripped text of an element, or None."""
    if el is None:
        return None
    t = el.text
    return t.strip() if t else None


def _int(el: etree._Element | None) -> int | None:
    """Return int text of an element, or None."""
    t = _text(el)
    if t is None:
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _mem_size_kb(parent: etree._Element) -> int:
    """Sum <mem size="0x..."/> children to get total size in KB."""
    total = 0
    for mem in parent.findall("mem"):
        raw = mem.get("size", "")
        try:
            total += int(raw, 0)  # handles 0x hex prefix
        except ValueError:
            pass
    return total // 1024 if total else 0


def list_machine_files(
    session: requests.Session,
    exclude_list: ExcludeList | None = None,
) -> list[dict[str, str]]:
    """Return list of {name, download_url} for .xml machine files."""
    src = LiveXMLSource(session)
    names = src.list_files(exclude_list=exclude_list)
    return [{"name": n, "download_url": src._url_map[n]} for n in names]


def parse_machine_xml(
    xml_bytes: bytes,
    filename: str,
    lut_rules: list[dict] | None = None,
    sha1_index: dict[str, Path] | None = None,
    systemroms_root: Path | None = None,
) -> dict[str, Any] | None:
    """Parse a single openMSX machine XML.  Returns field dict or None if skipped."""
    try:
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(xml_bytes, parser=parser)
    except etree.XMLSyntaxError:
        log.warning("XML parse error in %s — skipped", filename)
        return None

    if root is None:
        log.warning("XML parse error in %s — skipped", filename)
        return None

    info = root.find("info")
    if info is None:
        log.warning("No <info> in %s — skipped", filename)
        return None

    msx_type = _text(info.find("type"))
    if msx_type not in WANTED_TYPES:
        return None  # silently skip non-MSX2+ machines

    manufacturer = _text(info.find("manufacturer"))
    model = _text(info.find("code"))
    if not manufacturer or not model:
        log.warning("Missing manufacturer/code in %s — skipped", filename)
        return None

    openmsx_id = filename.removesuffix(".xml")

    result: dict[str, Any] = {
        "manufacturer": manufacturer,
        "model": model,
        "year": _int(info.find("release_year")),
        "region": _map_region(_text(info.find("region"))),
        "generation": _normalise_type(msx_type),
        "openmsx_id": openmsx_id,
    }

    # ── Hardware extraction (from <devices>) ─────────────────────────
    devices = root.find("devices")
    if devices is None:
        return result

    _extract_memory(devices, result)
    _extract_video(devices, result)
    _extract_audio(devices, result)
    _extract_media(devices, result)
    _extract_cpu(devices, result, msx_type)
    _extract_keyboard(devices, result)
    _extract_connectivity(devices, result)
    _extract_rtc(devices, result)
    _extract_z80_turbo(devices, result)
    _extract_bios_rom_info(root, result, sha1_index, systemroms_root, filename)

    # Slot map extraction (only when LUT rules are provided)
    if lut_rules is not None:
        slotmap = extract_slotmap(
            root,
            lut_rules,
            filename=filename,
            sha1_index=sha1_index,
            systemroms_root=systemroms_root,
        )
        result.update(slotmap)

    return result


def _normalise_type(t: str | None) -> str | None:
    """Normalise openMSX type string to our schema values."""
    mapping = {
        "MSX": "MSX",
        "MSX2": "MSX2",
        "MSX2+": "MSX2+",
        "MSXturboR": "turbo R",
    }
    return mapping.get(t or "", t)


def _map_region(code: str | None) -> str | None:
    if code is None:
        return None
    return REGION_MAP.get(code, code)


def _extract_memory(devices: etree._Element, out: dict[str, Any]) -> None:
    """Extract Main RAM, VRAM, ROM sizes."""
    # Main RAM: look for MemoryMapper elements and sum sizes.
    total_ram = 0
    for mm in devices.iter("MemoryMapper"):
        size = _int(mm.find("size"))
        if size:
            total_ram += size
    if total_ram:
        out["main_ram_kb"] = total_ram

    # Mapper type(s)
    mappers: list[str] = []
    for mm in devices.iter("MemoryMapper"):
        mid = mm.get("id", "")
        if mid and mid not in mappers:
            mappers.append(mid)
    if mappers:
        out["mapper"] = ", ".join(mappers) if len(mappers) > 1 else "Yes"

    # PanasonicRAM is used by turbo R and some MSX2+ machines.
    # It is a proprietary implementation of the standard MSX memory mapper interface.
    panasonic_ram_found = False
    for pram in devices.iter("PanasonicRAM"):
        size = _int(pram.find("size"))
        if size:
            total_ram += size
        panasonic_ram_found = True
    if panasonic_ram_found and "mapper" not in out:
        out["mapper"] = "Yes"
    if total_ram:
        out["main_ram_kb"] = total_ram

    # Also check for plain RAM (no mapper) in some simple machines.
    # Some <RAM> elements have <size>, others only have <mem size="0x...">.
    if not total_ram:
        for ram in devices.iter("RAM"):
            size = _int(ram.find("size"))
            if size:
                total_ram += size
            else:
                total_ram += _mem_size_kb(ram)
        if total_ram:
            out["main_ram_kb"] = total_ram
            out["mapper"] = "No"

    # SRAM: only the PANASONIC mapper type exposes <sramsize> (decimal KB).
    # NATIONAL and FSA1FM1/FSA1FM2 mapper types have SRAM too but no size
    # element in the XML — size is hardcoded in the emulator, so we skip them.
    for rom in devices.iter("ROM"):
        mappertype = _text(rom.find("mappertype"))
        if mappertype == "PANASONIC":
            sram_size = _int(rom.find("sramsize"))
            if sram_size:
                out["sram_kb"] = str(sram_size)
            break


def _extract_video(devices: etree._Element, out: dict[str, Any]) -> None:
    """Extract VDP version and VRAM."""
    vdp = devices.find(".//VDP")
    if vdp is None:
        return
    version = _text(vdp.find("version"))
    if version:
        out["vdp"] = version
        specs = VDP_SPECS.get(version, {})
        out.update({k: v for k, v in specs.items() if k not in out})
    vram = _int(vdp.find("vram"))
    if vram:
        out["vram_kb"] = vram


def _extract_audio(devices: etree._Element, out: dict[str, Any]) -> None:
    """Extract PSG and FM chip info."""
    psg = devices.find(".//PSG")
    if psg is not None:
        out["psg"] = "AY-3-8910"
        out["audio_channels"] = 3

    # FM chips — various element names in openMSX configs.
    fm_names = []
    for tag in ("MSX-MUSIC", "MSX-MUSIC-WX", "FMPAC", "MSX-AUDIO",
                "MoonSound", "YM2413"):
        for el in devices.iter(tag):
            chip_id = el.get("id", tag)
            if chip_id not in fm_names:
                fm_names.append(chip_id)
    if fm_names:
        out["fm_chip"] = ", ".join(fm_names)


def _extract_media(devices: etree._Element, out: dict[str, Any]) -> None:
    """Extract floppy drives, cartridge slots, tape interface."""
    # Floppy drives: TC8566AF, WD2793, MB8877A, etc.
    floppy_count = 0
    for fdc_tag in ("TC8566AF", "WD2793", "MB8877A", "Microsol"):
        for fdc in devices.iter(fdc_tag):
            n = _int(fdc.find("drives"))
            if n:
                floppy_count += n
    if floppy_count:
        out["floppy_drives"] = str(floppy_count)

    # Cartridge slots: count primary slots marked external="true", plus secondary
    # slots marked external="true" (cartridge in a subslot — non-standard design).
    root = devices.getparent()
    cart_count = 0
    if root is not None:
        for primary in root.iter("primary"):
            if primary.get("external") == "true":
                cart_count += 1
            else:
                for secondary in primary.findall("secondary"):
                    if secondary.get("external") == "true":
                        cart_count += 1
    if cart_count:
        out["scraped_cart_slots"] = cart_count

    # Tape interface
    if root is not None and root.find("CassettePort") is not None:
        out["tape_interface"] = "Yes"


def _extract_cpu(
    devices: etree._Element, out: dict[str, Any], msx_type: str | None
) -> None:
    """Set CPU based on MSX type defaults."""
    cpu = CPU_DEFAULTS.get(msx_type or "", ("Z80", 3.58))[0]
    out["cpu"] = cpu

    # turbo R has both Z80 and R800; check for R800 element.
    if msx_type == "MSXturboR":
        out["sub_cpu"] = "Z80"


def _extract_keyboard(devices: etree._Element, out: dict[str, Any]) -> None:
    ppi = devices.find(".//PPI")
    if ppi is None:
        return
    kb = _text(ppi.find("keyboard_type"))
    if kb:
        # Map openMSX keyboard codes to readable names.
        kb_map: dict[str, str] = {
            "jp_jis": "Japanese (JIS)",
            "jp_ansi": "Japanese (ANSI)",
            "int": "International",
            "es": "Spanish",
            "fr": "French (AZERTY)",
            "de": "German (QWERTZ)",
            "gb": "UK",
            "pt": "Portuguese",
            "br": "Brazilian",
            "kr": "Korean",
            "ru": "Russian",
            "ar": "Arabic",
            "se": "Swedish",
        }
        out["keyboard_layout"] = kb_map.get(kb, kb)


def _extract_rtc(devices: etree._Element, out: dict[str, Any]) -> None:
    """Detect RTC hardware by presence of <RTC> element under <devices>."""
    out["rtc"] = "Yes" if devices.find("RTC") is not None else "No"


def _extract_z80_turbo(devices: etree._Element, out: dict[str, Any]) -> None:
    """Detect Z80 turbo support from <Matsushita><hasturbo> under <devices>.

    Any model whose XML was parsed gets an explicit "Yes" or "No".
    Models with no XML file never call this function and keep a null value.
    """
    matsushita = devices.find("Matsushita")
    if matsushita is None:
        out["z80_turbo"] = "No"
        return
    out["z80_turbo"] = "Yes" if _text(matsushita.find("hasturbo")) == "true" else "No"


def _resolve_bios_file(
    bios_rom_el: etree._Element,
    root: etree._Element,
    sha1_index: dict[str, Path],
    systemroms_root: Path,
    filename: str,
) -> tuple[Path | None, int]:
    """Return (rom_file_path, bios_start_offset) or (None, 0) on failure.

    Two resolution paths:
    - Direct SHA1: the BIOS ROM element has a <sha1> child; a <window base>
      offset is applied if present.
    - Block-based: the BIOS ROM element uses <firstblock>/<lastblock> (turbo R /
      PanasonicRom machines); the firmware file is located via <PanasonicRom>'s
      SHA1 and the byte offset is firstblock * 8192.
    """
    rom_child = bios_rom_el.find("rom")
    if rom_child is None:
        return None, 0

    # --- Direct SHA1 path ---
    sha1_els = rom_child.findall("sha1")
    if sha1_els:
        window_el = rom_child.find("window")
        window_base = int(window_el.get("base", "0"), 0) if window_el is not None else 0
        for sha1_el in sha1_els:
            sha1 = (sha1_el.text or "").strip().lower()
            if not sha1:
                continue
            file_rel = sha1_index.get(sha1)
            if file_rel is None:
                continue
            file_path = systemroms_root / file_rel
            if file_path.exists():
                return file_path, window_base
        log.warning("BIOS ROM SHA1 not resolved to a file on disk for %s", filename)
        return None, 0

    # --- Block-based path (PanasonicRom / turbo R) ---
    firstblock_el = rom_child.find("firstblock")
    if firstblock_el is not None:
        try:
            firstblock = int((firstblock_el.text or "").strip())
        except ValueError:
            log.warning("Invalid <firstblock> in BIOS ROM for %s", filename)
            return None, 0

        panasonic_rom = root.find(".//PanasonicRom")
        if panasonic_rom is None:
            log.warning("No <PanasonicRom> for block-based BIOS in %s", filename)
            return None, 0

        pan_rom_child = panasonic_rom.find("rom")
        if pan_rom_child is None:
            return None, 0

        for sha1_el in pan_rom_child.findall("sha1"):
            sha1 = (sha1_el.text or "").strip().lower()
            if not sha1:
                continue
            file_rel = sha1_index.get(sha1)
            if file_rel is None:
                continue
            file_path = systemroms_root / file_rel
            if file_path.exists():
                return file_path, firstblock * _BIOS_BLOCK_SIZE

        log.warning("PanasonicRom SHA1 not resolved to a file on disk for %s", filename)
        return None, 0

    return None, 0


def _extract_bios_rom_info(
    root: etree._Element,
    out: dict[str, Any],
    sha1_index: dict[str, Path] | None,
    systemroms_root: Path | None,
    filename: str,
) -> None:
    """Extract character_set and keyboard_type from the main BIOS ROM.

    Reads byte 0x002B (character set) and 0x002C (keyboard type), masks the
    lower nibble of each, and maps the value to a human-readable string.
    Sets no keys when the ROM file cannot be located or a value is unknown.
    """
    if sha1_index is None or systemroms_root is None:
        return

    bios_rom = root.find('.//*[@id="MSX BIOS with BASIC ROM"]')
    if bios_rom is None:
        return

    rom_path, bios_offset = _resolve_bios_file(
        bios_rom, root, sha1_index, systemroms_root, filename
    )
    if rom_path is None:
        return

    try:
        data = rom_path.read_bytes()
    except OSError as exc:
        log.warning("Cannot read BIOS ROM %s for %s: %s", rom_path, filename, exc)
        return

    for field, offset, value_map in (
        ("character_set", 0x002B, _CHARSET_MAP),
        ("keyboard_type", 0x002C, _KBTYPE_MAP),
    ):
        file_pos = bios_offset + offset
        if file_pos >= len(data):
            log.warning(
                "BIOS ROM too short for %s in %s (need %d bytes, have %d)",
                field, filename, file_pos + 1, len(data),
            )
            continue
        nibble = data[file_pos] & 0x0F
        mapped = value_map.get(nibble)
        if mapped is None:
            log.warning("Unknown %s value %d in BIOS ROM for %s", field, nibble, filename)
            continue
        out[field] = mapped


def _extract_connectivity(devices: etree._Element, out: dict[str, Any]) -> None:
    ports: list[str] = []
    root = devices.getparent()
    if root is not None and root.find("CassettePort") is not None:
        ports.append("Cassette")
    for el in devices.iter("PrinterPort"):
        ports.append("Printer")
        break
    # Joystick ports are implicit on MSX (always 2)
    if ports:
        out["connectivity"] = ", ".join(ports)


def fetch_all(
    session: requests.Session | None = None,
    *,
    source: XMLSource | None = None,
    delay: float = 0.3,
    limit: int | None = None,
    exclude_list: ExcludeList | None = None,
    lut_rules: list[dict] | None = None,
    sha1_index: dict[str, Path] | None = None,
    systemroms_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse all openMSX machine configs.  Returns list of model dicts.

    When *source* is given it is used as-is (live, mirror, or fallback).
    When *source* is None a ``LiveXMLSource`` is created from *session*
    (creating a default session when *session* is also None).
    """
    if source is None:
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        source = LiveXMLSource(session)

    log.info("Listing openMSX machine files…")
    try:
        names = source.list_files(exclude_list=exclude_list)
    except Exception:
        log.exception("Failed to list openMSX machine files — returning empty result")
        return []
    log.info("Found %d XML files", len(names))

    if limit:
        names = names[:limit]

    models: list[dict[str, Any]] = []
    excluded = 0
    skipped = 0
    errors = 0

    for i, name in enumerate(names):
        try:
            xml_bytes = source.fetch_file(name)
            if xml_bytes is None:
                skipped += 1
                continue
            result = parse_machine_xml(
                xml_bytes, name,
                lut_rules=lut_rules,
                sha1_index=sha1_index,
                systemroms_root=systemroms_root,
            )
            if result:
                if exclude_list and exclude_list.is_excluded(
                    result.get("manufacturer"), result.get("model")
                ):
                    log.debug(
                        "[exclude:skip] Excluded model | manufacturer=%s model=%s source=openmsx",
                        result.get("manufacturer"), result.get("model"),
                    )
                    excluded += 1
                else:
                    models.append(result)
            else:
                skipped += 1
        except Exception:
            log.exception("Error parsing %s", name)
            errors += 1

        if delay and i < len(names) - 1:
            time.sleep(delay)

    log.info(
        "openMSX: %d models extracted, %d excluded, %d skipped, %d errors",
        len(models), excluded, skipped, errors,
    )
    return models

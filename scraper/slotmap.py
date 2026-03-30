"""Slot map extractor for openMSX machine XML files.

Walks the <primary>/<secondary> hierarchy and classifies each device via the
slot map LUT, producing 64 cell values (4 main slots × 4 sub-slots × 4 pages)
per machine.

Cell value conventions:
  "~"        — slot/page not expanded (default)
  "CS{N}"    — cartridge slot N (external primary, derived from slot="N")
  "<abbr>"   — LUT-matched abbreviation (e.g. "MAIN", "MM", "DSK")
  "<abbr>*"  — mirror page (origin abbreviation + asterisk)
  "<tag>"    — unmatched device element tag (with [WARN] logged to stdout)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from lxml import etree

# All 64 column keys, pre-computed.
_ALL_KEYS: list[str] = [
    f"slotmap_{ms}_{ss}_{p}"
    for ms in range(4)
    for ss in range(4)
    for p in range(4)
]

_TILDE = "~"

# Pages 0-3 correspond to address ranges 0x0000-0x3FFF, 0x4000-0x7FFF, etc.
_PAGE_SIZE = 0x4000


def _pages_for_mem(base: int, size: int) -> list[int]:
    """Return the list of 4KB pages (0-3) whose range intersects [base, base+size)."""
    pages = []
    for p in range(4):
        page_start = p * _PAGE_SIZE
        page_end = page_start + _PAGE_SIZE
        mem_end = base + size
        if page_start < mem_end and page_end > base:
            pages.append(p)
    return pages


def _parse_hex_or_int(s: str | None) -> int | None:
    """Parse a hex (0x...) or decimal integer string, or return None."""
    if s is None:
        return None
    try:
        return int(s, 0)
    except (ValueError, TypeError):
        return None


def match_lut(element_tag: str, element_id: str | None, rules: list[dict]) -> str | None:
    """Return the abbr for the first matching LUT rule, or None if no match.

    Matching logic:
      - rule["element"] is a pipe-separated list of element tag names
        (or a single name). Compared case-sensitively.
      - rule["id_pattern"] is a case-insensitive regex matched against
        element_id. null means match any id.
      - "__sentinel__" and "secondary" entries are skipped (structural, not
        device elements).
    """
    for rule in rules:
        rule_element = rule.get("element", "")
        # Skip structural/sentinel entries
        if rule_element in ("__sentinel__", "secondary"):
            continue
        alternatives = [e.strip() for e in rule_element.split("|")]
        if element_tag not in alternatives:
            continue
        id_pattern = rule.get("id_pattern")
        if id_pattern is not None:
            id_str = element_id or ""
            if not re.search(id_pattern, id_str, re.IGNORECASE):
                continue
        return rule["abbr"]
    return None


def _classify_devices(
    slot_el: etree._Element,
    lut_rules: list[dict],
    filename: str,
) -> dict[int, str]:
    """Classify all direct device children of *slot_el* into a {page: abbr} map.

    Returns a page map (pages 0-3). Devices with no <mem> child are skipped.
    Overlapping pages: first assignment wins; [WARN] logged for subsequent.
    Unknown devices: raw element tag used as value; [WARN] logged.
    """
    page_map: dict[int, str] = {}

    for child in slot_el:
        tag = child.tag
        # Skip structural/non-device elements
        if not isinstance(tag, str):
            continue
        if tag in ("secondary", "Mirror", "primary"):
            continue

        mem_el = child.find("mem")
        if mem_el is None:
            continue  # no memory mapping — not a slottable device

        base = _parse_hex_or_int(mem_el.get("base"))
        size = _parse_hex_or_int(mem_el.get("size"))
        if base is None or size is None:
            continue

        pages = _pages_for_mem(base, size)
        if not pages:
            continue

        element_id = child.get("id")
        abbr = match_lut(tag, element_id, lut_rules)

        if abbr is None:
            print(
                f"[WARN] Unmatched device: {tag} id={element_id!r} in {filename}",
                file=sys.stderr,
            )
            abbr = tag  # raw tag as fallback

        for p in pages:
            if p in page_map:
                print(
                    f"[WARN] Page overlap: {tag} id={element_id!r} overlaps page {p}"
                    f" in {filename}; first device wins",
                    file=sys.stderr,
                )
            else:
                page_map[p] = abbr

    return page_map


def _page_map_to_cells(page_map: dict[int, str]) -> list[str]:
    """Convert a {page: abbr} map to a 4-element list (pages 0-3), defaulting to '~'."""
    return [page_map.get(p, _TILDE) for p in range(4)]


def extract_slotmap(
    root: etree._Element,
    lut_rules: list[dict],
    filename: str = "<unknown>",
    sha1_index: dict[str, Path] | None = None,
    systemroms_root: Path | None = None,
) -> dict[str, str]:
    """Extract all 64 slot map cell values from an openMSX machine XML root.

    Returns a dict with all 64 keys (slotmap_{ms}_{ss}_{p}), each valued as:
    "~", "CS{N}", an LUT abbreviation, "abbr*" (mirror), or a raw element tag.

    Args:
        root: Parsed lxml element (<msxconfig> or <machine> root).
        lut_rules: Loaded LUT rules from slotmap-lut.json.
        filename: Machine filename for warning messages.
        sha1_index: Optional mapping of SHA1 → Path for mirror method 2.
        systemroms_root: Base directory for ROM file lookups (mirror method 2).
    """
    # Initialise all 64 cells to "~"
    result: dict[str, str] = {k: _TILDE for k in _ALL_KEYS}

    devices = root.find("devices")
    if devices is None:
        return result

    # ── First pass: walk primary/secondary hierarchy ──────────────────────
    # Collect per-slot classifications for mirror method 3 cross-references.
    # slot_abbrs[ms][ss][page] = abbr
    slot_abbrs: dict[int, dict[int, dict[int, str]]] = {
        ms: {ss: {} for ss in range(4)} for ms in range(4)
    }

    for primary in devices.findall("primary"):
        ms_attr = primary.get("slot")
        if ms_attr is None:
            continue
        try:
            ms = int(ms_attr)
        except ValueError:
            continue
        if ms not in range(4):
            continue

        # External primary: cartridge slot
        if primary.get("external") == "true":
            abbr = f"CS{ms}"
            for p in range(4):
                result[f"slotmap_{ms}_0_{p}"] = abbr
                slot_abbrs[ms][0][p] = abbr
            # Sub-slots 1-3 remain "~"
            continue

        # Check for secondary children
        secondaries = primary.findall("secondary")

        if not secondaries:
            # Non-expanded primary: classify direct device children into sub-slot 0
            page_map = _classify_devices(primary, lut_rules, filename)
            page_map = _apply_rom_visibility(primary, page_map, lut_rules, filename,
                                             sha1_index, systemroms_root)
            for p, abbr in page_map.items():
                result[f"slotmap_{ms}_0_{p}"] = abbr
                slot_abbrs[ms][0][p] = abbr
            # Sub-slots 1-3 remain "~"
        else:
            # Expanded primary: classify each secondary slot
            for secondary in secondaries:
                ss_attr = secondary.get("slot")
                if ss_attr is None:
                    continue
                try:
                    ss = int(ss_attr)
                except ValueError:
                    continue
                if ss not in range(4):
                    continue

                page_map = _classify_devices(secondary, lut_rules, filename)
                page_map = _apply_rom_visibility(secondary, page_map, lut_rules,
                                                 filename, sha1_index, systemroms_root)
                for p, abbr in page_map.items():
                    result[f"slotmap_{ms}_{ss}_{p}"] = abbr
                    slot_abbrs[ms][ss][p] = abbr

    # ── Second pass: resolve Mirror elements ─────────────────────────────
    _apply_mirror_elements(root, devices, result, slot_abbrs, filename)

    return result


def _apply_rom_visibility(
    slot_el: etree._Element,
    page_map: dict[int, str],
    lut_rules: list[dict],
    filename: str,
    sha1_index: dict[str, Path] | None,
    systemroms_root: Path | None,
) -> dict[int, str]:
    """Apply mirror annotations from rom_visibility (method 1) and ROM file size (method 2).

    Modifies page_map in place. Returns the modified page_map.
    """
    for child in slot_el:
        tag = child.tag
        if not isinstance(tag, str):
            continue
        if tag in ("secondary", "Mirror", "primary"):
            continue

        mem_el = child.find("mem")
        if mem_el is None:
            continue
        base = _parse_hex_or_int(mem_el.get("base"))
        size = _parse_hex_or_int(mem_el.get("size"))
        if base is None or size is None:
            continue

        element_id = child.get("id")
        abbr = match_lut(tag, element_id, lut_rules)
        if abbr is None:
            abbr = tag

        mem_pages = _pages_for_mem(base, size)

        # Method 1: <rom_visibility>
        rv_el = child.find("rom_visibility")
        if rv_el is not None:
            rv_base = _parse_hex_or_int(rv_el.get("base"))
            rv_size = _parse_hex_or_int(rv_el.get("size"))
            if rv_base is not None and rv_size is not None:
                visible_pages = set(_pages_for_mem(rv_base, rv_size))
                for p in mem_pages:
                    if p not in visible_pages:
                        page_map[p] = f"{abbr}*"

        # Method 2: ROM file size vs mem range
        if tag == "ROM" and sha1_index is not None:
            file_size = _rom_file_size(child, sha1_index, systemroms_root, filename)
            if file_size is not None and file_size < size:
                # Pages whose start offset is >= file_size are mirrors
                for p in mem_pages:
                    page_offset = p * _PAGE_SIZE - base
                    if page_offset >= file_size:
                        page_map[p] = f"{abbr}*"

    return page_map


def _rom_file_size(
    rom_el: etree._Element,
    sha1_index: dict[str, Path],
    systemroms_root: Path | None,
    filename: str,
) -> int | None:
    """Return the on-disk size of the ROM file referenced by *rom_el*, or None."""
    for rom_child in rom_el.findall("rom"):
        for sha1_el in rom_child.findall("sha1"):
            sha1 = (sha1_el.text or "").strip().lower()
            if not sha1:
                continue
            file_rel = sha1_index.get(sha1)
            if file_rel is None:
                print(
                    f"[WARN] SHA1 not found in index: {sha1} in {filename};"
                    f" skipping mirror detection for this ROM",
                    file=sys.stderr,
                )
                continue
            if systemroms_root is None:
                return None
            file_path = systemroms_root / file_rel
            if not file_path.exists():
                print(
                    f"[WARN] ROM file not found: {file_path} in {filename};"
                    f" skipping mirror",
                    file=sys.stderr,
                )
                continue
            return file_path.stat().st_size
    return None


def _apply_mirror_elements(
    root: etree._Element,
    devices: etree._Element,
    result: dict[str, str],
    slot_abbrs: dict[int, dict[int, dict[int, str]]],
    filename: str,
) -> None:
    """Second pass: resolve <Mirror> elements throughout the XML tree.

    Writes `origin_abbr*` to the pages specified by the Mirror's <mem>.
    """
    # Collect all Mirror elements from anywhere in the devices tree
    for mirror in devices.iter("Mirror"):
        mem_el = mirror.find("mem")
        if mem_el is None:
            continue
        base = _parse_hex_or_int(mem_el.get("base"))
        size = _parse_hex_or_int(mem_el.get("size"))
        if base is None or size is None:
            continue

        # Origin slot
        ps_el = mirror.find("ps")
        ss_el = mirror.find("ss")
        ps = _parse_hex_or_int(ps_el.text if ps_el is not None else None)
        ss = _parse_hex_or_int(ss_el.text if ss_el is not None else None)
        if ps is None:
            continue
        if ss is None:
            ss = 0  # default to sub-slot 0 if not specified

        # Determine which slot this Mirror lives in
        host_ms, host_ss = _find_mirror_host(mirror, devices)
        if host_ms is None:
            continue

        # Look up origin abbreviation
        origin_pages = slot_abbrs.get(ps, {}).get(ss, {})
        if not origin_pages:
            print(
                f"[WARN] Mirror origin slot {ps}/{ss} not yet classified"
                f" in {filename}; skipping",
                file=sys.stderr,
            )
            continue

        # Use the most common abbr in the origin slot as the mirror label
        # (typically all pages in the origin have the same abbr)
        abbrs = [a for a in origin_pages.values() if not a.endswith("*") and a != _TILDE]
        if not abbrs:
            continue
        origin_abbr = max(set(abbrs), key=abbrs.count)

        mirror_pages = _pages_for_mem(base, size)
        for p in mirror_pages:
            key = f"slotmap_{host_ms}_{host_ss}_{p}"
            result[key] = f"{origin_abbr}*"


def _find_mirror_host(
    mirror_el: etree._Element,
    devices: etree._Element,
) -> tuple[int | None, int | None]:
    """Return (ms, ss) of the slot that contains *mirror_el*."""
    for primary in devices.findall("primary"):
        ms_attr = primary.get("slot")
        if ms_attr is None:
            continue
        try:
            ms = int(ms_attr)
        except ValueError:
            continue

        # Check direct children of primary (non-expanded)
        if mirror_el in primary:
            return ms, 0

        # Check secondary children
        for secondary in primary.findall("secondary"):
            if mirror_el in secondary:
                ss_attr = secondary.get("slot")
                try:
                    ss = int(ss_attr) if ss_attr is not None else 0
                except ValueError:
                    ss = 0
                return ms, ss

    return None, None


def load_sha1_index(path: Path | None) -> dict[str, Path]:
    """Parse all_sha1s.txt and return {sha1_hex: relative_path}.

    Returns an empty dict if path is None or the file does not exist.
    """
    if path is None or not path.exists():
        return {}
    index: dict[str, Path] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            sha1, rel = parts
            # Strip leading "./" from paths
            rel = rel.lstrip("./")
            index[sha1.lower()] = Path(rel)
    return index

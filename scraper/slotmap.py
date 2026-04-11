"""Slot map extractor for openMSX machine XML files.

Walks the <primary>/<secondary> hierarchy and classifies each device via the
slot map LUT, producing 64 cell values (4 main slots × 4 sub-slots × 4 pages)
per machine.

Cell value conventions:
  "⌧"        — sub-slot physically absent (non-expanded SS1-3, cartridge SS1-3)
  "•"        — page is present in a real sub-slot but has no device mapped
  "CS{N}"    — cartridge slot N (sequential counter, not slot index)
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

# ⌧ U+2327: sub-slot is physically absent (non-expanded SS1-3, cartridge SS1-3).
_ABSENT = "\u2327"  # ⌧

# • U+2022: sub-slot is real but the page has no device mapped there.
_EMPTY_PAGE = "\u2022"  # •

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
        if rule_element in ("__sentinel__", "__cartridge__", "secondary"):
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


def _iter_slot_devices(slot_el: etree._Element):
    """Iterate device children of *slot_el*, skipping structural elements.

    Yields child elements while skipping secondary, Mirror, primary, and
    non-string tags.  ToshibaTCX-200x wrappers are yielded as-is (handled
    specially by ``_classify_tcx_wrapper``).
    """
    for child in slot_el:
        tag = child.tag
        if not isinstance(tag, str):
            continue
        if tag in ("secondary", "Mirror", "primary"):
            continue
        yield child


def _classify_tcx_wrapper(
    wrapper_el: etree._Element,
    lut_rules: list[dict],
    filename: str,
) -> dict[int, str]:
    """Classify sub-devices inside a <ToshibaTCX-200x> compound device.

    The wrapper's own ``<mem base size>`` defines the Z80 address range.
    Inner ROM/device children use ``<window size>`` to declare their internal
    bank size.  Sub-devices are packed sequentially into the wrapper's address
    range, each consuming ``min(window_size, remaining_space)`` bytes.

    Returns a ``{page: abbr}`` map for the pages covered.
    """
    # Wrapper's Z80 address range
    wrapper_mem = wrapper_el.find("mem")
    if wrapper_mem is None:
        return {}
    wrapper_base = _parse_hex_or_int(wrapper_mem.get("base"))
    wrapper_size = _parse_hex_or_int(wrapper_mem.get("size"))
    if wrapper_base is None or wrapper_size is None:
        return {}
    wrapper_end = wrapper_base + wrapper_size

    page_map: dict[int, str] = {}
    offset = wrapper_base

    for child in wrapper_el:
        child_tag = child.tag
        if not isinstance(child_tag, str):
            continue
        # Skip non-device children (mem, sramname, initialContent, etc.)
        window_el = child.find("window")
        if window_el is None:
            continue
        win_size = _parse_hex_or_int(window_el.get("size"))
        if win_size is None or win_size <= 0:
            continue

        # How much space this child occupies in the Z80 range
        effective_size = min(win_size, wrapper_end - offset)
        if effective_size <= 0:
            break  # no room left in the wrapper's range

        pages = _pages_for_mem(offset, effective_size)
        element_id = child.get("id")
        # TCX wrapper uses lowercase tags (e.g. <rom>) but the LUT uses
        # the canonical uppercase form (<ROM>), so normalise for matching.
        lut_tag = child_tag.upper()
        abbr = match_lut(lut_tag, element_id, lut_rules)
        if abbr is None:
            print(
                f"[WARN] Unmatched device: {lut_tag} id={element_id!r} in {filename}",
                file=sys.stderr,
            )
            abbr = lut_tag

        for p in pages:
            if p not in page_map:
                page_map[p] = abbr

        offset += win_size  # advance by full window size for packing

    return page_map


def _classify_devices(
    slot_el: etree._Element,
    lut_rules: list[dict],
    filename: str,
) -> dict[int, str]:
    """Classify all direct device children of *slot_el* into a {page: abbr} map.

    Returns a page map (pages 0-3). Devices with no <mem> child are skipped.
    Overlapping pages: first assignment wins; [WARN] logged for subsequent.
    Unknown devices: raw element tag used as value; [WARN] logged.
    ToshibaTCX-200x compound devices are handled via ``_classify_tcx_wrapper``.
    """
    page_map: dict[int, str] = {}

    for child in _iter_slot_devices(slot_el):
        tag = child.tag

        # Compound wrapper — sub-devices use <window>, not <mem>
        if tag == "ToshibaTCX-200x":
            tcx_map = _classify_tcx_wrapper(child, lut_rules, filename)
            for p, abbr in tcx_map.items():
                if p not in page_map:
                    page_map[p] = abbr
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
    """Convert a {page: abbr} map to a 4-element list (pages 0-3), defaulting to '•'."""
    return [page_map.get(p, _EMPTY_PAGE) for p in range(4)]


def extract_slotmap(
    root: etree._Element,
    lut_rules: list[dict],
    filename: str = "<unknown>",
    sha1_index: dict[str, Path] | None = None,
    systemroms_root: Path | None = None,
) -> dict[str, str | None]:
    """Extract all 64 slot map cell values from an openMSX machine XML root.

    Returns a dict with all 64 keys (slotmap_{ms}_{ss}_{p}), each valued as:
    "⌧"   — sub-slot is physically absent (non-expanded SS1-3, cartridge SS1-3)
    "•"   — sub-slot is real but the page has no device mapped (U+2022)
    "CS{N}" — cartridge slot N (sequential 1-based counter)
    "<abbr>" — LUT-matched abbreviation (e.g. "MAIN", "MM", "DSK")
    "<abbr>*" — mirror page (origin abbreviation + asterisk)
    "<tag>" — unmatched device element tag (with [WARN] logged)

    Rules:
    - Non-expanded primary (no <secondary> children): sub-slot 0 pages with no
      device → "•"; sub-slots 1-3 → "⌧".
    - External primary (cartridge): sub-slot 0 → "CS{N}" on all 4 pages
      (N is a sequential 1-based counter, not the slot index);
      sub-slots 1-3 → "⌧".
    - Expanded primary (<secondary> children): pages with no device in a
      present sub-slot → "•"; sub-slots absent from XML → "⌧".

    Args:
        root: Parsed lxml element (<msxconfig> or <machine> root).
        lut_rules: Loaded LUT rules from slotmap-lut.json.
        filename: Machine filename for warning messages.
        sha1_index: Optional mapping of SHA1 → Path for mirror method 2.
        systemroms_root: Base directory for ROM file lookups (mirror method 2).
    """
    # Initialise all 64 cells to ⌧ (absent); real sub-slots are filled below.
    result: dict[str, str | None] = {k: _ABSENT for k in _ALL_KEYS}

    devices = root.find("devices")
    if devices is None:
        return result

    # ── First pass: walk primary/secondary hierarchy ──────────────────────
    # Collect per-slot classifications for mirror method 3 cross-references.
    # slot_abbrs[ms][ss][page] = abbr
    slot_abbrs: dict[int, dict[int, dict[int, str]]] = {
        ms: {ss: {} for ss in range(4)} for ms in range(4)
    }

    # Sequential counter for cartridge slot numbering (CS1, CS2, …)
    cs_counter = 0

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
            cs_counter += 1
            abbr = f"CS{cs_counter}"
            for p in range(4):
                result[f"slotmap_{ms}_0_{p}"] = abbr
                slot_abbrs[ms][0][p] = abbr
            # Sub-slots 1-3: ⌧ (no secondary expansion on a cartridge slot)
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
            # Sub-slot 0: pages with no device → • (real page, nothing mapped)
            for p in range(4):
                if result[f"slotmap_{ms}_0_{p}"] == _ABSENT:
                    result[f"slotmap_{ms}_0_{p}"] = _EMPTY_PAGE
            # Sub-slots 1-3: ⌧ (no secondary expansion exists)

        else:
            # Expanded primary: classify each secondary slot
            present_subslots = set()
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

                present_subslots.add(ss)

                # External secondary: cartridge slot in a subslot (non-standard).
                # Mark with ! suffix to signal the unusual placement.
                if secondary.get("external") == "true":
                    cs_counter += 1
                    abbr = f"CS{cs_counter}!"
                    for p in range(4):
                        result[f"slotmap_{ms}_{ss}_{p}"] = abbr
                        slot_abbrs[ms][ss][p] = abbr
                    continue

                page_map = _classify_devices(secondary, lut_rules, filename)
                page_map = _apply_rom_visibility(secondary, page_map, lut_rules,
                                                 filename, sha1_index, systemroms_root)
                for p, abbr in page_map.items():
                    result[f"slotmap_{ms}_{ss}_{p}"] = abbr
                    slot_abbrs[ms][ss][p] = abbr
                # Pages with no device in this real sub-slot → •
                for p in range(4):
                    if result[f"slotmap_{ms}_{ss}_{p}"] == _ABSENT:
                        result[f"slotmap_{ms}_{ss}_{p}"] = _EMPTY_PAGE

            # If any subslot is present, all subslots 0-3 must be considered present (never ⌧)
            if present_subslots:
                for ss in range(4):
                    for p in range(4):
                        key = f"slotmap_{ms}_{ss}_{p}"
                        if result[key] == _ABSENT:
                            result[key] = _EMPTY_PAGE

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

    Method 1: ``<rom_visibility base size>`` child on any device — pages outside the
    visibility range are marked as mirrors.

    Method 2: ROM file size vs ``<mem size>`` — applies to ``<ROM>`` elements and
    to FDC/other devices (e.g. ``WD2793``, ``TC8566AF``) that have an embedded
    ``<rom>`` child.  Pages whose start offset within the device's Z80 range is
    >= the on-disk ROM file size are marked as mirrors.

    Modifies page_map in place. Returns the modified page_map.
    """
    for child in _iter_slot_devices(slot_el):
        tag = child.tag

        # ToshibaTCX-200x children use <window>, not <mem> — no rom_visibility
        if tag == "ToshibaTCX-200x":
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
        # Applies to <ROM> elements and to FDC/other devices with an embedded <rom> child
        # (e.g. WD2793, TC8566AF) whose ROM is smaller than the mapped address range.
        has_rom_child = child.find("rom") is not None
        if (tag == "ROM" or has_rom_child) and sha1_index is not None:
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
        abbrs = [a for a in origin_pages.values() if not a.endswith("*") and a not in (_EMPTY_PAGE, _ABSENT)]
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

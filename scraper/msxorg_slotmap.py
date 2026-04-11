"""Slot map parser for msx.org wiki HTML pages.

Parses the "Slot Map" section found on many msx.org model wiki pages and
produces the same 64-cell ``dict[str, str]`` output format as
``scraper.slotmap.extract_slotmap()``.

Cell value conventions (identical to scraper.slotmap):
  "⌧"      — sub-slot physically absent (non-expanded SS 1-3, cartridge SS 1-3)
  "•"      — sub-slot present but no device mapped on this page
  "CS{N}"  — cartridge slot N (1-based sequential counter per table, L→R)
  "<abbr>" — short abbreviation (e.g. "MAIN", "MM", "DSK")

The HTML Slot Map table uses a compact visual layout:
  - Non-expanded main slots appear as a single data column.
  - Expanded main slots (sub-slots 0-3) appear as four data columns.
  - Page rows run top→bottom as C000h (page 3) → 8000h → 4000h → 0000h (page 0).
  - Cells with rowspan=4 span all four page rows (e.g. cartridge slots).
  - Divider columns between slot groups contain blank text.

Limitations vs. the openMSX XML extractor:
  - No mirror/alias detection (msx.org HTML does not encode mirror info).
  - Cell content is free text → abbreviation matching is heuristic.
  - Multiple Slot_Map sections on one page (e.g. 1chipMSX default/upgraded):
    only the FIRST section is used.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import sys
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

log = logging.getLogger(__name__)

# ── Cell sentinels — identical to scraper.slotmap ────────────────────────
_ABSENT = "\u2327"     # ⌧  sub-slot physically absent
_EMPTY_PAGE = "\u2022" # •  sub-slot real, no device on this page

# All 64 column keys, pre-computed.
_ALL_KEYS: list[str] = [
    f"slotmap_{ms}_{ss}_{p}"
    for ms in range(4)
    for ss in range(4)
    for p in range(4)
]

# ── Page address → page number ────────────────────────────────────────────

_RE_PAGE_ADDR = re.compile(r"\b([0-9A-Fa-f]{4})[hH]")


def _page_from_label(text: str) -> int | None:
    """Parse 'Page C000h~...' or 'Bank 8000h~...' text → page number 0-3.

    Returns None if the text does not look like a page-row label.
    """
    m = _RE_PAGE_ADDR.search(text)
    if m is None:
        return None
    try:
        addr = int(m.group(1), 16)
    except ValueError:
        return None
    p = addr // 0x4000
    return p if 0 <= p <= 3 else None


# ── Column header label → (main_slot, sub_slot) ──────────────────────────

# Matches "N-M", "N‑M" (with non-breaking hyphen U+2011), "N.M", etc.
_RE_MS_SS = re.compile(r"(\d)[^\d](\d)$")
_RE_MS_ONLY = re.compile(r"\b(\d)\b$")


def _parse_col_label(text: str) -> tuple[int, int] | None:
    """Map a column header string to (main_slot, sub_slot) or None.

    Handles labels such as:
      "0-0", "0-1", "3-3*"  → (ms, ss) from the two digits
      "Slot 0", "Slot 1"    → (ms, 0)
      "Slot 3-0", "3-1"     → (ms, ss)
      ""  or  "Slot"        → None (divider / outer group header)
    """
    text = text.strip()
    # Strip leading "Slot " prefix (case-insensitive)
    stripped = re.sub(r"^[Ss]lot\s*", "", text).strip()
    # Remove trailing non-alphanumeric chars (e.g. "*" in "3-3*")
    stripped = re.sub(r"[^0-9\-\u2011]+$", "", stripped).rstrip("-\u2011").strip()

    if not stripped:
        return None
    if stripped.lower() == "slot":
        return None

    # Try "N-M" (any single non-digit separator between two single digits)
    m = _RE_MS_SS.search(stripped)
    if m:
        ms, ss = int(m.group(1)), int(m.group(2))
        if ms in range(4) and ss in range(4):
            return (ms, ss)

    # Try single digit (non-expanded slot label)
    m = _RE_MS_ONLY.search(stripped)
    if m:
        ms = int(m.group(1))
        if ms in range(4):
            return (ms, 0)

    return None


# ── HTML table flattening ─────────────────────────────────────────────────


def _flatten_table(table: Tag) -> list[list[str]]:
    """Flatten an HTML table respecting rowspan/colspan.

    Returns a 2-D list of strings (rows × cols).  All rows are padded to the
    same width with empty strings.
    """
    # Collect <tr> elements (they may be inside <thead>/<tbody>)
    rows = table.find_all("tr")

    occupied: dict[tuple[int, int], str] = {}
    max_col = 0

    for r_idx, tr in enumerate(rows):
        col_cursor = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            # Advance past any column positions already occupied by rowspan
            while (r_idx, col_cursor) in occupied:
                col_cursor += 1

            text = cell.get_text(separator=" ", strip=True)
            try:
                rowspan = max(1, int(cell.get("rowspan", 1)))
                colspan = max(1, int(cell.get("colspan", 1)))
            except (ValueError, TypeError):
                rowspan = colspan = 1

            for dr in range(rowspan):
                for dc in range(colspan):
                    occupied[(r_idx + dr, col_cursor + dc)] = text

            col_cursor += colspan
        if col_cursor > max_col:
            max_col = col_cursor

    if not occupied:
        return []

    num_rows = max(r for r, _ in occupied) + 1
    grid: list[list[str]] = [
        [occupied.get((r, c), "") for c in range(max_col)]
        for r in range(num_rows)
    ]
    return grid


# ── Cell text → abbreviation ──────────────────────────────────────────────

# Cartridge-like slots (produce CS{N} with sequential numbering)
_CART_RE = re.compile(
    r"cartridge\s+slot"
    r"|mini[\s\-]cartridge"
    r"|module\s+slot"
    r"|slot\s+cn\d+",          # National FS-5000x internal connector slots
    re.IGNORECASE,
)

# Expansion bus
_EXP_RE = re.compile(r"expansion\s+bus", re.IGNORECASE)

# Patterns loaded from data/slotmap-lut.json.  ``element`` is ignored here
# (it encodes openMSX XML element names, not HTML cell text).  Only entries
# with a non-null ``id_pattern`` are used from the LUT.  A small supplemental
# list handles element-only entries where ``id_pattern`` is null.
_TEXT_PATTERNS: list[tuple[re.Pattern[str], str]]


def _load_text_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Build (pattern, abbr) pairs from data/slotmap-lut.json.

    LUT order is preserved and treated as priority order (first match wins).
    Supplemental patterns for element-only entries are inserted just before
    the broad FW firmware catch-all.
    """
    _SKIP = {"__cartridge__", "__sentinel__", "secondary"}

    lut_path = pathlib.Path(__file__).parent.parent / "data" / "slotmap-lut.json"
    with lut_path.open(encoding="utf-8") as fh:
        lut: list[dict] = json.load(fh)

    lut_patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(entry["id_pattern"], re.IGNORECASE), entry["abbr"])
        for entry in lut
        if entry["element"] not in _SKIP and entry.get("id_pattern")
    ]

    # Supplemental patterns for LUT entries that have no id_pattern (element
    # names only).  These match the free-text device labels on msx.org pages.
    # Order: PM before MM/RAM; MM before RAM; all before the FW catch-all.
    supplemental: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"panasonic\s+(?:mapper|ram)",            re.IGNORECASE), "PM"),
        (re.compile(r"memory\s+mapper|\d+\s*[kmgt]b\s+memory\b", re.IGNORECASE), "MM"),
        (re.compile(r"\bram\b",                               re.IGNORECASE), "RAM"),
        # LUT "Main ROM" pattern won't match "Main-ROM" (hyphen); cover it here.
        (re.compile(r"main[\s\-]rom",                         re.IGNORECASE), "MAIN"),
        (re.compile(r"disk\s+rom|floppy",                     re.IGNORECASE), "DSK"),
        (re.compile(r"msx[\s\-]*music|fmpac|fm\s+(?:voicing|music)", re.IGNORECASE), "MUS"),
        (re.compile(r"\brs[\s\-]?232\b",                      re.IGNORECASE), "RS"),
        (re.compile(r"\bmodem\b",                             re.IGNORECASE), "MOD"),
        (re.compile(r"bunsetsu",                              re.IGNORECASE), "BUN"),
    ]

    # Insert supplemental just before the FW catch-all entry.
    fw_pos = next(
        (i for i, (_, abbr) in enumerate(lut_patterns) if abbr == "FW"),
        len(lut_patterns),
    )
    return lut_patterns[:fw_pos] + supplemental + lut_patterns[fw_pos:]


_TEXT_PATTERNS = _load_text_patterns()

# Sentinel returned when the cell text looks like a cartridge slot.
# The caller replaces this with "CS{N}".
_CART_SENTINEL = "__CART__"


def _classify_cell_text(text: str) -> str | None:
    """Map a cell text string to an abbreviation, or None if unrecognised.

    Returns ``_CART_SENTINEL`` for cartridge-like slots (caller must replace).
    Returns ``None`` for blank text (caller interprets as empty page).
    Returns ``None`` for unrecognised text (caller logs a warning and uses
    the raw text as a fallback).
    """
    t = text.strip()
    if not t:
        return None

    if _CART_RE.search(t):
        return _CART_SENTINEL

    if _EXP_RE.search(t):
        return "EXP"

    for pattern, abbr in _TEXT_PATTERNS:
        if pattern.search(t):
            return abbr

    return None  # unrecognised


# ── Core table parser ─────────────────────────────────────────────────────


def _parse_slotmap_table(table: Tag, page_title: str) -> dict[str, str]:
    """Parse a single msx.org slot-map HTML table.

    Returns a dict of all 64 ``slotmap_{ms}_{ss}_{p}`` keys.
    """
    grid = _flatten_table(table)
    if not grid:
        return {k: _ABSENT for k in _ALL_KEYS}

    # Pad all rows to the same width
    num_cols = max(len(row) for row in grid)
    grid = [row + [""] * (num_cols - len(row)) for row in grid]

    # ── Separate header rows from data rows ───────────────────────────────
    # Data rows have a "Page …h" or "Bank …h" label in column 0.
    data_row_indices: list[int] = []
    page_for_row: dict[int, int] = {}
    last_header_row: int | None = None

    for r_idx, row in enumerate(grid):
        p = _page_from_label(row[0])
        if p is not None:
            data_row_indices.append(r_idx)
            page_for_row[r_idx] = p
        else:
            last_header_row = r_idx

    if not data_row_indices:
        log.warning("No page rows found in slot map table in %s", page_title)
        return {k: _ABSENT for k in _ALL_KEYS}

    if last_header_row is None:
        log.warning("No header row in slot map table in %s", page_title)
        return {k: _ABSENT for k in _ALL_KEYS}

    # ── Build column → (ms, ss) map from last header row ─────────────────
    col_to_slot: dict[int, tuple[int, int]] = {}
    for c in range(1, num_cols):  # col 0 is always the row-label column
        label = grid[last_header_row][c]
        slot = _parse_col_label(label)
        if slot is not None:
            col_to_slot[c] = slot

    if not col_to_slot:
        log.warning("No slot columns decoded in slot map table in %s", page_title)
        return {k: _ABSENT for k in _ALL_KEYS}

    # ── Determine which main slots are expanded (>1 sub-slot column) ──────
    ms_subslots: dict[int, set[int]] = {}
    for ms, ss in col_to_slot.values():
        ms_subslots.setdefault(ms, set()).add(ss)

    ms_expanded: dict[int, bool] = {
        ms: len(subs) > 1
        for ms, subs in ms_subslots.items()
    }

    # ── Pre-compute cartridge column → CS number (left-to-right order) ───
    first_data = data_row_indices[0]
    cart_col_cs: dict[int, str] = {}
    cs_counter = 0
    for c in sorted(col_to_slot.keys()):
        if _CART_RE.search(grid[first_data][c].strip()):
            cs_counter += 1
            cart_col_cs[c] = f"CS{cs_counter}"

    # ── Initialise all 64 cells to ⌧ ─────────────────────────────────────
    result: dict[str, str] = {k: _ABSENT for k in _ALL_KEYS}

    # ── Fill data cells ───────────────────────────────────────────────────
    for r_idx in data_row_indices:
        page = page_for_row[r_idx]
        for c, (ms, ss) in col_to_slot.items():
            raw = grid[r_idx][c].strip()
            key = f"slotmap_{ms}_{ss}_{page}"

            if c in cart_col_cs:
                result[key] = cart_col_cs[c]
            elif not raw:
                result[key] = _EMPTY_PAGE
            else:
                abbr = _classify_cell_text(raw)
                if abbr is None:
                    # Unrecognised text: warn and use truncated raw as fallback
                    print(
                        f"[WARN] msxorg slotmap: unrecognised cell {raw!r}"
                        f" in {page_title}",
                        file=sys.stderr,
                    )
                    result[key] = raw[:10]
                elif abbr == _CART_SENTINEL:
                    # Should not reach here (pre-computed above), but be safe
                    cs_counter += 1
                    cart_col_cs[c] = f"CS{cs_counter}"
                    result[key] = cart_col_cs[c]
                else:
                    result[key] = abbr

    # ── Fill sentinel / empty-page for slots based on expansion status ────
    for ms, subs in ms_subslots.items():
        if ms_expanded[ms]:
            # Expanded: all 4 sub-slots are physically present.
            # Any sub-slot not seen in col_to_slot, or any page still ⌧ → •
            for ss in range(4):
                for p in range(4):
                    if result[f"slotmap_{ms}_{ss}_{p}"] == _ABSENT:
                        result[f"slotmap_{ms}_{ss}_{p}"] = _EMPTY_PAGE
        else:
            # Non-expanded: sub-slot 0 is real, 1-3 are absent (stay ⌧).
            # Sub-slot 0 pages still ⌧ had an empty cell in the HTML → •
            for p in range(4):
                if result[f"slotmap_{ms}_0_{p}"] == _ABSENT:
                    result[f"slotmap_{ms}_0_{p}"] = _EMPTY_PAGE
            # sub-slots 1-3 already ⌧ — leave them

    return result


# ── Public API ────────────────────────────────────────────────────────────


def parse_slotmap_from_soup(
    soup: BeautifulSoup,
    page_title: str = "<unknown>",
) -> dict[str, str] | None:
    """Extract the slot map from an already-parsed msx.org wiki page.

    Returns a 64-key ``slotmap_*`` dict, or ``None`` if no Slot_Map section
    is found.  Only the first ``Slot_Map`` section is used (pages with multiple
    sections, such as 1chipMSX, use the default/first configuration).
    """
    slot_span = soup.find("span", id=re.compile(r"^Slot_Map"))
    if slot_span is None:
        return None

    h2 = slot_span.parent  # the <h2> element

    # Walk siblings until we find the first <table>
    table: Tag | None = None
    node = h2.next_sibling
    while node is not None:
        if isinstance(node, Tag):
            if node.name == "table":
                table = node
                break
            # Stop at the next heading (another section began)
            if node.name and node.name[0] == "h" and node.name[1:].isdigit():
                break
        node = node.next_sibling

    if table is None:
        log.warning(
            "Slot_Map heading found but no table follows in %s", page_title
        )
        return None

    return _parse_slotmap_table(table, page_title)


def parse_msxorg_slotmap(
    html: bytes,
    page_title: str = "<unknown>",
) -> dict[str, str] | None:
    """Parse the slot map from raw msx.org wiki HTML.

    Convenience wrapper around ``parse_slotmap_from_soup`` for callers that
    have the raw HTML bytes rather than a pre-parsed soup object.

    Returns a 64-key ``slotmap_*`` dict, or ``None`` if no Slot_Map section
    is found.
    """
    soup = BeautifulSoup(html, "lxml")
    return parse_slotmap_from_soup(soup, page_title)

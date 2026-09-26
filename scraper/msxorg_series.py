"""Per-variant data from msx.org series pages.

msx.org keeps the technical details of some model families on one shared
series page (a wiki category such as ``Category:Sony_HB-75``). Its specs table
covers every variant at once, naming the variants a value applies to in free
text, and it may carry several slot maps told apart by their headings. The
member pages (``Sony HB-75P``) have no specs table and link to the series.

This module turns a series page into the specs dict and slot map table for one
variant, so the normal model-page parsing can run on them unchanged.

Design: .claude/artifacts/planning/2026-09-26-msxorg-series-pages-design.md
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from .msxorg_slotmap import _flatten_table, slotmap_sections

log = logging.getLogger(__name__)

# "(other models)", "(other versions)"
_OTHER_RE = re.compile(r"\bother (?:models?|versions?)\b", re.IGNORECASE)
# A model-code-shaped label ("HB-10:", "HX-22GB:", even the typo "HB-22I:").
_CODE_LABEL_RE = re.compile(r"(?<![\w-])([A-Z]{1,4}-?\d+[A-Z0-9]*)\s*:")
_SEE_TABLE_RE = re.compile(r"\bsee table above\b", re.IGNORECASE)
_KB_RE = re.compile(r"(\d+)\s*kB", re.IGNORECASE)

# Specs fields parse_model_page reads; an unresolved one is worth reporting.
_PARSED_FIELDS = {
    "Year", "Region", "RAM", "VRAM", "Video", "Audio", "Media", "Extras", "Chipset", "Keyboard layout",
}

# Specs fields whose "see table above" is answered by a variant-table column.
_TABLE_COLUMN_FOR_FIELD = {"Region": "Region", "Keyboard layout": "Keyboard"}

# Region codes used in the variant tables.
_REGION_CODES = {
    "AR": "Argentina", "AU": "Australia", "BE": "Belgium", "CH": "Switzerland",
    "DE": "Germany", "ES": "Spain", "FI": "Finland", "FR": "France", "GB": "United Kingdom",
    "IT": "Italy", "JP": "Japan", "KR": "Korea", "NL": "Netherlands", "SE": "Sweden",
    "UK": "United Kingdom", "US": "United States",
}
# Region names a region-qualified value may use; a European country also
# matches a segment qualified "Europe".
_EUROPE = {
    "Belgium", "Finland", "France", "Germany", "Italy", "Netherlands", "Spain",
    "Sweden", "Switzerland", "United Kingdom",
}
_REGION_NAMES = sorted(
    set(_REGION_CODES.values()) | _EUROPE | {"Europe", "Japan"}, key=len, reverse=True
)
_REGION_QUALIFIER_RE = re.compile(
    rf"(?:\bin\s+|\()({'|'.join(re.escape(n) for n in _REGION_NAMES)})\)?", re.IGNORECASE
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _variant_re(variants: list[str]) -> re.Pattern[str]:
    """Whole-token, longest-first matcher, so HX-10S never matches inside HX-10SA."""
    alternatives = "|".join(re.escape(v) for v in sorted(set(variants), key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


def _names_in(text: str, vre: re.Pattern[str]) -> set[str]:
    return {m.group(0).upper() for m in vre.finditer(text)}


def _strip_separators(text: str) -> str:
    text = re.sub(r"^\s*(?:,|;|-|or\b|and\b)\s*", "", text)
    return text.strip(" ,;-")


# ── Field resolution ────────────────────────────────────────────────────────


def _resolve_by_region(text: str, region: str) -> str | None:
    """``1984-10-16 in Japan - 1985 in Spain`` → the segment for *region*."""
    wanted = {region.lower()}
    if region in _EUROPE:
        wanted.add("europe")
    start = 0
    for m in _REGION_QUALIFIER_RE.finditer(text):
        segment = _strip_separators(text[start:m.start()])
        start = m.end()
        if m.group(1).lower() in wanted:
            return segment or None
    return None


def resolve_value(
    value: str,
    variant: str,
    variants: list[str],
    *,
    region: str | None = None,
) -> str | None:
    """The part of a series specs *value* that applies to *variant*.

    Returns ``None`` when the value names variants but not this one (and has no
    "other models" part): an unresolved value must never be filled with another
    variant's text. ``region`` enables region-qualified resolution (Year).
    """
    text = _normalise(value)
    vre = _variant_re(variants)
    target = variant.upper()

    if region is not None and len(_REGION_QUALIFIER_RE.findall(text)) >= 2:
        return _resolve_by_region(text, region)

    if not _names_in(text, vre) and not _OTHER_RE.search(text):
        return text  # shared by every variant

    # Label-colon: "HB-10: Japan HB-10B: United Kingdom"
    labels = list(_CODE_LABEL_RE.finditer(text))
    if len(labels) >= 2:
        for i, m in enumerate(labels):
            end = labels[i + 1].start() if i + 1 < len(labels) else len(text)
            if m.group(1).upper() == target:
                return _strip_separators(text[m.end():end]) or None
        return None

    # Leading label: "(HB-101) QWERTY/JP50on - (HB-101P) QWERTY with a £ key"
    groups = [m for m in re.finditer(r"\(([^()]*)\)\s*", text) if _names_in(m.group(1), vre)]
    if groups and groups[0].start() == 0:
        for i, m in enumerate(groups):
            end = groups[i + 1].start() if i + 1 < len(groups) else len(text)
            if target in _names_in(m.group(1), vre):
                return _strip_separators(text[m.end():end]) or None
        return None

    # "in" qualifier: "TCX-1010 in HX-21, TCX-1012 in HX-21F"
    parts = [p for p in re.split(r",\s*", text) if p]
    in_parts = [re.match(rf"(.+?)\s+in\s+(?=(?:{vre.pattern}))(.+)$", p, re.IGNORECASE) for p in parts]
    if len(parts) >= 2 and all(in_parts):
        for m in in_parts:
            if target in _names_in(m.group(2), vre):
                return m.group(1).strip() or None
        return None

    # Trailing qualifier: "16kB in slot 0 (HB-10) or 64kB in slot 3 (other models)"
    segments: list[tuple[str, set[str], bool]] = []
    start = 0
    for m in re.finditer(r"\(([^()]*)\)", text):
        names = _names_in(m.group(1), vre)
        other = bool(_OTHER_RE.search(m.group(1)))
        if not names and not other:
            continue
        segments.append((_strip_separators(text[start:m.start()]), names, other))
        start = m.end()
    for segment, names, _ in segments:
        if target in names:
            return segment or None
    for segment, _, other in segments:
        if other:
            return segment or None
    return None


def expand_region_codes(text: str) -> str:
    """``BE, NL`` → ``Belgium, Netherlands``; names and unknown codes are kept."""
    parts = [p.strip() for p in re.split(r"\s*,\s*", text) if p.strip()]
    return ", ".join(_REGION_CODES.get(p.upper(), p) for p in parts)


# ── Page structure ──────────────────────────────────────────────────────────


def series_slug(page: BeautifulSoup) -> str | None:
    """The series a member page defers to ("see HB-75 series for the technical details")."""
    body = page.select_one("#bodyContent") or page
    for a in body.find_all("a", href=True):
        href = a["href"]
        if "Category:" in href and "series" in a.get_text(" ", strip=True).lower():
            return unquote(href.split("Category:", 1)[1]).split("#")[0].split("&")[0]
    return None


def _strip_brand(name: str, brand: str) -> str:
    name = _normalise(name)
    return name[len(brand) + 1:] if brand and name.startswith(brand + " ") else name


def _variant_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
    tables = []
    for table in soup.find_all("table"):
        grid = _flatten_table(table)
        if grid and grid[0] and grid[0][0].strip().lower() == "product":
            tables.append(grid)
    return tables


def variant_row(soup: BeautifulSoup, variant: str, variants: list[str]) -> dict[str, str]:
    """This variant's row from the per-variant table(s) (first column "Product")."""
    vre = _variant_re(variants)
    for grid in _variant_tables(soup):
        header = [h.strip() for h in grid[0]]
        for row in grid[1:]:
            if variant.upper() in _names_in(row[0], vre):
                return dict(zip(header, (c.strip() for c in row)))
    return {}


def choose_slotmap_table(
    soup: BeautifulSoup,
    variant: str,
    variants: list[str],
    ram: str,
) -> Tag | None:
    """The slot map for *variant* (first match wins).

    1. A heading naming the variant.  2. A heading naming the variant's RAM size.
    3. A heading saying "other models".  4. The first slot map.
    """
    sections = slotmap_sections(soup)
    if not sections:
        return None
    vre = _variant_re(variants)
    for heading, table in sections:
        if variant.upper() in _names_in(heading, vre):
            return table
    kb = _KB_RE.search(ram or "")
    if kb:
        for heading, table in sections:
            if re.search(rf"(?<!\d){kb.group(1)}\s*kB", heading, re.IGNORECASE):
                return table
    for heading, table in sections:
        if _OTHER_RE.search(heading):
            return table
    return sections[0][1]


def build_variant_specs(
    series: BeautifulSoup,
    member_title: str,
    *,
    page_title: str | None = None,
) -> tuple[dict[str, str] | None, Tag | None]:
    """Specs dict and slot map table for one member of a series page.

    Returns ``(None, None)`` when the series page has no specs table. Fields
    that cannot be resolved for the variant are left out (and logged).
    """
    from .msxorg import _find_specs_table  # local import: msxorg imports this module

    specs = _find_specs_table(series)
    if not specs:
        return None, None

    brand = re.sub(r"\s*\(.*?\)\s*", "", specs.get("Brand", "")).strip()
    variant = _strip_brand(member_title, brand)
    variants = sorted(
        {_strip_brand(a.get_text(" ", strip=True), brand) for a in series.select("#mw-pages a")}
        | {v.strip() for v in specs.get("Model", "").split("/") if v.strip()}
        | {_strip_brand(row[0], brand) for grid in _variant_tables(series) for row in grid[1:] if row}
        | {variant}
    )
    row = variant_row(series, variant, variants)
    label = page_title or member_title

    def from_table(field: str) -> str | None:
        column = _TABLE_COLUMN_FOR_FIELD.get(field)
        value = row.get(column, "") if column else ""
        return value or None

    out: dict[str, str] = {"Brand": brand, "Model": variant}

    # The variant table's Region is per variant by definition, so it beats the
    # specs Region, which is often a family-wide list ("Argentina, Italy, Japan, Spain").
    region = from_table("Region")
    if region is None and specs.get("Region") is not None:
        region = resolve_value(specs["Region"], variant, variants)
        if region is not None and _SEE_TABLE_RE.search(region):
            region = None
    if region:
        out["Region"] = expand_region_codes(region)

    for field, raw in specs.items():
        if field in ("Brand", "Model", "Region"):
            continue
        value = resolve_value(
            raw, variant, variants, region=out.get("Region") if field == "Year" else None
        )
        if value is not None and _SEE_TABLE_RE.search(value):
            value = from_table(field)
        if value is None and field in _TABLE_COLUMN_FOR_FIELD:
            value = from_table(field)
        if value is None:
            if field in _PARSED_FIELDS:
                log.info("[msxorg:series] Unresolved | page=%s field=%s value=%r",
                         label, field, _normalise(raw))
            continue
        out[field] = value

    table = choose_slotmap_table(series, variant, variants, out.get("RAM", ""))
    return out, table

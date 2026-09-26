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
from typing import NamedTuple
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from .msxorg_slotmap import _flatten_table, slotmap_sections
from .revisions import REVISION_RE, revision_numbers

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


class _Segment(NamedTuple):
    """A piece of a value and whom it applies to."""
    text: str
    names: frozenset[str]   # variant names it is qualified for (upper case)
    revs: frozenset[int]    # revision numbers it is qualified for
    other: bool             # qualified "other models"


def _label_matches(text: str) -> list[tuple[int, int, frozenset[str], frozenset[int]]]:
    """``CODE:`` and ``2nd version:`` labels as (start, end, names, revisions)."""
    out = [(m.start(), m.end(), frozenset({m.group(1).upper()}), frozenset())
           for m in _CODE_LABEL_RE.finditer(text)]
    for m in REVISION_RE.finditer(text):
        colon = re.match(r"\s*:", text[m.end():])
        if colon:
            out.append((m.start(), m.end() + colon.end(), frozenset(), frozenset(revision_numbers(m.group(0)))))
    return sorted(out)


def _segments(text: str, vre: re.Pattern[str]) -> list[_Segment] | None:
    """Split a qualified value into segments; None when nothing is qualified (shared)."""
    def qualifier(inner: str) -> tuple[frozenset[str], frozenset[int], bool]:
        return (frozenset(_names_in(inner, vre)), frozenset(revision_numbers(inner)),
                bool(_OTHER_RE.search(inner)))

    # Label-colon: "HB-10: Japan HB-10B: United Kingdom" / "1st version: X, 2nd version: Y"
    labels = _label_matches(text)
    if len(labels) >= 2:
        # Text before the first label applies to every segment:
        # "PSG clone (1st version: X, 2nd version: Y)" -> "PSG clone X" / "PSG clone Y".
        lead = text[:labels[0][0]].rstrip(" (:")

        def piece(start: int, stop: int) -> str:
            body = _strip_separators(text[start:stop])
            if body.count(")") > body.count("("):
                body = body.rstrip(") ")
            return f"{lead} {body}".strip() if lead else body

        return [_Segment(piece(end, labels[i + 1][0] if i + 1 < len(labels) else len(text)), names, revs, False)
                for i, (_, end, names, revs) in enumerate(labels)]

    # Leading label: "(HB-101) X - (HB-101P) Y" / "(1st version) X (2nd version) Y"
    groups = [m for m in re.finditer(r"\(([^()]*)\)\s*", text) if any(qualifier(m.group(1))[:2])]
    if groups and groups[0].start() == 0:
        return [_Segment(_strip_separators(text[m.end():groups[i + 1].start() if i + 1 < len(groups) else len(text)]),
                         *qualifier(m.group(1)))
                for i, m in enumerate(groups)]

    # "in" qualifier: "TCX-1010 in HX-21, TCX-1012 in HX-21F"
    parts = [p for p in re.split(r",\s*", text) if p]
    in_parts = [re.match(rf"(.+?)\s+in\s+(?=(?:{vre.pattern}))(.+)$", p, re.IGNORECASE) for p in parts]
    if len(parts) >= 2 and all(in_parts):
        return [_Segment(m.group(1).strip(), frozenset(_names_in(m.group(2), vre)), frozenset(), False)
                for m in in_parts]

    # Trailing qualifier: "X (HB-10) or Y (other models)" / "X (version 1) or Y (version 2)"
    segments: list[_Segment] = []
    start = 0
    for m in re.finditer(r"\(([^()]*)\)", text):
        names, revs, other = qualifier(m.group(1))
        if names or revs or other:
            segments.append(_Segment(_strip_separators(text[start:m.start()]), names, revs, other))
            start = m.end()
    if segments:
        return segments
    if _names_in(text, vre) or revision_numbers(text) or _OTHER_RE.search(text):
        return []   # qualified, but in no form we can split
    return None


def resolve_value(
    value: str,
    variant: str,
    variants: list[str],
    *,
    region: str | None = None,
    revision: int = 1,
    override: bool = False,
) -> str | None:
    """The part of a specs *value* that applies to *variant* (and *revision*).

    Returns ``None`` when the value names variants but not this one (and has no
    "other models" part): an unresolved value must never be filled with another
    variant's text. ``region`` enables region-qualified resolution (Year).

    Revisions (see scraper/revisions.py): the base record (``revision=1``)
    skips segments marked for a later revision. With ``override=True`` only a
    segment marked for ``revision`` is returned — anything else is inherited
    from the base record, so the result is ``None``.
    """
    text = _normalise(value)
    vre = _variant_re(variants)
    target = variant.upper()

    if region is not None and not override and len(_REGION_QUALIFIER_RE.findall(text)) >= 2:
        return _resolve_by_region(text, region)

    segments = _segments(text, vre)
    if segments is None:
        return None if override else text   # shared by every variant and revision

    def for_variant(seg: _Segment) -> bool:
        return target in seg.names or not seg.names

    if override:
        for seg in segments:
            if revision in seg.revs and for_variant(seg) and not seg.other:
                return seg.text or None
        return None

    named = [s for s in segments if target in s.names]
    unnamed = [s for s in segments if not s.names and not s.other]
    ranked = (
        [s for s in named if revision in s.revs]
        + [s for s in named if not s.revs]
        + [s for s in unnamed if revision in s.revs]
        + [s for s in unnamed if not s.revs]
    )
    # "other models" means other *variants*: never for a variant named elsewhere.
    if not named:
        ranked += [s for s in segments if s.other and (not s.revs or revision in s.revs)]
    return (ranked[0].text or None) if ranked else None


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
    *,
    revision: int = 1,
    override: bool = False,
) -> Tag | None:
    """The slot map for *variant* (and *revision*); first match wins.

    Headings marked for another revision ("2nd Gen HB-F500") are skipped.
    1. Names the variant and this revision.  2. Names the variant.
    3. Names this revision only.  4. Names the variant's RAM size.
    5. Says "other models".  6. The first remaining slot map.
    With ``override=True`` only a heading marked for ``revision`` counts
    (else None: the revision inherits the base slot map).
    """
    sections = slotmap_sections(soup)
    if not sections:
        return None
    vre = _variant_re(variants)
    target = variant.upper()
    tagged = [(heading, table, _names_in(heading, vre), revision_numbers(heading))
              for heading, table in sections]

    if override:
        for _, table, names, revs in tagged:
            if revision in revs and (target in names or not names):
                return table
        return None

    usable = [t for t in tagged if not t[3] or revision in t[3]]
    for heading, table, names, revs in usable:
        if target in names and revision in revs:
            return table
    for heading, table, names, revs in usable:
        if target in names:
            return table
    for heading, table, names, revs in usable:
        if not names and revision in revs:
            return table
    kb = _KB_RE.search(ram or "")
    if kb:
        for heading, table, *_ in usable:
            if re.search(rf"(?<!\d){kb.group(1)}\s*kB", heading, re.IGNORECASE):
                return table
    for heading, table, *_ in usable:
        if _OTHER_RE.search(heading):
            return table
    return (usable or tagged)[0][1]


class VariantContext(NamedTuple):
    """Where one variant's data lives: a series page, or a model's own page."""
    specs: dict[str, str]    # raw specs table of that page
    soup: BeautifulSoup      # the page (variant table, slot maps)
    brand: str
    variant: str
    variants: list[str]      # every name the page may use to qualify a value


def series_context(series: BeautifulSoup, member_title: str) -> VariantContext | None:
    """Context for one member of a series page; None without a specs table."""
    from .msxorg import _find_specs_table  # local import: msxorg imports this module

    specs = _find_specs_table(series)
    if not specs:
        return None
    brand = re.sub(r"\s*\(.*?\)\s*", "", specs.get("Brand", "")).strip()
    variant = _strip_brand(member_title, brand)
    variants = sorted(
        {_strip_brand(a.get_text(" ", strip=True), brand) for a in series.select("#mw-pages a")}
        | {v.strip() for v in specs.get("Model", "").split("/") if v.strip()}
        | {_strip_brand(row[0], brand) for grid in _variant_tables(series) for row in grid[1:] if row}
        | {variant}
    )
    return VariantContext(specs, series, brand, variant, variants)


def page_context(page: BeautifulSoup, specs: dict[str, str], brand: str,
                 model: str, models: list[str]) -> VariantContext:
    """Context for a model page that has its own specs table."""
    return VariantContext(specs, page, brand, model, sorted(set(models) | {model}))


def revisions_in(ctx: VariantContext) -> list[int]:
    """Revision numbers >= 2 referenced by the page's specs values or slot map headings."""
    found: set[int] = set()
    for value in ctx.specs.values():
        found |= revision_numbers(value)
    for heading, _ in slotmap_sections(ctx.soup):
        found |= revision_numbers(heading)
    return sorted(n for n in found if n >= 2)


def resolve_specs(
    ctx: VariantContext,
    *,
    revision: int = 1,
    override: bool = False,
    page_title: str | None = None,
) -> tuple[dict[str, str], Tag | None]:
    """The specs dict and slot map table for ``ctx.variant`` at *revision*.

    Base (``override=False``): every field resolved for the variant; fields that
    cannot be resolved are left out (and logged). Override (``override=True``):
    only the fields and slot map marked for *revision* — everything else is
    inherited from the base record by the caller.
    """
    variant, variants, specs = ctx.variant, ctx.variants, ctx.specs
    label = page_title or variant
    out: dict[str, str] = {}

    if override:
        for field, raw in specs.items():
            if field in ("Brand", "Model"):
                continue
            value = resolve_value(raw, variant, variants, revision=revision, override=True)
            if value is not None:
                out[field] = value
        table = choose_slotmap_table(ctx.soup, variant, variants, out.get("RAM", ""),
                                     revision=revision, override=True)
        return out, table

    row = variant_row(ctx.soup, variant, variants)

    def from_table(field: str) -> str | None:
        column = _TABLE_COLUMN_FOR_FIELD.get(field)
        value = row.get(column, "") if column else ""
        return value or None

    out.update({"Brand": ctx.brand, "Model": variant})

    # The variant table's Region is per variant by definition, so it beats the
    # specs Region, which is often a family-wide list ("Argentina, Italy, Japan, Spain").
    region = from_table("Region")
    # When the page lists per-variant regions and this variant is not among
    # them, a region shared by the whole family ("Europe, Japan") is not this
    # variant's region: leave it unset rather than guess.
    table_has_region = any("Region" in (h.strip() for h in grid[0]) for grid in _variant_tables(ctx.soup))
    family_wide = table_has_region and not row
    if region is None and specs.get("Region") is not None:
        raw_region = _normalise(specs["Region"])
        if not (family_wide and _segments(raw_region, _variant_re(variants)) is None):
            region = resolve_value(raw_region, variant, variants, revision=revision)
        if region is not None and _SEE_TABLE_RE.search(region):
            region = None
    if region:
        out["Region"] = expand_region_codes(region)

    for field, raw in specs.items():
        if field in ("Brand", "Model", "Region"):
            continue
        value = resolve_value(raw, variant, variants, revision=revision,
                              region=out.get("Region") if field == "Year" else None)
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

    table = choose_slotmap_table(ctx.soup, variant, variants, out.get("RAM", ""), revision=revision)
    return out, table


def build_variant_specs(
    series: BeautifulSoup,
    member_title: str,
    *,
    page_title: str | None = None,
) -> tuple[dict[str, str] | None, Tag | None]:
    """Specs dict and slot map table for one member of a series page.

    Returns ``(None, None)`` when the series page has no specs table.
    """
    ctx = series_context(series, member_title)
    if ctx is None:
        return None, None
    return resolve_specs(ctx, page_title=page_title or member_title)

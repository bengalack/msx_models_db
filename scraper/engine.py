"""Split the scraped Engine text into semi-custom and full-custom ASIC values.

The msx.org "Chipset" field is free prose ("probably Yamaha S3527", "Gate arrays
Toshiba TCX-1008, TCX-2001 and TCX-2002"). This module turns it into two short,
sortable cell values using the vocabulary in ``data/engine-chips.json``.

Design: .claude/artifacts/planning/2026-09-21-engine-columns-design.md
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

CHIPS_PATH = Path(__file__).parent.parent / "data" / "engine-chips.json"

# Whole value is only question marks / blank -> unknown.
_UNKNOWN_RE = re.compile(r"^[?\s]*$")
# "probably" / "possibly" / a leading "?" mean: take the chip and append "?".
_UNCERTAIN_WORD_RE = re.compile(r"^(?:probably|possibly)\s+", re.IGNORECASE)
_UNCERTAIN_MARK_RE = re.compile(r"^\?\s*")
# T9769 in all its spellings, with an optional A/B/C qualifier.
_T9769_RE = re.compile(
    r"\bT9769x?\b(?:\s+model)?\s*\(?((?:[ABC](?:\s+or\s+[ABC])*)?)\)?", re.IGNORECASE
)
_ULA_RE = re.compile(r"(?:(\d+)\s+)?\bULA\b.*", re.IGNORECASE)
_NONE_RE = re.compile(r"\bnone\b", re.IGNORECASE)
# "none ... for /00 version, S3527 for /19 ... versions" -> the variants are alternatives.
_VARIANT_RE = re.compile(r"\bfor\b.*\bversions?\b", re.IGNORECASE)
_ALTERNATIVE_RE = re.compile(r"\bor\b", re.IGNORECASE)
# Looks like a chip designator but is not in the dictionary -> warn, don't guess.
_CHIP_SHAPED_RE = re.compile(r"\b[A-Za-z]{1,4}-?\d{3,5}[A-Za-z0-9-]*\b")

NONE = "None"


@dataclass(frozen=True)
class ChipDictionary:
    """Vocabulary loaded from data/engine-chips.json."""

    semi_custom: tuple[str, ...] = ()
    full_custom: tuple[str, ...] = ()
    vendors: tuple[str, ...] = ()
    filler: tuple[str, ...] = ()
    explanatory: tuple[str, ...] = ()
    links: dict[str, str] = field(default_factory=dict)   # chip id -> URL
    _vendor_re: re.Pattern[str] | None = field(default=None, compare=False)
    _filler_res: tuple[re.Pattern[str], ...] = field(default=(), compare=False)
    _explanatory_re: re.Pattern[str] | None = field(default=None, compare=False)


def load_chip_dictionary(path: Path = CHIPS_PATH) -> ChipDictionary:
    """Load and validate the chip vocabulary.

    Raises ``ValueError`` on malformed input (fail fast, before any scraping) and
    ``FileNotFoundError`` when the file is missing.
    """
    with open(path, encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Engine chip dictionary is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Engine chip dictionary must be a JSON object")

    def _list(key: str) -> tuple[str, ...]:
        value = raw.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ValueError(f"Engine chip dictionary: {key!r} must be a list of non-empty strings")
        return tuple(value)

    semi, full = _list("semi_custom"), _list("full_custom")
    overlap = set(semi) & set(full)
    if overlap:
        raise ValueError(
            f"Engine chip dictionary: {sorted(overlap)} listed as both semi-custom and full-custom"
        )

    links = raw.get("links", {})
    if not isinstance(links, dict) or not all(isinstance(k, str) and isinstance(v, str) and v
                                               for k, v in links.items()):
        raise ValueError("Engine chip dictionary: 'links' must map chip ids to URL strings")
    unknown = sorted(set(links) - set(semi) - set(full))
    if unknown:
        raise ValueError(f"Engine chip dictionary: links for unknown chips {unknown}")

    vendors = _list("vendors")
    filler = _list("filler")
    explanatory = _list("explanatory_parentheticals")
    for pattern in filler + explanatory:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Engine chip dictionary: invalid pattern {pattern!r}: {exc}") from exc

    log.info(
        "Loaded engine chips: %d semi-custom, %d full-custom from %s",
        len(semi), len(full), path,
    )
    return ChipDictionary(
        semi_custom=semi,
        full_custom=full,
        vendors=vendors,
        filler=filler,
        explanatory=explanatory,
        links=dict(links),
        _vendor_re=re.compile("|".join(re.escape(v) for v in vendors), re.IGNORECASE) if vendors else None,
        _filler_res=tuple(re.compile(rf"\b{p}\b", re.IGNORECASE) for p in filler),
        _explanatory_re=(
            re.compile(rf"\((?:{'|'.join(explanatory)})[^)]*\)", re.IGNORECASE) if explanatory else None
        ),
    )


def normalise(raw: str) -> str:
    """Collapse whitespace (incl. line breaks) and tidy stray spaces around punctuation."""
    text = raw.replace(" ", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+,", ",", text)
    return text


def _family(chip: str) -> str:
    """Alphabetic prefix of a chip id — decides '/' vs ' and ' when joining."""
    match = re.match(r"^[A-Za-z]+", chip)
    return (match.group(0) if match else chip).upper()


def _join(chips: list[str], source: str) -> str:
    """Same family (or the source already used '/') -> '/', otherwise ' and '."""
    if len(chips) == 1:
        return chips[0]
    same_family = len({_family(c) for c in chips}) == 1
    return ("/" if same_family or "/" in source else " and ").join(chips)


def parse_engine(
    raw: str | None,
    chips: ChipDictionary,
    *,
    context: str = "",
) -> tuple[str | None, str | None]:
    """Return ``(semi_custom, full_custom)`` cell values for one scraped Engine text.

    ``None`` means "unknown" (the grid renders an em-dash); ``"None"`` means the
    source was understood and there is no ASIC of that kind.
    """
    if raw is None:
        return None, None
    source = normalise(raw)
    if _UNKNOWN_RE.match(source):
        return None, None

    work = chips._explanatory_re.sub(" ", source) if chips._explanatory_re else source

    uncertain = False
    if _UNCERTAIN_MARK_RE.match(work):
        work = _UNCERTAIN_MARK_RE.sub("", work)
        uncertain = True
    if _UNCERTAIN_WORD_RE.match(work):
        work = _UNCERTAIN_WORD_RE.sub("", work)
        uncertain = True

    says_none = bool(_NONE_RE.search(work))
    none_is_variant = bool(_VARIANT_RE.search(work))
    alternatives = bool(_ALTERNATIVE_RE.search(work)) or none_is_variant

    cleaned = chips._vendor_re.sub(" ", work) if chips._vendor_re else work
    for pattern in chips._filler_res:
        cleaned = pattern.sub(" ", cleaned)

    semi: list[str] = []
    full: list[str] = []

    match = _T9769_RE.search(cleaned)
    if match:
        letters = [c.upper() for c in re.findall(r"[ABC]", match.group(1) or "", re.IGNORECASE)]
        full.append("T9769" + (f" ({' or '.join(letters)})" if letters else ""))
        cleaned = _T9769_RE.sub(" ", cleaned)

    if re.search(r"\bFPGA\b", cleaned, re.IGNORECASE):
        full.append("FPGA")
        cleaned = re.sub(r"\S*FPGA\S*", " ", cleaned, flags=re.IGNORECASE)

    ula = _ULA_RE.search(cleaned)
    if ula:
        count = f"{ula.group(1)} " if ula.group(1) else ""
        semi.append(f"{count}ULA + std logic")
        cleaned = _ULA_RE.sub(" ", cleaned)

    # Chips appear in source order, not dictionary order.
    found: list[tuple[int, str, list[str]]] = []
    for dictionary, bucket in ((chips.semi_custom, semi), (chips.full_custom, full)):
        for chip in sorted(dictionary, key=len, reverse=True):
            hit = re.search(rf"\b{re.escape(chip)}\b", cleaned, re.IGNORECASE)
            if hit:
                found.append((hit.start(), chip, bucket))
                cleaned = cleaned[: hit.start()] + " " * (hit.end() - hit.start()) + cleaned[hit.end():]
    for _, chip, bucket in sorted(found, key=lambda item: item[0]):
        if chip not in bucket:
            bucket.append(chip)

    for leftover in _CHIP_SHAPED_RE.findall(cleaned):
        log.warning(
            "[engine:unknown_chip] Not in data/engine-chips.json | chip=%s source=%r%s",
            leftover, source, f" model={context}" if context else "",
        )

    def render(bucket: list[str]) -> str | None:
        if not bucket:
            # Understood source (named a chip, or said "none") -> confirmed absent.
            return NONE if (says_none or semi or full) else None
        text = " or ".join(bucket) if (alternatives and len(bucket) > 1) else _join(bucket, source)
        if says_none and none_is_variant:
            text = f"{NONE} or {text}"
        return f"{text}?" if uncertain else text

    return render(semi), render(full)

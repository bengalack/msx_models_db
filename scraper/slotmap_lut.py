"""Slot map Look-Up Table loader and utilities.

The LUT is a JSON array of rules evaluated in order; the first matching rule
wins.  Each rule has:

    element     -- XML element name (pipe-separated alternatives) or
                   "__sentinel__" for internal sentinels.  null means
                   match any element (id_pattern must then discriminate).
    id_pattern  -- Case-insensitive regex matched against the XML ``id``
                   attribute.  null means match-all (element type alone
                   determines the match).
    abbr        -- Short abbreviation shown in the grid cell.
    tooltip     -- Human-readable description shown on hover.

Usage::

    from scraper.slotmap_lut import load_slotmap_lut, compact_lut

    rules = load_slotmap_lut("data/slotmap-lut.json")
    lut   = compact_lut(rules)   # {abbr: tooltip} — embedded in data.js
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_slotmap_lut(path: str | Path) -> list[dict]:
    """Load and validate the slot map LUT from *path*.

    Returns an ordered list of rule dicts.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError: if the file is not valid JSON, contains duplicate ``abbr``
                    values, or contains a malformed ``id_pattern`` regex.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Slot map LUT not found: {path}")

    with path.open(encoding="utf-8") as fh:
        try:
            rules: list[dict] = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Slot map LUT is not valid JSON: {exc}") from exc

    if not isinstance(rules, list):
        raise ValueError("Slot map LUT must be a JSON array")

    seen_abbrs: set[str] = set()
    for i, rule in enumerate(rules):
        abbr = rule.get("abbr")
        if abbr in seen_abbrs:
            raise ValueError(
                f"Slot map LUT rule {i}: duplicate abbr {abbr!r}"
            )
        seen_abbrs.add(abbr)

        id_pattern = rule.get("id_pattern")
        if id_pattern is not None:
            try:
                re.compile(id_pattern, re.IGNORECASE)
            except re.error as exc:
                raise ValueError(
                    f"Slot map LUT rule {i} (abbr={abbr!r}): "
                    f"invalid id_pattern {id_pattern!r}: {exc}"
                ) from exc

    print(f"[INFO] Loaded slotmap LUT: {len(rules)} rules from {path}")
    return rules


def compact_lut(rules: list[dict]) -> dict[str, str]:
    """Return a flat ``{abbr: tooltip}`` dict for embedding in ``data.js``.

    Only ``abbr`` and ``tooltip`` are included — no rule metadata.
    """
    return {rule["abbr"]: rule["tooltip"] for rule in rules}

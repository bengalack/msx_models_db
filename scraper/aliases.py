"""Alias LUT — normalize field values to canonical names at merge time."""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_aliases(path: str | Path) -> dict[str, dict[str, str]]:
    """Load and validate an alias JSON file.

    Returns an inverted lookup: {column: {alias_lower: canonical}}.
    Raises FileNotFoundError if the file is absent.
    Raises ValueError on malformed JSON, wrong structure, or conflicting aliases.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Alias LUT not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object at top level")

    inverted: dict[str, dict[str, str]] = {}
    for column, mappings in raw.items():
        if not isinstance(mappings, dict):
            raise ValueError(
                f"{path}: value for column '{column}' must be an object"
            )
        col_lut: dict[str, str] = {}
        for canonical, aliases in mappings.items():
            if not isinstance(aliases, list):
                raise ValueError(
                    f"{path}: aliases for '{canonical}' in column '{column}' must be a list"
                )
            for alias in aliases:
                key = alias.lower()
                if key in col_lut and col_lut[key] != canonical:
                    raise ValueError(
                        f"{path}: duplicate alias '{alias}' in column '{column}': "
                        f"maps to both '{col_lut[key]}' and '{canonical}'"
                    )
                col_lut[key] = canonical
        inverted[column] = col_lut

    log.debug("Loaded alias LUT: %d column(s) from %s", len(inverted), path)
    return inverted


def apply_aliases(record: dict, lut: dict[str, dict[str, str]]) -> None:
    """Replace alias values in *record* with their canonical names (in-place)."""
    for column, alias_map in lut.items():
        value = record.get(column)
        if not isinstance(value, str):
            continue
        canonical = alias_map.get(value.lower())
        if canonical is not None:
            record[column] = canonical

"""Alias LUT — normalize field values to canonical names at merge time."""
from __future__ import annotations

import json
from pathlib import Path


def load_aliases(path: Path) -> dict[str, dict[str, str]]:
    """Load and validate an alias JSON file.

    Returns an inverted lookup: {column: {alias_lower: canonical}}.
    Raises FileNotFoundError if the file is absent.
    Raises ValueError on malformed JSON, wrong structure, or conflicting aliases.
    """
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
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
            for alias in aliases:
                key = alias.lower()
                if key in col_lut and col_lut[key] != canonical:
                    raise ValueError(
                        f"{path}: duplicate alias '{alias}' in column '{column}': "
                        f"maps to both '{col_lut[key]}' and '{canonical}'"
                    )
                col_lut[key] = canonical
        inverted[column] = col_lut

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

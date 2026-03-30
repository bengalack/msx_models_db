"""Merge model data from openMSX and msx.org sources."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Natural key ──────────────────────────────────────────────────────


def natural_key(model: dict[str, Any]) -> str:
    """Build a stable natural key: 'manufacturer|model' (lowercased, trimmed)."""
    mfr = model.get("manufacturer", "").lower().strip()
    mdl = model.get("model", "").lower().strip()
    return f"{mfr}|{mdl}"


# ── Normalization ────────────────────────────────────────────────────
# Auto-resolve known formatting differences so they don't show as conflicts.

_REGION_NORM: dict[str, str] = {
    "south korea": "Korea",
    "korea": "Korea",
    "the netherlands": "Netherlands",
    "netherlands": "Netherlands",
}

_FM_NORM: dict[str, str] = {
    "msx-music": "MSX-MUSIC",
    "msx music": "MSX-MUSIC",
    "msx-audio": "MSX-AUDIO",
    "msx audio": "MSX-AUDIO",
    "moonsound": "MoonSound",
}

_STANDARD_NORM: dict[str, str] = {
    "msx2": "MSX2",
    "msx2+": "MSX2+",
    "turbo r": "turbo R",
    "msxturbor": "turbo R",
}


def _normalise_region(val: str) -> str:
    return _REGION_NORM.get(val.lower().strip(), val)


def _normalise_fm(val: str) -> str:
    parts = [p.strip() for p in val.split(",")]
    return ", ".join(_FM_NORM.get(p.lower(), p) for p in parts)


def _normalise_standard(val: str) -> str:
    return _STANDARD_NORM.get(val.lower().strip(), val)


def _normalise_keyboard(val: str) -> str:
    """Normalise keyboard layout — prefer the more detailed msx.org value."""
    return val  # Don't normalise; let preference rules handle it.


# Fields where msx.org generally has richer info.
_PREFER_MSXORG: set[str] = {"keyboard_layout", "region"}

# Fields where openMSX is more reliable (hardware-level).
_PREFER_OPENMSX: set[str] = {"cartridge_slots", "vdp", "vram_kb", "main_ram_kb", "psg"}

# Normalisation functions per-field.
_FIELD_NORMALISERS: dict[str, Any] = {
    "region": _normalise_region,
    "fm_chip": _normalise_fm,
    "standard": _normalise_standard,
}


def normalise_model(model: dict[str, Any]) -> dict[str, Any]:
    """Apply field-level normalisation to a model dict."""
    out = dict(model)
    for field, fn in _FIELD_NORMALISERS.items():
        if field in out and isinstance(out[field], str):
            out[field] = fn(out[field])
    return out


# ── Merge logic ──────────────────────────────────────────────────────


def merge_models(
    openmsx: list[dict[str, Any]],
    msxorg: list[dict[str, Any]],
    *,
    resolutions: dict[str, dict[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge models from both sources.

    Args:
        openmsx: Models from openMSX scraper.
        msxorg: Models from msx.org scraper.
        resolutions: Optional pre-resolved conflicts.
            Format: {natural_key: {field: "openmsx"|"msxorg"}}

    Returns:
        (merged_models, unresolved_conflicts)
        where unresolved_conflicts is a list of conflict dicts for the maintainer.
    """
    if resolutions is None:
        resolutions = {}

    # Index by natural key.
    o_by_key: dict[str, dict[str, Any]] = {}
    for m in openmsx:
        nm = normalise_model(m)
        o_by_key[natural_key(nm)] = nm

    m_by_key: dict[str, dict[str, Any]] = {}
    for m in msxorg:
        nm = normalise_model(m)
        m_by_key[natural_key(nm)] = nm

    all_keys = sorted(set(o_by_key.keys()) | set(m_by_key.keys()))
    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for key in all_keys:
        o_model = o_by_key.get(key)
        m_model = m_by_key.get(key)

        if o_model and not m_model:
            # openMSX-only.
            merged.append(o_model)
            continue
        if m_model and not o_model:
            # msx.org-only.
            merged.append(m_model)
            continue

        # Both sources — merge field by field.
        assert o_model is not None and m_model is not None
        result, model_conflicts = _merge_single(key, o_model, m_model, resolutions.get(key, {}))
        merged.append(result)
        if model_conflicts:
            conflicts.extend(model_conflicts)

    log.info(
        "Merge: %d total models (%d matched, %d openMSX-only, %d msx.org-only), %d unresolved conflicts",
        len(merged),
        len(set(o_by_key.keys()) & set(m_by_key.keys())),
        len(set(o_by_key.keys()) - set(m_by_key.keys())),
        len(set(m_by_key.keys()) - set(o_by_key.keys())),
        len(conflicts),
    )
    return merged, conflicts


# Fields that are source-specific metadata (not merged as data fields).
_META_FIELDS = {"openmsx_id", "msxorg_title"}


def _merge_single(
    key: str,
    o: dict[str, Any],
    m: dict[str, Any],
    resolutions: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge a single model from both sources. Returns (merged_dict, conflict_list)."""
    all_fields = sorted(set(o.keys()) | set(m.keys()))
    result: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []

    for field in all_fields:
        ov = o.get(field)
        mv = m.get(field)

        # Meta fields — keep both.
        if field in _META_FIELDS:
            if ov is not None:
                result[field] = ov
            if mv is not None:
                result[field] = mv
            continue

        # Only one source has this field — use it.
        if ov is not None and mv is None:
            result[field] = ov
            continue
        if mv is not None and ov is None:
            result[field] = mv
            continue
        if ov is None and mv is None:
            continue

        # Both have it — check for conflict.
        if str(ov) == str(mv):
            result[field] = ov
            continue

        # Check pre-resolved.
        if field in resolutions:
            winner = resolutions[field]
            result[field] = ov if winner == "openmsx" else mv
            continue

        # Apply preference rules.
        if field in _PREFER_OPENMSX:
            result[field] = ov
            continue
        if field in _PREFER_MSXORG:
            result[field] = mv
            continue

        # Genuine unresolved conflict.
        # Default to openMSX (more authoritative for hardware specs), but record the conflict.
        result[field] = ov
        conflicts.append({
            "natural_key": key,
            "field": field,
            "openmsx_value": ov,
            "msxorg_value": mv,
            "used": "openmsx",
        })

    return result, conflicts


# ── Conflict resolution file I/O ─────────────────────────────────────


def load_resolutions(path: Path) -> dict[str, dict[str, str]]:
    """Load a conflict resolution JSON file.

    Format: [{"natural_key": "...", "field": "...", "use": "openmsx"|"msxorg"}, ...]
    Returns: {natural_key: {field: source}}
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    result: dict[str, dict[str, str]] = {}
    for entry in entries:
        nk = entry["natural_key"]
        result.setdefault(nk, {})[entry["field"]] = entry["use"]
    return result


def save_conflicts(conflicts: list[dict[str, Any]], path: Path) -> None:
    """Save unresolved conflicts to a JSON file for maintainer review.

    The maintainer edits the 'use' field to 'openmsx' or 'msxorg',
    then re-runs merge with --resolutions pointing to this file.
    """
    entries = []
    for c in conflicts:
        entries.append({
            "natural_key": c["natural_key"],
            "field": c["field"],
            "openmsx_value": c["openmsx_value"],
            "msxorg_value": c["msxorg_value"],
            "use": c["used"],  # default choice, maintainer can override
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")


def print_conflict_summary(conflicts: list[dict[str, Any]]) -> None:
    """Print a human-readable conflict summary to stderr."""
    if not conflicts:
        log.info("No unresolved conflicts!")
        return

    # Group by field.
    by_field: dict[str, list[dict[str, Any]]] = {}
    for c in conflicts:
        by_field.setdefault(c["field"], []).append(c)

    log.warning("%d unresolved conflicts across %d fields:", len(conflicts), len(by_field))
    for field, items in sorted(by_field.items()):
        log.warning("  %s: %d conflicts", field, len(items))
        for item in items[:5]:
            log.warning(
                "    %s: openMSX=%r vs msx.org=%r [using %s]",
                item["natural_key"], item["openmsx_value"], item["msxorg_value"], item["used"],
            )
        if len(items) > 5:
            log.warning("    ... and %d more", len(items) - 5)

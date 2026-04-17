"""Merge model data from openMSX and msx.org sources."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from scraper.aliases import AliasLUT, apply_aliases, load_aliases

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
    # YM2413 aliases — all normalize to the chip part number
    "msx-music": "YM2413",
    "msx music": "YM2413",
    "fm-pac": "YM2413",
    "fmpac": "YM2413",
    "fm-pak": "YM2413",
    "fmpak": "YM2413",
    "ym2413": "YM2413",
    # Other FM chips
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
_PREFER_OPENMSX: set[str] = {"scraped_cart_slots", "vdp", "vram_kb", "main_ram_kb", "psg"}

# Matches CS/ES slot abbreviations with optional number and ! suffix.
# The number is optional to tolerate bare "CS"/"ES" that can appear in stale
# msx.org raw data when the scraper fell back to raw cell text.
# _renumber_cs_es will assign proper sequential numbers in all cases.
_CS_ES_RE = re.compile(r"^(CS|ES)(\d*)(!?)$")


def _is_cs_or_es(value: Any) -> bool:
    """Return True if *value* is a CS/ES slot abbreviation (with or without number)."""
    return isinstance(value, str) and bool(_CS_ES_RE.match(value))


def _is_slot_type(value: Any) -> bool:
    """Return True if *value* is any slot-type abbreviation: CS*, ES*, or EXP.

    Used in merge preference: when both sources assign a slot-type value to the
    same slotmap cell, msx.org always wins (it carries human-curated slot-type
    information that openMSX XML cannot express, e.g. expansion-bus vs cartridge).
    """
    return _is_cs_or_es(value) or value == "EXP"

# Normalisation functions per-field.
_FIELD_NORMALISERS: dict[str, Any] = {
    "region": _normalise_region,
    "fm_chip": _normalise_fm,
    "generation": _normalise_standard,
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
    local: list[dict[str, Any]] | None = None,
    resolutions: dict[str, dict[str, str]] | None = None,
    alias_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Merge models from all sources.

    Args:
        openmsx: Models from openMSX scraper.
        msxorg: Models from msx.org scraper.
        local: Models from the local supplemental file (highest authority).
        resolutions: Optional pre-resolved conflicts.
            Format: {natural_key: {field: "openmsx"|"msxorg"}}
        alias_path: Optional path to aliases.json; when provided, alias values
            in each record are replaced with their canonical form before
            natural_key() matching.

    Returns:
        merged_models list (unresolved conflicts are logged via print_conflict_summary).
    """
    if resolutions is None:
        resolutions = {}
    if local is None:
        local = []

    alias_lut: AliasLUT = AliasLUT()
    if alias_path is not None:
        alias_lut = load_aliases(alias_path)
    for record in [*openmsx, *(msxorg or []), *(local or [])]:
        apply_aliases(record, alias_lut)

    # Index by natural key.
    o_by_key: dict[str, dict[str, Any]] = {}
    for m in openmsx:
        nm = normalise_model(m)
        o_by_key[natural_key(nm)] = nm

    m_by_key: dict[str, dict[str, Any]] = {}
    for m in msxorg:
        nm = normalise_model(m)
        m_by_key[natural_key(nm)] = nm

    l_by_key: dict[str, dict[str, Any]] = {}
    for m in local:
        nm = normalise_model(m)
        l_by_key[natural_key(nm)] = nm

    all_keys = sorted(set(o_by_key.keys()) | set(m_by_key.keys()) | set(l_by_key.keys()))
    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for key in all_keys:
        o_model = o_by_key.get(key)
        m_model = m_by_key.get(key)
        l_model = l_by_key.get(key)

        if o_model and not m_model:
            base = o_model
        elif m_model and not o_model:
            base = m_model
        elif o_model is None and m_model is None:
            # Local-only model — no base from scraped sources.
            base = {}
        else:
            # Both sources — merge field by field.
            assert o_model is not None and m_model is not None
            base, model_conflicts = _merge_single(key, o_model, m_model, resolutions.get(key, {}))
            if model_conflicts:
                conflicts.extend(model_conflicts)

        # Apply local overrides on top (local wins for any field it provides).
        if l_model:
            result = dict(base)
            for field, val in l_model.items():
                if val is not None:
                    result[field] = val
            merged.append(_renumber_cs_es(result))
        else:
            merged.append(_renumber_cs_es(base))

    local_only = set(l_by_key.keys()) - set(o_by_key.keys()) - set(m_by_key.keys())
    log.info(
        "Merge: %d total models (%d matched openmsx+msxorg, %d openMSX-only, %d msx.org-only,"
        " %d local-only, %d local overrides), %d unresolved conflicts",
        len(merged),
        len(set(o_by_key.keys()) & set(m_by_key.keys())),
        len(set(o_by_key.keys()) - set(m_by_key.keys())),
        len(set(m_by_key.keys()) - set(o_by_key.keys())),
        len(local_only),
        len(set(l_by_key.keys()) - local_only),
        len(conflicts),
    )
    print_conflict_summary(conflicts)
    return merged


# Fields that are source-specific metadata (not merged as data fields).
_META_FIELDS = {"openmsx_id", "msxorg_title"}


def _renumber_cs_es(model: dict[str, Any]) -> dict[str, Any]:
    """Re-assign sequential CS and ES numbers across all slotmap keys.

    Both scrapers emit provisional numbers (CS1, CS2, ES1, …).  After merge
    the CS/ES type for some slots may have been upgraded (openMSX CS →
    msx.org ES).  This function re-walks the 64 slotmap keys in slot order
    (ms 0→3, ss 0→3) and assigns fresh, independent counters:

    - cs_counter: increments for each CS slot encountered
    - es_counter: increments for each ES slot encountered

    The ``!`` suffix (non-standard subslot placement) is preserved.

    Models that contain no CS or ES values are returned unchanged.
    """
    # Collect (ms, ss) pairs that carry a CS or ES value (type from first page).
    cs_es_slots: dict[tuple[int, int], str] = {}  # (ms,ss) → type+bang e.g. "CS", "ES!"
    for ms in range(4):
        for ss in range(4):
            val = model.get(f"slotmap_{ms}_{ss}_0")
            if val and _is_cs_or_es(val):
                m = _CS_ES_RE.match(val)
                if m:
                    cs_es_slots[(ms, ss)] = m.group(1) + m.group(3)  # e.g. "CS" or "ES!"

    if not cs_es_slots:
        return model

    result = dict(model)
    cs_counter = 0
    es_counter = 0
    for ms in range(4):
        for ss in range(4):
            type_bang = cs_es_slots.get((ms, ss))
            if type_bang is None:
                continue
            kind  = type_bang.rstrip("!")   # "CS" or "ES"
            bang  = "!" if type_bang.endswith("!") else ""
            if kind == "CS":
                cs_counter += 1
                new_abbr = f"CS{cs_counter}{bang}"
            else:
                es_counter += 1
                new_abbr = f"ES{es_counter}{bang}"
            for p in range(4):
                result[f"slotmap_{ms}_{ss}_{p}"] = new_abbr
    return result


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

        # Slot-type conflict (CS/ES/EXP): msx.org always wins.
        # msx.org carries human-curated slot-type information (e.g. a connector
        # that openMSX models as a cartridge slot may be an expansion bus).
        # Numbers are provisional and reassigned by _renumber_cs_es() later.
        if field.startswith("slotmap_") and _is_slot_type(ov) and _is_slot_type(mv):
            result[field] = mv  # msx.org knows the slot type
            continue

        # openMSX emits • for secondary pages it has no device for; it cannot
        # determine the connector type.  If msx.org has a slot-type value for
        # the same cell, prefer msx.org.
        if field.startswith("slotmap_") and ov == "\u2022" and _is_slot_type(mv):
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
        for item in items:
            log.warning(
                "    %s: openMSX=%r vs msx.org=%r [using %s]",
                item["natural_key"], item["openmsx_value"], item["msxorg_value"], item["used"],
            )


# ── Substitutions ────────────────────────────────────────────────────


def load_substitutions(path: Path) -> dict[str, list[dict]]:
    """Load substitutions.json and compile regex patterns.

    Format: {"column_key": [{"match": "<regex>", "replace": <str|null>}, ...]}

    Returns {} if the file does not exist.
    Each rule dict in the returned structure has a compiled "pattern" key
    (re.Pattern) instead of the raw "match" string.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw: dict[str, list[dict]] = json.load(f)
    result: dict[str, list[dict]] = {}
    for column, rules in raw.items():
        compiled = []
        for rule in rules:
            compiled.append({
                "pattern": re.compile(rule["match"]),
                "replace": rule["replace"],
            })
        result[column] = compiled
    return result

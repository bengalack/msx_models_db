"""Build pipeline: merge → derive → assign IDs → write data.js."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from . import merge, msxorg, openmsx
from .columns import (
    COLUMNS, GROUPS, Column,
    active_columns, group_by_key,
)
from .exclude import load_excludes
from .registry import IDRegistry
from .slotmap_lut import compact_lut, load_slotmap_lut

log = logging.getLogger(__name__)

# Default file paths
RAW_OPENMSX = Path("data/openmsx-raw.json")
RAW_MSXORG = Path("data/msxorg-raw.json")
REGISTRY_PATH = Path("data/id-registry.json")
EXCLUDE_PATH = Path("data/exclude.json")
SLOTMAP_LUT_PATH = Path("data/slotmap-lut.json")
DATA_JS_PATH = Path("docs/data.js")


def fetch_sources(
    *,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    delay: float = 0.3,
) -> None:
    """Fetch fresh data from external sources and cache to disk."""
    log.info("Fetching openMSX data…")
    openmsx_models = openmsx.fetch_all(delay=delay)
    _write_json(openmsx_models, openmsx_path)
    log.info("Wrote %d openMSX models to %s", len(openmsx_models), openmsx_path)

    log.info("Fetching msx.org data…")
    msxorg_models = msxorg.fetch_all(delay=delay)
    _write_json(msxorg_models, msxorg_path)
    log.info("Wrote %d msx.org models to %s", len(msxorg_models), msxorg_path)


def build(
    *,
    do_fetch: bool = False,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    registry_path: Path = REGISTRY_PATH,
    exclude_path: Path = EXCLUDE_PATH,
    slotmap_lut_path: Path = SLOTMAP_LUT_PATH,
    output_path: Path = DATA_JS_PATH,
    resolutions_path: Path | None = None,
) -> None:
    """Run the full build pipeline."""
    # Step 0: Load config files (fail fast before any I/O if files are malformed)
    exclude_list = load_excludes(exclude_path)
    slotmap_rules = load_slotmap_lut(slotmap_lut_path)
    slotmap_lut_compact = compact_lut(slotmap_rules)

    # Step 1: Fetch if requested
    if do_fetch:
        fetch_sources(openmsx_path=openmsx_path, msxorg_path=msxorg_path)

    # Step 2: Load cached raw data
    if not openmsx_path.exists():
        raise FileNotFoundError(
            f"Cached openMSX data not found: {openmsx_path}\n"
            "Run with --fetch to download fresh data."
        )
    if not msxorg_path.exists():
        raise FileNotFoundError(
            f"Cached msx.org data not found: {msxorg_path}\n"
            "Run with --fetch to download fresh data."
        )

    with open(openmsx_path, encoding="utf-8") as f:
        openmsx_data = json.load(f)
    with open(msxorg_path, encoding="utf-8") as f:
        msxorg_data = json.load(f)

    log.info("Loaded %d openMSX + %d msx.org models from cache",
             len(openmsx_data), len(msxorg_data))

    # Apply exclude list to cached data (handles the case where data was cached
    # before an exclusion rule was added, or when --fetch is not used)
    if exclude_list.rules:
        before_openmsx = len(openmsx_data)
        before_msxorg = len(msxorg_data)
        openmsx_data = [
            m for m in openmsx_data
            if not exclude_list.is_excluded(m.get("manufacturer"), m.get("model"))
        ]
        msxorg_data = [
            m for m in msxorg_data
            if not exclude_list.is_excluded(m.get("manufacturer"), m.get("model"))
        ]
        excluded_openmsx = before_openmsx - len(openmsx_data)
        excluded_msxorg = before_msxorg - len(msxorg_data)
        if excluded_openmsx or excluded_msxorg:
            log.info(
                "[exclude] Filtered from cache: %d openMSX, %d msx.org",
                excluded_openmsx, excluded_msxorg,
            )

    # Step 3: Merge
    resolutions = {}
    if resolutions_path:
        resolutions = merge.load_resolutions(resolutions_path)

    merged, conflicts = merge.merge_models(openmsx_data, msxorg_data, resolutions=resolutions)
    merge.print_conflict_summary(conflicts)

    # Step 4: Derive computed columns
    derive_cols = [c for c in COLUMNS if c.derive is not None]
    for model in merged:
        for col in derive_cols:
            model[col.key] = col.derive(model)

    # Step 5: Assign model IDs
    registry = IDRegistry.load(registry_path)
    for model in merged:
        nk = merge.natural_key(model)
        model["_id"] = registry.assign_model_id(nk)

    # Step 6: Build data.js payload
    active_cols = active_columns()
    group_id_map = {g.key: g.id for g in GROUPS}

    js_groups = [
        {"id": g.id, "key": g.key, "label": g.label, "order": g.order}
        for g in GROUPS
    ]

    js_columns = []
    for col in active_cols:
        entry: dict[str, Any] = {
            "id": col.id,
            "key": col.key,
            "label": col.label,
            "groupId": group_id_map[col.group],
            "type": col.type,
        }
        if col.short_label:
            entry["shortLabel"] = col.short_label
        if col.tooltip:
            entry["tooltip"] = col.tooltip
        if col.linkable:
            entry["linkable"] = True
        js_columns.append(entry)

    js_models = []
    for model in merged:
        values = []
        for col in active_cols:
            val = model.get(col.key)
            values.append(val)

        record: dict[str, Any] = {
            "id": model["_id"],
            "values": values,
        }

        # Add links for linkable columns
        links: dict[str, str] = {}
        for col in active_cols:
            if col.linkable and col.key == "model":
                msxorg_title = model.get("msxorg_title")
                if msxorg_title:
                    links[col.key] = f"https://www.msx.org/wiki/{msxorg_title.replace(' ', '_')}"
        if links:
            record["links"] = links

        js_models.append(record)

    # Sort models by ID for stable output
    js_models.sort(key=lambda m: m["id"])

    payload = {
        "version": 1,
        "generated": date.today().isoformat(),
        "groups": js_groups,
        "columns": js_columns,
        "models": js_models,
        "slotmap_lut": slotmap_lut_compact,
    }

    # Step 7: Write output
    _write_data_js(payload, output_path)
    registry.save(registry_path)

    log.info(
        "Build complete: %d models, %d columns, %d groups → %s",
        len(js_models), len(js_columns), len(js_groups), output_path,
    )

    # Dead-rule check — warn for any exclude rule that matched nothing
    for i in exclude_list.dead_rules():
        log.warning(
            "[exclude:dead_rule] Rule matched nothing | rule=%d entry=%s",
            i, exclude_list.rules[i],
        )


def _write_json(data: Any, path: Path) -> None:
    """Write JSON with atomic rename."""
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _write_data_js(payload: dict[str, Any], path: Path) -> None:
    """Write docs/data.js in the window.MSX_DATA format."""
    json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    content = f"// MSX Models DB — generated by scraper build\n// Generated: {payload['generated']}\nwindow.MSX_DATA = {json_str};\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

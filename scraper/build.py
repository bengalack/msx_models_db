"""Build pipeline: merge → derive → assign IDs → write data.js."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

from . import local_source, merge, msxorg, openmsx
from .columns import (
    COLUMNS, GROUPS, Column,
    active_columns, group_by_key,
)
from .exclude import load_excludes
from .mirror import FallbackPageSource, MirrorPageSource
from .openmsx_source import FallbackXMLSource, LiveXMLSource, MirrorXMLSource
from .link_shares import apply_link_shares, load_link_shares
from .registry import IDRegistry
from .slotmap import load_sha1_index
from .slotmap_lut import compact_lut, load_slotmap_lut

log = logging.getLogger(__name__)

# Default file paths
RAW_OPENMSX = Path("data/openmsx-raw.json")
RAW_MSXORG = Path("data/msxorg-raw.json")
RAW_LOCAL = Path("data/local-raw.json")
REGISTRY_PATH = Path("data/id-registry.json")
EXCLUDE_PATH = Path("data/exclude.json")
SLOTMAP_LUT_PATH = Path("data/slotmap-lut.json")
SHA1_INDEX_PATH = Path("systemroms/machines/all_sha1s.txt")
SYSTEMROMS_ROOT = Path("systemroms/machines")
DATA_JS_PATH = Path("docs/data.js")
SUBSTITUTIONS_PATH = Path("data/substitutions.json")
SCRAPER_CONFIG_PATH = Path("data/scraper-config.json")


def load_scraper_config(path: Path = SCRAPER_CONFIG_PATH) -> dict:
    """Load scraper-config.json, returning {} if absent or malformed."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        log.exception("Failed to load scraper config: %s — using defaults", path)
        return {}


def fetch_sources(
    *,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    delay: float = 0.3,
    lut_rules: list | None = None,
    sha1_index: dict | None = None,
    systemroms_root: Path | None = None,
    openmsx_mirror_path: Path | None = None,
    local_openmsx_only: bool = False,
    mirror_path: Path | None = None,
    local_only: bool = False,
    exclude_list=None,
) -> None:
    """Fetch fresh data from external sources and cache to disk.

    openMSX source selection (openmsx_mirror_path / local_openmsx_only):
      mirror + local_openmsx_only=True  → MirrorXMLSource (skip GitHub entirely)
      mirror + local_openmsx_only=False → FallbackXMLSource (GitHub first, mirror on failure)
      no mirror                         → LiveXMLSource (GitHub only)

    msx.org source selection (mirror_path / local_only):
      mirror + local_only=True  → MirrorPageSource (skip live entirely)
      mirror + local_only=False → FallbackPageSource (live first, mirror on failure)
      no mirror                 → LivePageSource (live only)
    """
    log.info("Fetching openMSX data…")
    _t0_openmsx = time.perf_counter()
    if openmsx_mirror_path is not None and local_openmsx_only:
        log.info("[mirror:mode] openMSX local-only | path=%s", openmsx_mirror_path)
        openmsx_source = MirrorXMLSource(openmsx_mirror_path)
        openmsx_models = openmsx.fetch_all(source=openmsx_source, delay=0,
                                           lut_rules=lut_rules, sha1_index=sha1_index,
                                           systemroms_root=systemroms_root,
                                           exclude_list=exclude_list)
    elif openmsx_mirror_path is not None:
        log.info("[mirror:mode] openMSX live-with-fallback | path=%s", openmsx_mirror_path)
        import requests as _requests
        _session = _requests.Session()
        _session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        openmsx_source = FallbackXMLSource(LiveXMLSource(_session), MirrorXMLSource(openmsx_mirror_path))
        openmsx_models = openmsx.fetch_all(source=openmsx_source, delay=delay,
                                           lut_rules=lut_rules, sha1_index=sha1_index,
                                           systemroms_root=systemroms_root,
                                           exclude_list=exclude_list)
    else:
        openmsx_models = openmsx.fetch_all(delay=delay, lut_rules=lut_rules,
                                           sha1_index=sha1_index, systemroms_root=systemroms_root,
                                           exclude_list=exclude_list)
    _write_json(openmsx_models, openmsx_path)
    log.info("Wrote %d openMSX models to %s (%.1fs)", len(openmsx_models), openmsx_path,
             time.perf_counter() - _t0_openmsx)

    log.info("Fetching msx.org data…")
    _t0_msxorg = time.perf_counter()
    if mirror_path is not None and local_only:
        log.info("[mirror:mode] msx.org local-only | path=%s", mirror_path)
        msxorg_source = MirrorPageSource(mirror_path)
        msxorg_models = msxorg.fetch_all(source=msxorg_source, delay=0, exclude_list=exclude_list)
    elif mirror_path is not None:
        log.info("[mirror:mode] msx.org live-with-fallback | path=%s", mirror_path)
        import requests as _requests
        session = _requests.Session()
        session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        from .mirror import LivePageSource
        msxorg_source = FallbackPageSource(LivePageSource(session), MirrorPageSource(mirror_path))
        msxorg_models = msxorg.fetch_all(source=msxorg_source, delay=delay, exclude_list=exclude_list)
    else:
        msxorg_models = msxorg.fetch_all(delay=delay, exclude_list=exclude_list)
    _write_json(msxorg_models, msxorg_path)
    log.info("Wrote %d msx.org models to %s (%.1fs)", len(msxorg_models), msxorg_path,
             time.perf_counter() - _t0_msxorg)


def build(
    *,
    do_fetch: bool = False,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    local_path: Path = RAW_LOCAL,
    registry_path: Path = REGISTRY_PATH,
    exclude_path: Path = EXCLUDE_PATH,
    slotmap_lut_path: Path = SLOTMAP_LUT_PATH,
    sha1_index_path: Path = SHA1_INDEX_PATH,
    systemroms_root: Path = SYSTEMROMS_ROOT,
    output_path: Path = DATA_JS_PATH,
    resolutions_path: Path | None = None,
    substitutions_path: Path | None = None,
    openmsx_mirror_path: Path | None = None,
    local_openmsx_only: bool = False,
    mirror_path: Path | None = None,
    local_only: bool = False,
) -> None:
    """Run the full build pipeline."""
    _t_start = time.perf_counter()

    # Step 0: Load config files (fail fast before any I/O if files are malformed)
    exclude_list = load_excludes(exclude_path)
    slotmap_rules = load_slotmap_lut(slotmap_lut_path)
    slotmap_lut_compact = compact_lut(slotmap_rules)

    # Load SHA1 index for mirror detection (gracefully absent)
    sha1_index = load_sha1_index(sha1_index_path if sha1_index_path.exists() else None)
    sr_root = systemroms_root if systemroms_root.exists() else None
    if sha1_index:
        log.info("Loaded SHA1 index: %d entries from %s", len(sha1_index), sha1_index_path)
    else:
        log.info("SHA1 index not found at %s — mirror method 2 disabled", sha1_index_path)

    # Step 1: Fetch if requested
    if do_fetch:
        # Resolve mirror paths: explicit arg > config file
        cfg = load_scraper_config()
        resolved_openmsx_mirror = openmsx_mirror_path
        if resolved_openmsx_mirror is None:
            raw = cfg.get("openmsx_mirror")
            if raw:
                resolved_openmsx_mirror = Path(raw)
        resolved_mirror = mirror_path
        if resolved_mirror is None:
            raw = cfg.get("msxorg_mirror")
            if raw:
                resolved_mirror = Path(raw)
        fetch_sources(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            lut_rules=slotmap_rules,
            sha1_index=sha1_index or None,
            systemroms_root=sr_root,
            openmsx_mirror_path=resolved_openmsx_mirror,
            local_openmsx_only=local_openmsx_only,
            mirror_path=resolved_mirror,
            local_only=local_only,
            exclude_list=exclude_list,
        )

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

    # Backward-compat migration: rename "standard" → "generation" in cached raw data
    # (cached files may predate the rename; fetch regenerates with the correct key).
    for model in openmsx_data:
        if "standard" in model:
            model["generation"] = model.pop("standard")
    for model in msxorg_data:
        if "standard" in model:
            model["generation"] = model.pop("standard")

    # Backward-compat migration: rename "cartridge_slots" → "scraped_cart_slots".
    # Cached raw files written before this rename still use the old key; migrating
    # here ensures the derive step sees the correct field name.
    for model in openmsx_data + msxorg_data:
        if "cartridge_slots" in model and "scraped_cart_slots" not in model:
            model["scraped_cart_slots"] = model.pop("cartridge_slots")

    # Load local supplemental data (optional — absent file is not an error).
    local_data = local_source.load_local(local_path)

    log.info("Loaded %d openMSX + %d msx.org + %d local models from cache",
             len(openmsx_data), len(msxorg_data), len(local_data))

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

    alias_path = Path("data/aliases.json") if Path("data/aliases.json").exists() else None
    merged = merge.merge_models(
        openmsx_data,
        msxorg_data,
        local=local_data,
        resolutions=resolutions,
        alias_path=alias_path,
    )

    # Step 3b: Apply substitutions
    subs_path = substitutions_path if substitutions_path is not None else SUBSTITUTIONS_PATH
    subs = merge.load_substitutions(subs_path)
    if subs:
        merge.apply_substitutions(merged, subs)

    # Step 4: Derive computed columns
    derive_cols = [c for c in COLUMNS if c.derive is not None]
    for model in merged:
        for col in derive_cols:
            # Only derive if no explicit value already present (local overrides take priority).
            if model.get(col.key) is None:
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
        if col.truncate_limit > 0:
            entry["truncateLimit"] = col.truncate_limit
        if col.shaded:
            entry["shaded"] = True
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
            elif col.linkable and col.key == "openmsx_id":
                oid = model.get("openmsx_id")
                if oid:
                    links[col.key] = f"https://github.com/openMSX/openMSX/blob/master/share/machines/{oid}.xml"
        if links:
            record["links"] = links

        js_models.append(record)

    # Apply link-shares: back-fill missing links from a donor model
    link_shares_path = Path("data/link-shares.json")
    if link_shares_path.exists():
        shares = load_link_shares(link_shares_path)
        natural_keys = [merge.natural_key(m) for m in merged]
        apply_link_shares(js_models, natural_keys, shares)

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
        "Build complete: %d models, %d columns, %d groups → %s (total %.1fs)",
        len(js_models), len(js_columns), len(js_groups), output_path,
        time.perf_counter() - _t_start,
    )

    # Dead-rule check — only meaningful after a full fetch.
    # Without --fetch, filename rules are never evaluated (no file listing occurs)
    # and manufacturer+model rules may appear dead because a previous fetch already
    # removed matching models from the cache.
    if do_fetch:
        for i in exclude_list.dead_rules():
            log.warning(
                "[exclude:dead_rule] Rule matched nothing | rule=%d entry=%s",
                i, exclude_list.rules[i],
            )
    else:
        log.debug(
            "[exclude:dead_rule] Skipping dead-rule check (requires --fetch for accurate results)"
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

"""Slot-map display symbols, loaded from data/scraper-config.json.

Defaults are used when the config file is absent or the ``slotmap_symbols``
key is missing; this keeps older config files working unchanged.

Exported names
--------------
ABSENT         : marks a sub-slot that is physically absent (non-expanded SS1-3)
EMPTY_PAGE     : marks a page in a real sub-slot with no device mapped
MIRROR_SUFFIX  : appended to an abbreviation to indicate a mirror page
SUBSLOT_SUFFIX : appended to CS/ES when the slot is inside a sub-slot (non-standard)
"""

from __future__ import annotations

import json
from pathlib import Path

# Config file lives at <project-root>/data/scraper-config.json, and this
# module is at <project-root>/scraper/symbols.py, so go up one level.
_CONFIG_PATH = Path(__file__).parent.parent / "data" / "scraper-config.json"

_DEFAULTS: dict[str, str] = {
    "absent":         "\u2327",  # ⌧  sub-slot physically absent
    "empty_page":     "\u2334",  # ⌴  sub-slot real, no device mapped
    "mirror_suffix":  "*",       # e.g. "DSK*" for a mirrored page
    "subslot_suffix": "!",       # e.g. "CS1!" for a cartridge slot in a subslot
}


def _load() -> dict[str, str]:
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh)
        syms = cfg.get("slotmap_symbols", {})
        return {k: str(syms.get(k, v)) for k, v in _DEFAULTS.items()}
    except Exception:
        return dict(_DEFAULTS)


_syms = _load()

ABSENT:         str = _syms["absent"]
EMPTY_PAGE:     str = _syms["empty_page"]
MIRROR_SUFFIX:  str = _syms["mirror_suffix"]
SUBSLOT_SUFFIX: str = _syms["subslot_suffix"]

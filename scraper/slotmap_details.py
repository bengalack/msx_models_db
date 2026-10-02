"""Per-cell details of the slot map tooltips ("Firmware: Painter ROM", "Disk ROM: WD2793").

The slot map LUT (data/slotmap-lut.json) gives one tooltip per label — "FW" is
"Firmware" in every cell, shipped once in ``MSXData.slotmap_lut``. A rule's
``"detail"`` asks for more, shipped sparsely per model in
``ModelRecord.slot_details`` and joined by the page as "<tooltip>: <detail>":

- ``"text"``    the msx.org slot map's own text for the cell. The msx.org parser
                keeps every device cell's ``[label, text]`` (``SLOT_TEXT_FIELD``);
                msx.org text is classified without the LUT, so the flag applies
                to every cell with the rule's label.
- ``"element"`` the openMSX device element behind the cell ("WD2793"). The
                openMSX parser keeps every device cell's ``[tag, id]``
                (``SLOT_DEVICES_FIELD``); the device is matched against the LUT
                again, so the flag applies to the cells *that rule* classified.

A cell gets a detail only when its final (merged) label is the one the source
gave it — a cell another source filled with another device never borrows the
text — and the detail says more than the tooltip ("Disk ROM" for "Disk ROM"
does not). An "element" detail wins over a "text" one.

Design: technical-design.md, *Feature Design: Slot Map Tooltip Details*.
"""
from __future__ import annotations

import re
from typing import Any

from .slotmap import match_rule

SLOT_TEXT_FIELD = "_slot_text"
SLOT_DEVICES_FIELD = "_slot_devices"
_FOOTNOTE_RE = re.compile(r"\s*\*+$")


def _squash(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def text_detail_labels(rules: list[dict]) -> set[str]:
    """Labels whose LUT rule asks for the msx.org text as the tooltip detail."""
    return {r["abbr"] for r in rules if r.get("detail") == "text" and r.get("abbr")}


def _informative(detail: str | None, tooltip: str | None) -> str | None:
    detail = _FOOTNOTE_RE.sub("", detail or "")      # "Network*": a footnote mark, not a name
    return detail if detail and _squash(detail) != _squash(tooltip) else None


def slot_details(model: dict[str, Any], rules: list[dict], tooltips: dict[str, str]) -> dict[str, str]:
    """``{cell key: detail}`` for one merged model (empty when nothing applies)."""
    out: dict[str, str] = {}
    for key, (tag, element_id) in (model.get(SLOT_DEVICES_FIELD) or {}).items():
        rule = match_rule(tag, element_id, rules)
        if rule is None or rule.get("detail") != "element" or model.get(key) != rule["abbr"]:
            continue
        if detail := _informative(tag, tooltips.get(rule["abbr"])):
            out[key] = detail
    labels = text_detail_labels(rules)
    for key, (label, text) in (model.get(SLOT_TEXT_FIELD) or {}).items():
        if key in out or label not in labels or model.get(key) != label:
            continue
        if detail := _informative(text, tooltips.get(label)):
            out[key] = detail
    return out

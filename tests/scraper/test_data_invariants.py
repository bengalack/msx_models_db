"""Invariants of the built data (docs/data.js, read only).

These hold for every real MSX, so a violation is a scraper bug, not a data
quirk. The expected values are derived from the configuration, never
hardcoded.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.slotmap import match_lut
from scraper.slotmap_lut import load_slotmap_lut

DATA_JS = Path("docs/data.js")
SLOTMAP_LUT = Path("data/slotmap-lut.json")


def _models() -> list[dict]:
    text = DATA_JS.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    keys = [c["key"] for c in data["columns"]]
    return [dict(zip(keys, m["values"])) for m in data["models"]]


def _main_rom_labels() -> set[str]:
    """The Main ROM label and its variants ("MAIN+": Frael's switchable BIOS/firmware ROM)."""
    rules = load_slotmap_lut(SLOTMAP_LUT)
    main = match_lut("ROM", "MSX BIOS with BASIC ROM", rules)
    assert main, "the slot map LUT classifies the standard main ROM"
    return {r["abbr"] for r in rules if str(r.get("abbr", "")).startswith(main)}


def _has_slotmap(model: dict) -> bool:
    return any(value for key, value in model.items() if key.startswith("slotmap_"))


@pytest.mark.skipif(not DATA_JS.exists(), reason="docs/data.js not built")
def test_main_rom_in_slot_0_pages_0_and_1():
    """Slot 0 (or 0-0 when expanded) always holds the Main ROM in pages 0 and 1."""
    main_labels = _main_rom_labels()
    violations = [
        (m["manufacturer"], m["model"], m["slotmap_0_0_0"], m["slotmap_0_0_1"])
        for m in _models()
        if _has_slotmap(m) and not {m["slotmap_0_0_0"], m["slotmap_0_0_1"]} <= main_labels
    ]
    assert not violations, f"slot 0-0 pages 0-1 must be one of {sorted(main_labels)}: {violations}"

"""Filling a model's missing fields from a donor model's row.

Shared by adaptations ("X is the adaptation of Y", scraper/msxorg.py) and
link-shares (data/link-shares.json, scraper/link_shares.py): in both cases the
donor's row describes the same hardware, so every field the model lacks is
copied — except the model's identity and facts about the donor's specific
machine.

Design: .claude/artifacts/planning/2026-09-26-adaptations-design.md
"""

from __future__ import annotations

from typing import Any

# Never copied: identity, the donor's emulator machine (openmsx_id would claim —
# and link to — a machine this model is not), and the character set / keyboard
# type read from the donor's BIOS ROM, which a localised model replaced.
# Internal fields (leading underscore) are never copied either.
NEVER_INHERITED = frozenset({
    "manufacturer", "model", "generation", "msxorg_title",
    "openmsx_id", "character_set", "keyboard_type",
    "mapper",  # derived from the slot map, so it travels with it
})


def fill_blanks(record: dict[str, Any], donor: dict[str, Any]) -> bool:
    """Copy every field *record* lacks from *donor* (in place). True if anything changed.

    The slot map (all ``slotmap_*`` cells) and its Memory Mapper are copied as
    a unit, and only when *record* has no slot map of its own.
    """
    changed = False
    for key, value in donor.items():
        if key in NEVER_INHERITED or key.startswith(("_", "slotmap_")) or value is None:
            continue
        if record.get(key) is None:
            record[key] = value
            changed = True
    donor_slots = {k: v for k, v in donor.items() if k.startswith("slotmap_")}
    if donor_slots and not any(k.startswith("slotmap_") for k in record):
        record.update(donor_slots)
        if donor.get("mapper") is not None:
            record["mapper"] = donor["mapper"]
        changed = True
    return changed

"""Filling a model's missing fields from a donor model's row.

Shared by adaptations ("X is the adaptation of Y", scraper/msxorg.py) and
link-shares (data/link-shares.json, scraper/link_shares.py): in both cases the
donor's row describes the same hardware, so every field the model lacks is
copied — except the model's identity and facts about the donor's specific
machine. A *version* of a model ("NMS 8220/16") takes its main model's row
except what its page states for the version (``inherit_from_main``).

Design: .claude/artifacts/planning/2026-09-26-adaptations-design.md
"""

from __future__ import annotations

from typing import Any

# Never copied: identity, the donor's emulator machine (openmsx_id would claim —
# and link to — a machine this model is not), and the character set / keyboard
# type read from the donor's BIOS ROM, which a localised model replaced.
# Internal fields (leading underscore) are never copied either.
NEVER_INHERITED = frozenset({
    "brand", "model", "generation", "msxorg_title",
    "openmsx_id", "character_set", "keyboard_type",
    "mapper",  # derived from the slot map, so it travels with it
})


# A version also keeps out the HIMEM value: measured by booting the main model's
# BIOS, which a localised version replaced.
VERSION_NEVER_INHERITED = NEVER_INHERITED | {"himem_addr"}


def inherit_from_main(record: dict[str, Any], main: dict[str, Any], own: set[str]) -> bool:
    """Make a version (*record*) its main model's row, except the fields in *own* (in place).

    *own* are the fields the page states for the version (region, keyboard, a
    table row's RAM). Every other field the main model has — openMSX's data
    included — replaces the version's, which only repeated the page's general
    values. The slot map goes as a unit, unless the version has its own.
    """
    own_slots = any(k.startswith("slotmap_") for k in own)
    changed = False
    for key, value in main.items():
        if key in VERSION_NEVER_INHERITED or key.startswith("_") or key in own or value is None:
            continue
        if own_slots and (key.startswith("slotmap_") or key == "mapper"):
            continue
        if record.get(key) != value:
            record[key] = value
            changed = True
    return changed


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

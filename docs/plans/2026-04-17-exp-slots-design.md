# Design: Expansion Slots Column + Slotmap-Derived Cart Slots

**Date:** 2026-04-17
**Author:** bengalack

## Problem

The Media column group shows "Cart Slots" but not "Exp Slots". Users cannot see how many
expansion slots a model has. Additionally, the current `cartridge_slots` value is scraped
independently by both parsers using heuristics (page text, XML element counts), making it
inconsistent with the final merged slotmap — the authoritative source of slot layout.

## Solution

Derive both `cartridge_slots` and new `expansion_slots` from the **final merged slotmap**
(post-renumber). Use the existing scraped cartridge count as a fallback for models that
have no slotmap table at all.

## Design

### Counting rule

Walk the 64 slotmap keys (`slotmap_{ms}_{ss}_0` for ms=0–3, ss=0–3). For each `(ms, ss)`,
page 0 holds the representative abbreviation for that sub-slot. Count distinct sub-slots
whose page-0 value matches `^CS\d+!?$` (cartridge) or `^ES\d+!?$` (expansion). The `!`
suffix (non-standard sub-slot placement) is still a real slot and is counted. Return the
integer count, or `None` if zero (consistent with nullable fields elsewhere).

### Fallback for cartridge slots

Models that have msx.org page text listing a slot count but no HTML slot map table will
have no CS* entries in the slotmap. For these, the existing scraped count is preserved
under a hidden key `scraped_cart_slots` and used as fallback.

There is no equivalent fallback for expansion slots — no existing scraped source.

### Changes by file

| File | Change |
|------|--------|
| `scraper/openmsx.py` | Rename `out["cartridge_slots"]` → `out["scraped_cart_slots"]` |
| `scraper/msxorg.py` | Rename `result["cartridge_slots"]` → `result["scraped_cart_slots"]` (all occurrences) |
| `scraper/columns.py` | Add hidden column `scraped_cart_slots`; add `derive` to `cartridge_slots` (id=19); add new column `expansion_slots` (id=101); add shared helper `_count_slotmap(model, kind)` |
| `scraper/merge.py` | Replace `"cartridge_slots"` with `"scraped_cart_slots"` in `_PREFER_OPENMSX` |
| `scraper/build.py` | No changes |

### New column

| Field | Value |
|-------|-------|
| id | 101 |
| key | `expansion_slots` |
| label | Expansion Slots |
| short_label | Exp Slots |
| group | media |
| type | number |
| tooltip | Expansion Slots |
| derive | `_count_slotmap(m, "ES") or None` |

### Derive functions (pseudocode)

```python
_SLOTMAP_SLOT_RE = re.compile(r"^(CS|ES)\d+!?$")

def _count_slotmap(model, kind):
    count = 0
    for ms in range(4):
        for ss in range(4):
            v = model.get(f"slotmap_{ms}_{ss}_0") or ""
            if _SLOTMAP_SLOT_RE.match(v) and v.startswith(kind):
                count += 1
    return count or None
```

`cartridge_slots` derive: `lambda m: _count_slotmap(m, "CS") or m.get("scraped_cart_slots")`
`expansion_slots` derive:  `lambda m: _count_slotmap(m, "ES")`

### Precedence

1. `local-raw.json` explicit value (build.py guard: skip derive if value already set)
2. Slotmap-derived count (primary)
3. `scraped_cart_slots` fallback (cartridge only)
4. `None`

## Testing

- Unit tests in `tests/scraper/test_columns.py` (or new `test_exp_slots.py`):
  - `_count_slotmap` with CS-only, ES-only, mixed, and empty slotmap
  - `!`-suffixed slots counted correctly
  - Fallback: no slotmap → scraped_cart_slots returned
  - local-raw.json override: explicit value preserved
- Existing `test_openmsx.py` / `test_msxorg.py`: update assertions that reference `cartridge_slots` → `scraped_cart_slots`
- `test_merge.py`: update `_PREFER_OPENMSX` references if tested directly

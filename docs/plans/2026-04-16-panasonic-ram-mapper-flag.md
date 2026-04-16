---
date: 2026-04-16
topic: PanasonicRAM implies memory mapper
status: approved
---

# Design: PanasonicRAM implies Memory Mapper

## Problem

Machines using `<PanasonicRAM>` (e.g. Panasonic FS-A1GT turboR) show `null` in the
Memory Mapper column. PanasonicRAM is a proprietary implementation of the standard MSX
memory mapper interface, so these machines do in fact have a mapper.

## Rule

In `_extract_memory` (`scraper/openmsx.py`): if one or more `<PanasonicRAM>` elements
are present and `mapper` has not already been set by a `<MemoryMapper>` element, set
`mapper = "Yes"`.

Priority order (first match wins, later steps skip if already set):
1. `<MemoryMapper>` found → `mapper = "Yes"` (or comma-separated ids for multiple)
2. `<PanasonicRAM>` found → `mapper = "Yes"`
3. `<RAM>` only (no mapper) → `mapper = "No"`
4. No RAM at all → `mapper` key absent

## Tech design update

Add to the memory extraction section of `technical-design.md`:

> `<PanasonicRAM>` present → `mapper = "Yes"` (proprietary implementation of the
> standard MSX memory mapper interface)

## Tests

| Test | Action |
|---|---|
| `test_panasonic_ram` | Add `assert result["mapper"] == "Yes"` |
| `test_panasonic_ram_with_memory_mapper` | New — both `<PanasonicRAM>` and `<MemoryMapper>` present; assert `mapper == "Yes"` (not duplicated) |

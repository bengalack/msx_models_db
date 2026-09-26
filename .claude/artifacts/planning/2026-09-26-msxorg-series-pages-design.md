# Design: msx.org series pages — per-variant data for model families

## Metadata
- Date: 2026-09-26
- Status: Implemented (`scraper/msxorg_series.py`)
- Related: technical-design.md (Scraper CLI, msx.org Page Source, Slot map cell semantics)

## Problem

msx.org moved the technical details of several model families to a shared **series page**, a wiki category such as `Category:Sony_HB-75`. The individual model pages (`Sony HB-75`, `Sony HB-75P`, …) keep their description but no longer carry a specs table; they say *"see HB-75 series for the technical details"*. The scraper read only the model page, found no specs table and skipped it, so those models got no msx.org data at all: no msx.org link, engine, VDP, Memory Mapper or slot map.

Scope in the current mirror (2026-09-26): 13 series pages with a specs table, 49 member pages.

| Series | Members |
|---|---|
| Sony HB-10, HB-101, HB-20, HB-201, HB-501, HB-55, HB-75 | 20 |
| Sony HB-F500, HB-F700 | 8 |
| Toshiba HX-10, HX-20, HX-21, HX-22 | 21 |

`Category:Sony_HB-F9` and `Category:Sony_HB-G900` are plain groupings without a specs table; their members still have their own specs and are unaffected.

## What a series page looks like

One specs table for the whole family, where a value either applies to every variant or names the variants it applies to:

| Form | Example |
|---|---|
| Shared | `64kB in slot 2` |
| Label-colon | `HB-10: Japan HB-10B: United Kingdom HB-10D: Germany` |
| Leading label | `(HB-101) QWERTY/JP50on - (HB-101P) QWERTY with a "£" key` |
| Trailing qualifier | `16kB in slot 0 (HB-10) or 64kB in slot 3 (other models)` |
| "in" qualifier | `Gate array Toshiba TCX-1010 in HX-21, TCX-1012 in HX-21F` |
| Region-qualified | `1984-10-16 in Japan - 1985 in Spain - 1986 in Argentina` |
| Deferred | `See table above` → a per-variant table (Product \| Region \| Keyboard \| …) |

Several slot maps, told apart by their headings: *for HB-75 model* / *for other models*, *for 16kB model* / *for 64kB models*, *on HX-22I (also probably HX-22CH and HX-22GB)*.

## Approach

A member page with no specs table that links to a series ("… series" link to a `Category:` page) is parsed from that series page, **for its own variant**. Everything downstream — field parsers, engine, Memory Mapper, slot map parser, merge — is unchanged: the series logic only builds a per-variant specs dict and picks the slot map table, then the existing model-page code runs on them.

### Identity
- Manufacturer: the series `Brand` field.
- Model: the member page title without the brand prefix (`Sony HB-75P` → `HB-75P`).
- `msxorg_title`: the member page, so the grid links to the model's own page.
- Variant vocabulary (for matching names in text): series members ∪ names in the `Model` field ∪ `Product` column of the variant table. Names match as whole tokens, longest first, so `HX-10S` never matches inside `HX-10SA`.

### Resolving a field for a variant (first match wins)
1. **Shared**: the value names no variant and says no "other models" → used as is.
2. **Label-colon**: two or more `CODE:` labels (any model-code-shaped label, so a typo like `HB-22I:` still ends the previous segment) → the text after this variant's label. Variant not labelled → unresolved.
3. **Leading label**: the value starts with `(variants)` groups → the text after this variant's group.
4. **"in" qualifier**: `X in V1, Y in V2` → the `X` of the segment naming this variant.
5. **Trailing qualifier**: each `(…)` group naming variants or "other models/versions" closes a segment → the segment naming this variant, else the "other models" segment.
6. **Region-qualified** (Year only): segments qualified by a region (`… in Japan`, `… (France)`) → the segment matching the variant's resolved region; a European country also matches a segment qualified "Europe".
7. **Deferred** (`see table above`): the matching column of the variant's row in the per-variant table (Region, Keyboard).
8. Otherwise **unresolved**: the field is left unset and logged `[msxorg:series] Unresolved` — never the whole family text, which would put one variant's value on another.

Region codes from the variant table are expanded (`JP` → Japan, `UK` → United Kingdom, `DE` → Germany, …); unknown codes are kept.

### Region
The variant table's Region wins when the table has one (it is per variant by definition); the specs Region is often a family-wide list (`Argentina, Italy, Japan, Spain`) and is only used when the table has no Region column — or, when it has one, only for a value that names variants. A variant missing from a page that lists per-variant regions gets no region rather than the family-wide list (HX-10P: unset, so openMSX's `uk` stays).

### Choosing the slot map (first match wins)
1. A heading naming the variant (`Slot Map for HB-75 model`, `… on HX-22I (also probably HX-22CH and HX-22GB)`).
2. A heading naming the variant's RAM size (`for 16kB model` when the variant's resolved RAM says 16kB).
3. A heading saying "other models/versions".
4. The first slot map (existing rule, including the "Checked on a real machine" preference).

Memory Mapper is derived from the same chosen table, so the two stay consistent.

### Loading the series page
`fetch_all` hands `parse_model_page` a loader that fetches `Category:<Series>` through the same `PageSource` (live, mirror or fallback) and caches it per run. Mirror file name follows the existing convention: `Category_Sony HB-75 - MSX Wiki.html`.

## Known gaps (from the prototype run over all 49 pages)

| Page | Field | Why | Result |
|---|---|---|---|
| Toshiba HX-10I | Video | not listed in the VDP sentence | unset (merge fills from openMSX if present) |
| Toshiba HX-22CH, HX-22GB | RAM | only HX-22 and HX-22I are named | unset |
| Toshiba HX-22CH, HX-22I | Region | not labelled (the page says `HB-22I` for HX-22I) | unset |
| Toshiba HX-10P, HX-10 Japanese models | Keyboard | "(Japanese models) QWERTY/JIS", and the Japanese variant table has no keyboard column | unset |

| Toshiba HX-20I | Year | Italy is not named in the year text | unset |
| Toshiba HX-10 Japanese models | Region | in a variant table without a Region column | the family-wide `Europe, Japan` |

Each can be corrected per model in `data/local-raw.json`, or fixed on the wiki.

## Result (2026-09-26 mirror)

- All 49 member pages parse from their series; every one now carries its msx.org link.
- 26 variants that openMSX does not have appear as new models (ids 419–444).
- 23 existing models gain msx.org data (engine, keyboard, VRAM, region, …); openMSX still wins conflicts.
- `data/slotmap-lut.json`: `DataBank` (msx.org's name for Sony's Personal Databank firmware) added to the FW rule.

## Testing
- Unit: each resolution form, the unresolved path, whole-token matching, region codes, slot map choice, series link detection; fixtures are inline HTML/text owned by the tests.
- Integration: a member page plus its series page through `parse_model_page`, including slot map and Memory Mapper from the chosen table.
- Regression: the model-page path (pages with their own specs) is unchanged.

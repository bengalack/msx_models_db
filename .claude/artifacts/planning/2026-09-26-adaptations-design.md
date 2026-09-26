# Design: adaptations — fill a model's blanks from the model it was adapted from

## Metadata
- Date: 2026-09-26
- Status: Implemented (`scraper/msxorg.py`: `adapted_from`, `fill_from_donors`; called in `scraper/build.py` after the merge)
- Related: 2026-09-26-msxorg-series-pages-design.md, 2026-09-26-model-revisions-design.md

## Problem

Many msx.org model pages describe a localised version of another model: "The Fenner FPC-900 is the adaptation of the Sanyo MPC-25FD computer, also known as Wavy 25, for the Italian market." Their own specs are often thin — Fenner FPC-900, Fenner DPC-200, CE-TEC MPC-80, Network DPC-200, Olympia DPC-200 and Yeno MX64 have no slot map — while the donor's page (possibly a series member, possibly itself an adaptation) has the details.

## Approach

### 1. Recognise the donor (per page)

A sentence in the page body whose subject is the page's own model and that says it *is* an adaptation of another model:

- "The [brand] <model> [computer] is (the | an | one of the [two]) [planned] adaptation(s) … of (the) [Japanese | original] **X**"
- "This [brand] <model> / This computer / It's / It is (the | an) adaptation … of **X**"
- "The <model> is the **X** adapted for …"

The donor is the first wiki link to a model page after "of" (or before "adapted for"). Not donors:
- the reverse direction — "This computer has been adapted for the Spanish market - see ML-G1" (the page is the *donor*);
- links to a series category (`Category:…`) or non-model pages;
- sentences mentioning a **prototype** ("the adaptation of the special MSX2 prototype version for the MPC-2 MSX1 computer" — the linked MPC-2 is not what was adapted).

A revision reference between "of" and the link picks that revision of the donor: "the adaptation … of the **second version** of the HB-55" → donor `HB-55 (v2)` (see revisions design); "the **first version** of HB-F500" → the base record.

Recorded on the msx.org record as `_adapted_from = {"title": <donor page title>, "revision": N}` (internal).

### 2. Fill the blanks (in the build, after the merge)

`fill_from_donors` runs in `scraper/build.py` between the merge and the derived columns, on the **final merged rows** — so an adaptation gets exactly what the grid shows for its donor (openMSX data included; e.g. Fenner FPC-900's slot map is identical to Sanyo MPC-25FD's row), and derived columns (Cart Slots, Memory Mapper, Engine) follow the filled data. The msx.org cache only records `_adapted_from`.

- The donor row is the merged row whose `msxorg_title` is the donor page (base, or revision *N*, falling back to the base).
- **Nesting**: the donor's own blanks are filled from *its* donor first (recursive, cycle-safe, depth-limited).
- **Every field the adaptation lacks is filled**, except:
  - identity: `manufacturer`, `model`, `generation`, `msxorg_title`;
  - `openmsx_id` — the donor's emulator machine; copying it would claim (and link to) a machine the adaptation is not;
  - `character_set`, `keyboard_type` — read from the donor's BIOS ROM, which the adaptation replaced with a localised one (30 adaptations would otherwise show e.g. `Japanese` on the UK Sony HB-75B, `French (AZERTY)` on the UK Network DPC-200).
- The **slot map** (all 64 cells) and the Memory Mapper derived from it are copied as a unit, and only when the adaptation has no slot map of its own.

Values the adaptation states itself are never overwritten; local-raw overrides still win.

## Result (2026-09-26 data)

- 67 adaptation links recognised; 34 rows gain data (10 full slot maps, HIMEM on 32, CPU/RTC/Z80-turbo on 30, RAM, year, VDP, Memory Mapper).
- The six reported examples (Fenner FPC-900, Fenner DPC-200, CE-TEC MPC-80, Network DPC-200, Olympia DPC-200, Yeno MX64) all gain a slot map.

## Testing
- Donor recognition: forward phrasings, reverse phrasing ignored, prototype ignored, category link ignored, revision of the donor.
- Filling: every missing field filled, own values kept, identity / emulator / BIOS fields never copied, slot map copied as a unit only when absent, nesting through two levels, cycle safety, missing donor page, and end to end: filled from the donor's merged row.

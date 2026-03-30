# Problem Description: Slot Map Columns

## Metadata
- Date: 2026-03-29
- Owner: bengalack
- Project Meta: .claude/artifacts/project/project-meta.md
- Parent Problem: .claude/artifacts/planning/problem-description.md

## Summary
- MSX models expose a slot map: up to 4 main slots, each optionally expanded into up to 4 sub-slots, each with 4 memory pages.
- The slot map describes what hardware device (ROM, RAM, cartridge slot, etc.) occupies each page of each sub-slot.
- This data must be scraped from two sources: openMSX XML (`<primary>`/`<secondary>` under `<msxconfig><devices>`) and msx.org wiki (visual "Slot Map" table).
- Raw device strings from both sources are normalised to ~20 short abbreviations (e.g. `MAIN`, `CS1`) each carrying a human-readable tooltip.
- A maintainer-controlled LUT JSON file maps regex patterns (matched case-insensitively against scraped strings) to `{ abbr, tooltip }` pairs; this is the single source of truth for the vocabulary.
- The LUT is used in two modes: (1) regex-based at scrape/build time to resolve abbreviations into `data.js`; (2) fast key-based at runtime in the webpage to resolve tooltips from abbreviations without repeating tooltip strings in every cell.
- Mirror entries (a sub-slot that is a live copy of another) are represented by appending `*` to the origin abbreviation (e.g. `MAIN*`).
- 64 new columns are added across 4 new column groups ("Slotmap, slot 0–3"), each group having 16 fixed columns (4 sub-slots × 4 pages).
- All models carry all 64 columns; cells that fall outside a model's physical slots receive the special value `~` ("Not expanded").
- openMSX XML is the default winning source; maintainers can override per-cell using the existing conflict resolution system.

## Problem
The existing MSX Models DB captures hardware specs (CPU, RAM, video, audio, etc.) but omits the slot map — the fundamental memory-layout descriptor that defines how ROM, RAM, cartridge slots, and expansion hardware are wired into the Z80 address space. This information exists in both openMSX XML files and msx.org wiki pages but requires non-trivial parsing from each source. Without it, users cannot compare or reference memory layout across models in the grid.

## Desired Outcomes
- Each model row in the grid shows 64 slot-map cells across 4 collapsible column groups.
- Cells contain short abbreviations; hovering reveals a descriptive tooltip.
- Cells outside a model's physical slot layout display `~` (visually distinct, non-content).
- Slot map data is populated by the scraper from openMSX XML and/or msx.org wiki, merged and conflict-resolved with the existing pipeline.
- Maintainer can resolve slot map conflicts using the same mechanism as other fields.

## Stakeholders
- MSX enthusiasts / collectors
  - Type: Customer
  - Goals: Understand and compare memory layouts across MSX models at a glance
  - Responsibilities: End users of the web page
- bengalack (maintainer)
  - Type: Internal
  - Goals: Keep slot map data accurate; resolve conflicts; run scraper as needed
  - Responsibilities: Maintain abbreviation-to-tooltip map; run scraper; resolve conflicts

## Current Workflows
- Slot map lookup (manual, today)
  - Trigger: User wants to know the memory layout of a specific MSX model
  - Steps:
    1. Open openMSX XML for the model and locate `<msxconfig><devices><primary>`/`<secondary>` elements
    2. Or navigate to the model's msx.org wiki page and find the "Slot Map" visual table
    3. Manually interpret the layout
  - Success End State: User understands what occupies each slot/page
  - Failure States:
    - XML device names are not human-readable without domain knowledge
    - msx.org page is missing or structured inconsistently
    - Sources disagree on the layout

- Data maintenance workflow (extended)
  - Trigger: Maintainer runs scraper to refresh data
  - Steps:
    1. Scraper parses openMSX XML: walks `<primary>` and `<secondary>` nodes under `<msxconfig><devices>`, maps device names to abbreviations
    2. Scraper parses msx.org wiki: locates "Slot Map" section, parses the visual table, maps cell text to abbreviations
    3. Merge step combines both sources; openMSX XML wins by default
    4. Conflicts written to conflict record; maintainer resolves as needed
    5. Output written to JSON; page re-deployed
  - Success End State: All 64 slot-map columns populated (or `~`) for every model
  - Failure States:
    - XML device element structure differs from expected schema
    - msx.org slot map table uses unexpected HTML structure
    - A device string has no matching abbreviation (unmapped value)

## In Scope
- 64 new columns across 4 new column groups (16 columns each):
  - "Slotmap, slot 0": `0-0/0` … `0-3/3`
  - "Slotmap, slot 1": `1-0/0` … `1-3/3`
  - "Slotmap, slot 2": `2-0/0` … `2-3/3`
  - "Slotmap, slot 3": `3-0/0` … `3-3/3`
- Column naming convention: `MS-SS/P` (Main Slot – Sub Slot / Page), pages 0–3 map to address ranges 0x0000–0x3FFF, 0x4000–0x7FFF, 0x8000–0xBFFF, 0xC000–0xFFFF
- A maintainer-controlled LUT JSON file (`data/slotmap-lut.json` or similar) mapping regex patterns to `{ abbr, tooltip }` pairs (~20 entries to start; grows as new device strings are encountered)
- `~` sentinel value for cells outside a model's physical slot configuration (tooltip: "Not expanded")
- Mirror convention: `*` appended to the origin abbreviation (e.g. `MAIN*`) — no separate LUT entry needed, derived at scrape time
- Scraper support for openMSX XML slot map extraction
- Scraper support for msx.org wiki "Slot Map" table extraction
- Integration with existing merge and conflict system (openMSX wins by default; maintainer override supported)
- All models carry all 64 columns (uniform schema, no per-model column variation)
- Webpage uses the LUT in fast key-lookup mode: tooltip strings stored once in the LUT, referenced by abbreviation (`LUT['MAIN'].tt`) rather than repeated per cell in `data.js`

## Out of Scope
- MSX1 slot maps (consistent with the parent project deferral)
- Dynamic column count per model (schema is fixed at 64 columns)
- Sub-slot expansion detection changing the column structure (expansion only affects whether sub-slot 1–3 cells are `~` or populated)
- Automatic conflict resolution beyond the existing system

## Constraints
- Schema must remain flat JSON compatible with the existing data file format
  - Source: Operational
  - Notes: 64 new keys per model record; no nested objects for slot cells
- Abbreviation vocabulary must be defined before scraper output can be validated
  - Source: Operational
  - Notes: Unmapped device strings should be flagged, not silently dropped
- openMSX XML is the authoritative source by default
  - Source: Policy
  - Notes: Consistent with existing merge priority rules

## Risks
- openMSX XML device element structure varies across machine configs
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: Audit a sample of XML files before designing the parser; document assumed structure
- msx.org "Slot Map" section HTML structure is inconsistent across model pages
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: Survey a sample of pages; design parser to log failures gracefully
- Device strings from either source have no matching abbreviation
  - Likelihood: Medium
  - Impact: Low
  - Mitigation: Scraper emits unmapped-value warnings; maintainer extends abbreviation config as needed
- 64 extra columns make the grid very wide, degrading usability
  - Likelihood: High
  - Impact: Low
  - Mitigation: All 4 slot-map groups are collapsible; default view can start them collapsed

## Unknowns
- Exact structure of `<primary>` / `<secondary>` elements across all target openMSX XML files
  - Why it matters: Determines parser complexity and edge-case handling
  - Suggested question: Inspect a representative sample of openMSX machine XMLs (MSX2, MSX2+, turboR) to document the device element pattern
- Full set of device strings that will be encountered across all models
  - Why it matters: Required to finalise the LUT regex patterns before the scraper can be validated
  - Suggested question: Do a dry-run parse of all target XML files and collect the unique device name strings; use results to extend the starter LUT
- Whether numbered cartridge slot entries (CS1, CS2, …) should be auto-generated from a single parameterised pattern or listed individually in the LUT
  - Why it matters: Determines LUT schema design (static entries vs. parameterised/template entries)
  - Suggested question: Confirm whether `CS(N)` is a template producing CS1, CS2, … or whether each is a separate LUT row
- Whether msx.org "Slot Map" tables use a consistent HTML structure
  - Why it matters: Determines whether a single parser covers all pages or per-page special cases are needed
  - Suggested question: Manually inspect 5–10 model pages to assess HTML consistency

## Simplification Opportunities
- Define the abbreviation vocabulary manually before writing the scraper
  - Why it helps: Decouples vocabulary design from parsing implementation; avoids mid-build rework
- Build the XML parser first; add the msx.org parser only if XML coverage is insufficient
  - Why it helps: openMSX XML is structured and machine-readable; msx.org HTML is fragile — defer the harder source until the value is confirmed

## Starter LUT Vocabulary

Classification is by **XML element type** and **`id` attribute** (matched case-insensitively), not flat string regex. The LUT is used in two modes: regex-based at scrape/build time; fast key-lookup at runtime (`LUT['MAIN'].tt`).

| XML element | `id` pattern (regex, case-insensitive) | Abbr | Tooltip |
|---|---|---|---|
| `<primary external="true" slot="N">` | — | `CS{N}` | Cartridge slot {N} _(N from slot attribute)_ |
| `<secondary external="true">` | — | `EXP` | Expansion Bus |
| `ROM` | `MSX BIOS with BASIC ROM\|Main ROM` | `MAIN` | MSX BIOS with BASIC ROM |
| `ROM` | `Sub.ROM` | `SUB` | Sub ROM |
| `ROM` | `Kanji` | `KNJ` | Kanji driver |
| `ROM` | `MSX-JE` | `JE` | MSX-JE |
| `ROM` | `Firmware\|Arabic ROM\|SWP ROM\|.*Cockpit.*\|Desk Pac.*` | `FW` | Firmware |
| `WD2793` or `TC8566AF` | _(any)_ | `DSK` | Disk ROM |
| `MSX-MUSIC` or `FMPAC` | _(any)_ | `MUS` | MSX Music |
| `MSX-RS232` | _(any)_ | `RS2` | RS-232C Interface |
| `MemoryMapper` | _(any)_ | `MM` | Memory Mapper |
| `PanasonicRAM` | _(any)_ | `PM` | Panasonic Mapper |
| `RAM` | _(any)_ | `RAM` | RAM (no memory mapper) |
| _(sentinel)_ | — | `~` | Not expanded |
| _(mirror suffix)_ | — | `<origin>*` | _(derived at scrape time — no LUT entry needed)_ |

> **Notes:**
>
> - `CS{N}` is parameterised: slot number is read from the `slot="N"` attribute directly — one rule, not N individual entries.
> - `mappertype=PANASONIC` inside a `ROM` element is a property of Firmware ROMs; these match the `FW` rule via their `id` — no separate LUT entry.
> - Mirrors append `*` to the origin abbreviation (e.g. `SUB*`, `DSK*`). Three detection methods from XML:
>   1. **Explicit `<Mirror>` element** — `<mem>` gives the mirrored pages; `<ps>`/`<ss>` identify the origin slot/device. Cell gets origin abbreviation + `*`.
>   2. **ROM file smaller than `<mem>` range** — compare ROM file size (looked up via SHA1 → `all_sha1s.txt` → file on disk) against the byte range covered by `<mem base size>`. Pages within the `<mem>` range that exceed the ROM file size are mirrors. First page = original; remainder = `<abbr>*`.
>   3. **`<rom_visibility>` present** — pages within the `<mem>` range but outside the `<rom_visibility>` range are mirrors. `rom_visibility` page = original; others = `<abbr>*`.
> - msx.org mirror extraction is deferred.

## References
- .claude/artifacts/planning/problem-description.md
- .claude/artifacts/project/project-meta.md
- .claude/artifacts/decisions/open-questions.md
- https://www.msx.org/wiki/Main_Page (Slot Map sections on model pages)
- https://github.com/openMSX/openMSX/tree/master/share (machine XML files)

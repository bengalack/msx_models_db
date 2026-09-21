# Design: Engine columns — parsing the scraped text into two ASIC columns

## Metadata
- Date: 2026-09-21
- Status: **Approved — decisions recorded below; ready to implement**
- Related:
  - Technical design: .claude/artifacts/planning/technical-design.md
  - Backlog: .claude/artifacts/planning/product-backlog.md
  - Prototype: scratchpad `engine_proto.py` (validated against all 46 live values)

## Problem

The scraped msx.org "Chipset" text lands in one column. It is free prose: vendor names, gate-array wording, uncertainty markers, double spaces, and several chips in one sentence. That makes the column wide and useless for sorting.

The maintainer supplied a target: two columns — **Engine (semi-custom ASIC)** (gate arrays) and **Engine (full-custom ASIC)** (MSX-Engines and similar) — with short chip ids, plus the original text on hover.

Scope: 46 distinct source values over 383 models (83 models have no value).

## Approach

A deterministic parser in the scraper, driven by a maintainer-editable chip dictionary. No per-source lookup table: every rule below is derived from the text, so new msx.org wordings are handled without editing a 46-row mapping. Unrecognised chips are reported (see Diagnostics) rather than silently dropped.

### Stage 1 — Normalise

1. Replace non-breaking spaces; collapse all whitespace runs (including line breaks) to one space; trim.
2. Remove the space before `)` and after `(`, and before `,`.
   Result: `"Yamaha  S3527"` → `"Yamaha S3527"`, `"… Fujitsu MB64H131 )"` → `"… Fujitsu MB64H131)"`.

### Stage 2 — Unknown and uncertainty markers

3. A value consisting only of `?`, `???` or whitespace → **both columns blank** (rendered as an em-dash, per the display rule below).
4. A leading `probably` / `possibly` (any case) → strip the word and mark the value *uncertain*.
5. A leading `?` → strip it and mark the value *uncertain* (decision D5).
6. *Uncertain* appends `?` to the rendered chip text: `probably Yamaha S3527` → `S3527?`.

### Stage 3 — Strip noise

7. Remove vendor names: Yamaha, Toshiba, Daewoo, Fujitsu, Hitachi, Mitsubishi, NEC, Sanyo, ASCII, Altera (dictionary-driven, extendable).
8. Remove filler: `gate array(s)`, `bus controller`, `chip(s)`, `model`, `separate IC's/ICs`, `whose a`, `two chips from`, `also`.
9. Drop purely explanatory parentheticals — `(a previous version of …)`, `(Gate array for lightpen interface)` — because they name chips that are not this model's engine. Parentheticals that qualify a chip (`(A or B)`) are kept.

### Stage 4 — Identify chips

10. Match against the **chip dictionary** (`data/engine-chips.json`): each entry is an id plus its class (semi-custom / full-custom). Longest match first, case-insensitive, whole-word.
11. Chips are listed in the order they appear in the source.
12. Special forms:
    - **T9769**: `T9769`, `T9769x`, `T9769 model A or B`, `T9769 B`, `T9769x (A or B)` → `T9769`, with the letters in parentheses when present: `T9769 (A or B)`, `T9769 (B)`.
    - **FPGA**: any value naming an FPGA (e.g. `Altera Cyclone EP1C12Q240C8N FPGA chip`) → `FPGA`.
    - **ULA**: `2 ULA and standard logic` → `2 ULA + std logic` (the word `standard` → `std`).
    - **none**: the word `none` means "no ASIC of this kind" → `None`.

### Stage 5 — Render each column

13. One chip → its id.
14. Several chips in the same column:
    - source says `or` (alternatives) → join with ` or `: `S1985 or S3527`
    - same chip family (shared alphabetic prefix, e.g. `TCX-`), or the source already used `/` → join with `/`: `TCX-1008/TCX-2001/TCX-2002`
    - otherwise → join with ` and `: `MB64H120 and uPD65002C022`, `T9769 (C) and S1990`
15. Per-version wording (`none … for /00 version, Yamaha S3527 for /19 … versions`) → the variants become alternatives: `None or S3527`.
16. Empty column → `None` when the source was understood (named a chip or said "none"); blank only for unknown sources (decision D1).
17. Sorting: cells sort as plain text, so short ids sort naturally; blanks sort last (existing grid behaviour).

### Display

18. Blank renders as an em-dash `—` (new: a blank cell currently renders empty).
19. **Tooltip**: hovering either Engine cell always shows the original scraped text, not only when the text is clipped. The grid already supports a per-cell tooltip (`td.dataset.tooltip`); what is missing is per-model data to fill it, so `ModelRecord` gains an optional `tooltips` map (`{ columnKey: text }`), serialised like the existing `links` map and only for cells whose source text exists.

## Data flow

| Path | Change |
|---|---|
| `data/engine-chips.json` | New maintainer-editable dictionary: chip id → class (semi/full), plus vendor and filler word lists |
| `scraper/engine.py` | New module: `parse_engine(raw) -> (semi, full)`; pure function, no I/O |
| `scraper/columns.py` | Scraped text moves to hidden `engine_raw`; `engine` (full-custom) and `engine_semi_custom` become derived columns; `nmos_cmos` derive reads `engine_raw` |
| `scraper/build.py` | Migrate the cached `engine` key to `engine_raw` (same pattern as `cartridge_slots` → `scraped_cart_slots`); serialise `tooltips` |
| `src/types.ts` | `ModelRecord.tooltips?: Record<string, string>` |
| `src/grid.ts` | Set `td.dataset.tooltip` from `tooltips`; render blank as `—` |
| `data/schema.md` | Document `tooltips` |

Merge precedence is unchanged: `local-raw.json` > openMSX > msx.org, all on `engine_raw`, so a maintainer override still flows through the parser.

## Diagnostics

- Any token that looks like a chip designator (`[A-Z]{1,4}[-]?\d{3,5}[A-Z0-9-]*`) but is not in the dictionary → `[WARN] engine: unrecognised chip 'X' in '<source>'`. The value still renders; the chip is simply not classified.
- The scraper never aborts on engine parsing.

## Testing

- `tests/scraper/test_engine.py`: one case per rule (normalisation, unknown, uncertainty, T9769 forms, joins, none, variants), plus a table-driven test over the maintainer's 46 expected rows held in a fixture file.
- Expectations come from the fixture and the chip dictionary, never hardcoded counts.
- `tests/web/engine-tooltip.test.ts`: a cell with a `tooltips` entry exposes it on hover regardless of clipping; blank renders as `—`.

## Decisions (2026-09-21)

- **D1 — blank vs `None`:** when the source is understood and names at least one chip (or says "none"), the other column renders `None`. Blank (em-dash) is reserved for unknown sources (`?`, `???`, empty). Resolves the 22 rows where the sample table did both.
- **D2 — `DW64MX1` is semi-custom.** Removed from the full-custom list. `Daewoo DW64MX1` (18 models) → semi-custom; `probably Daewoo DW64MX1` → `DW64MX1?` in semi-custom.
- **D3 — `M50014` is always semi-custom** (a gate array), in both T9769 sentences.
- **D4 — T9769 letters are always kept:** `T9769 C and ASCII S1990 bus controller` → `T9769 (C) and S1990`.
- **D5 — a leading `?` marks uncertainty**, like `probably`/`possibly`: `? Gate array Toshiba TCX-1012/TCX-1008` → `TCX-1012/TCX-1008?`.
- **D6 — `possibly` is treated exactly like `probably`:** take the chip id and append `?`.

## Expected output — all 46 source values

Produced by the prototype from the rules above; "Models" is how many models carry that source text.

| Source text | Models | Semi-custom ASIC | Full-custom ASIC |
|---|---:|---|---|
| `2 ULA and standard logic` | 1 | 2 ULA + std logic | None |
| `?` | 6 | — | — |
| `? Gate array Toshiba TCX-1012/TCX-1008` | 1 | TCX-1012/TCX-1008? | None |
| `? none (separate IC's)` | 1 | None | None |
| `???` | 1 | — | — |
| `Altera Cyclone EP1C12Q240C8N FPGA chip` | 4 | None | FPGA |
| `Daewoo DW64MX1` | 18 | DW64MX1 | None |
| `Gate array Toshiba TCX-1007` | 1 | TCX-1007 | None |
| `Gate array Toshiba TCX-1012` | 2 | TCX-1012 | None |
| `Gate array Toshiba TCX-1012/TCX-1008` | 1 | TCX-1012/TCX-1008 | None |
| `Gate arrays (Toshiba TCX-1008, TCX-2001 and TCX-2002)` | 1 | TCX-1008/TCX-2001/TCX-2002 | None |
| `Gate arrays Toshiba TCX-1008, TCX-2001 and TCX-2002` | 1 | TCX-1008/TCX-2001/TCX-2002 | None |
| `Hitachi HD62003` | 1 | HD62003 | None |
| `MB64H120, uPD65002C022 (Gate array for lightpen interface)` | 1 | MB64H120 and uPD65002C022 | None |
| `NEC AW100` | 1 | AW100 | None |
| `none` | 1 | None | None |
| `none (separate IC's)` | 102 | None | None |
| `none (separate IC's) for /00 version, Yamaha S3527 for /19, /20, /29 and /40 versions` | 1 | None | None or S3527 |
| `None (separate ICs whose a gate array Fujitsu MB64H131 )` | 2 | MB64H131 | None |
| `None (separate ICs whose a gate array Hitachi HG61H06 )` | 2 | HG61H06 | None |
| `probably Daewoo DW64MX1` | 1 | DW64MX1? | None |
| `probably Toshiba T7775` | 1 | None | T7775? |
| `Probably Yamaha S1985` | 1 | None | S1985? |
| `probably Yamaha S1985` | 2 | None | S1985? |
| `probably Yamaha S3527` | 4 | None | S3527? |
| `Toshiba  T7937A` | 3 | None | T7937A |
| `Toshiba T7775` | 4 | None | T7775 |
| `Toshiba T7937` | 2 | None | T7937 |
| `Toshiba T7937 or T7937A` | 2 | None | T7937 or T7937A |
| `Toshiba T7937A` | 4 | None | T7937A |
| `Toshiba T9763` | 1 | None | T9763 |
| `Toshiba T9769` | 1 | None | T9769 |
| `Toshiba T9769 B` | 1 | None | T9769 (B) |
| `Toshiba T9769 C and ASCII S1990 bus controller` | 2 | None | T9769 (C) and S1990 |
| `Toshiba T9769 C and NEC S1990 bus controller` | 1 | None | T9769 (C) and S1990 |
| `Toshiba T9769 model A or B and gate array Mitsubishi M50014` | 2 | M50014 | T9769 (A or B) |
| `Toshiba T9769 model B or C and gate array Mitsubishi M50014` | 1 | M50014 | T9769 (B or C) |
| `Toshiba T9769x (A or B)` | 3 | None | T9769 (A or B) |
| `Yamaha  S3527` | 4 | None | S3527 |
| `Yamaha S1985` | 34 | None | S1985 |
| `Yamaha S1985 + Sanyo CF77099AFT` | 1 | CF77099AFT | S1985 |
| `Yamaha S1985 or Yamaha S3527` | 3 | None | S1985 or S3527 |
| `Yamaha S3527` | 60 | None | S3527 |
| `Yamaha S3527 also two chips from Toshiba  TC17G005AP-0007` | 1 | TC17G005AP-0007 | S3527 |
| `Yamaha X3527 (a previous version of the Yamaha S3527 )` | 1 | None | X3527 |
| `Yamaha YM5214` | 11 | YM5214 | None |

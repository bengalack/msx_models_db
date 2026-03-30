# Plan: Slot Map — Column Definitions + LUT

## Metadata
- Date: 2026-03-30
- Backlog item: Slot map — column definitions + LUT
- Feature slug: slotmap-columns-and-lut

## Context
- Intended outcome: Add 4 slot map column groups (64 columns total) to the column configuration, create the maintainer-controlled LUT vocabulary file, wire LUT loading/validation into the build pipeline, and embed the compact LUT in `data.js` for browser-side tooltip lookup. This is the foundation required by the slot map XML extractor and browser tooltip renderer.

## Functional Snapshot
- Problem: The scraper and browser have no definition of the 64 slot map columns or the vocabulary (abbreviation → tooltip) used to populate them. Without these, slot map data cannot be classified, stored, or displayed.
- Target user: bengalack (maintainer) running the build; MSX enthusiasts reading slot map tooltips in the browser.
- Success criteria (observable):
  - `python -m scraper build` completes without error after changes (data.js is generated with 4 new groups and 64 new columns).
  - `data.js` contains a `slotmap_lut` key with at least 13 abbreviation → tooltip entries.
  - `validate_config(GROUPS, COLUMNS)` raises no errors with the new definitions.
  - LUT loading raises `ValueError` on a malformed or duplicate-abbr LUT file.
- Primary user flow:
  1. Maintainer runs `python -m scraper build`.
  2. Build loads `scraper/columns.py` → 4 new groups (IDs 8–11) and 64 new columns (IDs 30–93) pass validation.
  3. Build loads `data/slotmap-lut.json` → 13 rules validated, no duplicates.
  4. `data.js` is written with new groups/columns and `slotmap_lut: { MAIN: "MSX BIOS with BASIC ROM", ... }`.
  5. Browser reads `MSX_DATA.slotmap_lut` and can resolve any abbreviation to its tooltip string.
- Must never happen:
  - Duplicate column IDs or group IDs (config validation must catch this at import time).
  - Duplicate `abbr` values in LUT (load must raise on this).
  - LUT with malformed regex pattern silently accepted (load must raise).
  - `data.js` emitted without `slotmap_lut` key when LUT is present.
- Key edge cases:
  - LUT file absent → build raises a clear `FileNotFoundError` with path, not a KeyError.
  - LUT entry with `id_pattern: null` (element-type-only match) → valid, regex treated as match-all.
  - Column with `short_label` omitted → falls back to `label` (existing Column dataclass behaviour).
- Business rules:
  - Group IDs 8–11 are assigned to "Slotmap, slot 0–3" in order; no gaps.
  - Column IDs start at 30 (next after existing 29); sequential through 93; no gaps; no reuse.
  - Column key convention: `slotmap_{ms}_{ss}_{p}` where ms=main slot (0–3), ss=sub-slot (0–3), p=page (0–3).
  - Column label convention: `{ss} / P{p}` (with non-breaking spaces) e.g. `0 / P0`, `2 / P1`; the main slot is shown in the group header.
  - `~` and mirror `*` are runtime values, not LUT entries.
  - `CS{N}` is handled in scraper code (derived from XML `slot` attribute), not a LUT entry.
  - LUT rules are evaluated in order; first match wins.
- Integrations:
  - `scraper/columns.py` → consumed by `scraper/build.py` at import time; validation runs at import.
  - `data/slotmap-lut.json` → read by new `scraper/slotmap_lut.py` module; embedded in `data.js` by `scraper/output.py`.
  - Failure behavior: missing or malformed LUT → build raises and exits non-zero before writing any output.
- Non-functional requirements:
  - Performance: LUT load is once-per-build; 13 entries; negligible cost.
  - Reliability: Validation runs at import/load time; never silently produces a broken build.
- Minimal viable increment (MVI): All 3 chunks delivered together — columns defined, LUT file exists with starter vocabulary, LUT embedded in data.js. The feature is not useful until all three are in place.
- Deferred:
  - Actual slot map XML extraction (next backlog item).
  - Browser tooltip rendering (subsequent backlog item).
  - msx.org slot map parsing (explicitly out of scope this iteration).

## Executable Specification (Gherkin)

```gherkin
Feature: Slot map column definitions and LUT
  The scraper defines 64 slot map columns across 4 groups and a maintainer-controlled
  vocabulary LUT. The LUT is validated at build time and embedded in data.js for
  browser tooltip lookup.

  Background:
    Given the scraper package is installed and importable
    And data/slotmap-lut.json contains the starter vocabulary with 13 rules

  Scenario: Column config passes validation with slot map additions
    Given scraper/columns.py defines groups with IDs 0-11 and columns with IDs 1-93
    When the module is imported
    Then validate_config raises no errors
    And GROUPS contains exactly 12 entries
    And COLUMNS contains exactly 93 entries
    And each slotmap column key matches the pattern "slotmap_{ms}_{ss}_{p}"
    And each slotmap column label matches the pattern "{ss} / P{p}" (non-breaking spaces)

  Scenario: Slot map groups are numbered and ordered correctly
    When the module is imported
    Then the four slotmap groups have IDs 8, 9, 10, 11
    And their labels are "Slotmap, slot 0", "Slotmap, slot 1", "Slotmap, slot 2", "Slotmap, slot 3"
    And their order values are 8, 9, 10, 11

  Scenario: LUT loads and validates successfully
    Given data/slotmap-lut.json is a valid JSON file with no duplicate abbr values
    When load_slotmap_lut() is called with the file path
    Then it returns an ordered list of 13 rule dicts
    And each rule has keys: element, id_pattern, abbr, tooltip

  Scenario: LUT with duplicate abbreviation is rejected
    Given a LUT file containing two rules both with abbr "MAIN"
    When load_slotmap_lut() is called with that file path
    Then it raises ValueError mentioning the duplicate abbr "MAIN"

  Scenario: LUT with malformed regex pattern is rejected
    Given a LUT file containing a rule with id_pattern "[invalid("
    When load_slotmap_lut() is called with that file path
    Then it raises ValueError mentioning the invalid pattern

  Scenario: Missing LUT file raises a clear error
    Given data/slotmap-lut.json does not exist
    When load_slotmap_lut() is called with that path
    Then it raises FileNotFoundError containing the file path

  Scenario: data.js contains slotmap_lut after a successful build
    Given a valid column config and LUT file
    When python -m scraper build runs to completion
    Then docs/data.js contains a slotmap_lut key
    And slotmap_lut is a flat object mapping each abbr to its tooltip string
    And the object contains at least the 13 starter abbreviations

  Scenario: Compact LUT omits rule metadata
    Given the starter LUT has 13 rules each with element, id_pattern, abbr, tooltip
    When the compact LUT is built for data.js embedding
    Then the compact LUT contains only {abbr: tooltip} pairs
    And it does not contain element or id_pattern fields
```

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branch: `feature/slotmap-columns-and-lut`.

## Architecture Fit
- Touch points:
  - `scraper/columns.py` — add 4 groups and 64 columns (append-only; existing validation reused).
  - `data/slotmap-lut.json` — new file, committed to repo.
  - `scraper/slotmap_lut.py` — new module: `load_slotmap_lut(path)` → validated rule list; `compact_lut(rules)` → `{abbr: tooltip}`.
  - `scraper/output.py` — extend `data.js` writer to include `slotmap_lut` key.
  - `scraper/build.py` — load LUT at build startup; pass compact LUT to output writer.
- Compatibility notes: All changes are additive. Existing 29 columns and 8 groups are untouched. Existing data.js consumers ignore unknown top-level keys.

## Observability (Minimum Viable)
- Applicability: N/A for runtime. Build-time only.
- Failure modes:
  - LUT file missing → `FileNotFoundError` with path; build exits non-zero.
  - LUT invalid (duplicate abbr, malformed regex) → `ValueError` with clear message; build exits non-zero.
  - Column config invalid → existing `ValueError` from `validate_config`; build exits non-zero.
- Logs: `[INFO] Loaded slotmap LUT: {n} rules from {path}` on successful load.

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required — pytest):
  - `test_columns_slotmap.py`: import `columns.py`; assert group count = 12, column count = 93; assert group IDs 8–11 exist with correct labels/order; assert all slotmap column keys match `slotmap_{ms}_{ss}_{p}` pattern; assert all slotmap labels match `{ss} / P{p}` pattern (non-breaking spaces); assert no duplicate IDs or keys.
  - `test_slotmap_lut.py`: happy-path load of starter LUT; duplicate abbr rejection; malformed regex rejection; missing file raises `FileNotFoundError`; `compact_lut()` returns `{abbr: tooltip}` only (no element/id_pattern).
- Tier 1 (build integration — pytest):
  - Run `python -m scraper build` against cached raw data; assert `docs/data.js` contains `slotmap_lut` with all 13 starter abbrs; assert `groups` array in data.js has 12 entries; assert `columns` array has 93 entries.
- Tier 2: N/A.

## Data and Migrations
- Applicability: Schema only (data.js gains new groups, columns, and slotmap_lut key).
- Up migration: Additive — new groups/columns appended; new `slotmap_lut` key added to MSXData. No existing data is removed or changed.
- Down migration: No — reverting would require removing groups/columns from data.js and retiring IDs 30–93. Acceptable: this is a development-phase change before first public release; ID retirement rules apply only post-release.
- Backfill plan: None. Slot map column values are `null` for all models until the XML extractor (next feature) populates them.
- Rollback considerations: If reverted, IDs 30–93 and group IDs 8–11 must be treated as reserved (not reused) in any future config, per the stable-ID invariant.

## Rollout and Verify
- Applicability: N/A — offline build tool, no staged rollout needed.
- Strategy: All-at-once (commit to main after green CI).
- Verify (smoke path):
  1. `python -m scraper build` runs without error.
  2. `docs/data.js` contains `"slotmap_lut"`.
  3. Open `docs/index.html` — page loads, existing columns intact, 4 new slot map groups visible (empty/null cells).
  4. `pytest tests/scraper/` — all green.
  5. `npm test -- --run` — all green.

## Cleanup Before Merge
- Remove: none (no spike code or temp flags).
- Squash intermediate commits into logical commits (one per chunk is ideal).
- Ensure all commits follow Conventional Commits.
- Rebase onto trunk; merge fast-forward only.

## Definition of Done
- Gherkin specification complete and current.
- Tier 0 green; Tier 1 green.
- `validate_config` passes at import time with 12 groups and 93 columns.
- `data.js` includes `slotmap_lut` with all 13 starter abbreviations.
- Backlog item moved to "In product (shipped)".

## Chunks

- Chunk 1: Slot map groups + columns in columns.py
  - User value: Column config is complete and validates — downstream scraper and UI can reference all 64 slot map columns by ID/key.
  - Scope: `scraper/columns.py` only — add 4 Group entries (IDs 8–11) and 64 Column entries (IDs 30–93). No other files change.
  - Ship criteria: `python -c "from scraper.columns import GROUPS, COLUMNS; print(len(GROUPS), len(COLUMNS))"` prints `12 93`; all Tier 0 column tests green.
  - Rollout notes: None.

- Chunk 2: LUT file + load/validate module
  - User value: Vocabulary is defined and validated — the scraper can classify devices and the browser can resolve tooltips.
  - Scope: Create `data/slotmap-lut.json` with 13 starter rules; create `scraper/slotmap_lut.py` with `load_slotmap_lut()` and `compact_lut()`.
  - Ship criteria: All Tier 0 LUT tests green; `load_slotmap_lut("data/slotmap-lut.json")` returns 13 rules.
  - Rollout notes: None.

- Chunk 3: Wire LUT into build + embed in data.js
  - User value: `data.js` contains the compact LUT — browser can resolve abbreviation tooltips from day one (even before slot map extraction is live).
  - Scope: `scraper/build.py` (load LUT at startup, pass to output); `scraper/output.py` (add `slotmap_lut` key to MSXData output).
  - Ship criteria: Tier 1 build integration test green; `data.js` contains `slotmap_lut` with all 13 starter abbrs.
  - Rollout notes: None.

## Relevant Files (Expected)
- `scraper/columns.py` — add Group IDs 8–11 and Column IDs 30–93
- `data/slotmap-lut.json` — new file, starter vocabulary (13 rules)
- `scraper/slotmap_lut.py` — new module: `load_slotmap_lut()`, `compact_lut()`
- `scraper/build.py` — load LUT at startup; pass compact LUT to output step
- `scraper/output.py` — add `slotmap_lut` key to MSXData written to data.js
- `tests/scraper/test_columns_slotmap.py` — Tier 0 column tests (new file)
- `tests/scraper/test_slotmap_lut.py` — Tier 0 LUT tests (new file)

## Notes
- Column IDs 30–93 are assigned sequentially; the 64 entries cover all combinations of ms∈{0,1,2,3} × ss∈{0,1,2,3} × p∈{0,1,2,3}. The natural ordering is: iterate ms 0→3, then ss 0→3, then p 0→3 (so ID 30 = `slotmap_0_0_0`, ID 31 = `slotmap_0_0_1`, …, ID 93 = `slotmap_3_3_3`).
- Group IDs 8–11 extend the existing 0–7 range without gaps. `order` values match IDs (8, 9, 10, 11).
- The LUT JSON format is an **array** (ordered, not object) so rule priority is explicit.
- `CS{N}` and `~` are not LUT entries. `CS{N}` is emitted directly by the extractor from the XML slot attribute. `~` is the sentinel for unoccupied pages. Mirror `*` is appended at extraction time.
- The compact LUT embedded in data.js is a plain JS object `{ "MAIN": "MSX BIOS with BASIC ROM", ... }` — not the full rule array.

## Assumptions
- IDs 30–93 are currently unassigned (confirmed: highest existing column ID is 29).
- Group IDs 8–11 are currently unassigned (confirmed: highest existing group ID is 7).
- The existing `Column` dataclass, `validate_config`, and `output.py` do not need structural changes — only additions and a new top-level key in the output.
- `scraper/build.py` already has a clear point to inject the LUT load step before the output write.

## Validation Script (Draft)
1. `python -m pytest tests/scraper/test_columns_slotmap.py tests/scraper/test_slotmap_lut.py -v` — all green.
2. `python -m scraper build` — exits 0, prints `[INFO] Loaded slotmap LUT: 13 rules`.
3. `python -c "import json; d=open('docs/data.js').read(); assert 'slotmap_lut' in d; print('slotmap_lut present')"`.
4. `python -c "from scraper.columns import GROUPS, COLUMNS; assert len(GROUPS)==12 and len(COLUMNS)==93; print('OK')"`.
5. Open `docs/index.html` in browser — page loads without JS errors; 4 slot map column groups visible in column picker.

## Tasks

- [x] T-001 Create and checkout branch `feature/slotmap-columns-and-lut`

- [x] Chunk 1: Slot map groups + columns in columns.py
  - [x] T-010 Add Group entries IDs 8–11 ("Slotmap, slot 0–3") to GROUPS in `scraper/columns.py`
  - [x] T-011 Generate and add 64 Column entries (IDs 30–93, keys `slotmap_{ms}_{ss}_{p}`, labels `{ss} / P{p}` (non-breaking spaces), group `slotmap_{ms}`, type "string") to COLUMNS in `scraper/columns.py`
  - [x] T-012 Tests: create `tests/scraper/test_columns_slotmap.py` — assert 12 groups, 93 columns, no duplicate IDs/keys, correct group labels/order, all slotmap key/label patterns valid

- [x] Chunk 2: LUT file + load/validate module
  - [x] T-020 Create `data/slotmap-lut.json` with 13 starter rules (MAIN, SUB, KNJ, JE, FW, DSK, MUS, RS2, MM, PM, RAM, EXP, ~ — see problem-description-slotmap.md Starter LUT Vocabulary table for element/id_pattern/abbr/tooltip values)
  - [x] T-021 Create `scraper/slotmap_lut.py` with `load_slotmap_lut(path: str | Path) -> list[dict]` — reads JSON, validates: no duplicate abbrs, all id_pattern values compile as regex; raises `ValueError` or `FileNotFoundError` on failure; logs `[INFO] Loaded slotmap LUT: {n} rules from {path}` on success
  - [x] T-022 Add `compact_lut(rules: list[dict]) -> dict[str, str]` to `scraper/slotmap_lut.py` — returns `{abbr: tooltip}` flat dict
  - [x] T-023 Tests: create `tests/scraper/test_slotmap_lut.py` — happy-path load (13 rules), duplicate abbr raises ValueError, malformed regex raises ValueError, missing file raises FileNotFoundError, compact_lut returns abbr→tooltip only

- [x] Chunk 3: Wire LUT into build + embed in data.js
  - [x] T-030 In `scraper/build.py`: load LUT via `load_slotmap_lut("data/slotmap-lut.json")` early in build flow (before output write); pass `compact_lut(rules)` to output step
  - [x] T-031 In `scraper/build.py`: add `slotmap_lut` key to the MSXData payload written to `data.js` (note: no separate output.py exists — payload is assembled inline in build.py)
  - [x] T-032 Tests: extend build integration test — run full build, assert `data.js` contains `slotmap_lut` with all 13 starter abbrs as keys

- [x] Quality gate
  - [x] T-900 Run `python -m pytest tests/scraper/ -v` — all green (116 passed)
  - [x] T-901 Run `npm test -- --run` — all green (31 passed)
  - [x] T-902 Run `npm run lint && npm run typecheck` — clean

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits (one per chunk)
  - [ ] T-951 Verify all commits follow Conventional Commits (`feat:`, `test:`, `chore:` as appropriate)
  - [ ] T-952 Rebase onto trunk and merge fast-forward only


## Open Questions
- None blocking. Starter LUT vocabulary is fully defined in problem-description-slotmap.md.

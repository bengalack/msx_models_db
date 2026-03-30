# Plan: Slot map — XML extractor

## Metadata
- Date: 2026-03-30
- Backlog item: Slot map — XML extractor
- Feature slug: slotmap-xml-extractor

## Context
- Intended outcome: Running `python -m scraper build --fetch` populates all 64 `slotmap_{ms}_{ss}_{p}` columns per model in `openmsx-raw.json` and therefore in `data.js`. The grid displays real slot map values instead of nulls, with mirror cells annotated as `abbr*`.

## Functional Snapshot
- Problem: The 64 slot map columns exist in the schema and `data.js` but every cell is null because no extractor reads the openMSX XML slot hierarchy.
- Target user: bengalack running the scraper build; MSX enthusiasts reading the grid.
- Success criteria (observable):
  - `python -m scraper build --fetch` produces `openmsx-raw.json` where each model dict contains all 64 `slotmap_{ms}_{ss}_{p}` keys
  - Slot map values match the Sony HB-F1XV reference layout (verified manually or by fixture test)
  - Cartridge slots show `CS1` / `CS2` for the external primary slots
  - Mirror cells show `abbr*` (e.g. `SUB*` for mirrored Sub ROM pages in the Philips NMS 8255)
  - Unknown device element types: a `[WARN]` line is printed; raw element tag written as cell value; build continues
  - Missing `systemroms/` directory: mirror method 2 is silently skipped; all other cells extracted correctly
- Primary user flow:
  1. Maintainer runs `python -m scraper build --fetch`
  2. `openmsx.fetch_all()` fetches and parses each XML; `extract_slotmap()` is called for each machine
  3. 64 slotmap keys added to each model dict alongside the existing hardware fields
  4. Model dicts cached in `openmsx-raw.json`; `build.py` writes them into `data.js`
  5. Grid shows slot map columns populated with real data
- Must never happen:
  - Unknown device element causes an exception or aborts the build
  - A missing `systemroms/` directory causes an exception
  - Any of the 64 keys is absent from the output — all must be present, defaulting to `~`
- Key edge cases:
  - `<primary external="true" slot="N">` → CS{N} in sub-slot 0 pages 0-3; sub-slots 1-3 all `~`
  - Non-expanded `<primary>` (no `<secondary>` children) → classify direct device children; sub-slots 1-3 all `~`
  - Empty `<secondary slot="ss"/>` or missing secondary element → all 4 pages `~`
  - Multiple devices on the same page → first device wins; `[WARN]` for the overlap
  - ROM with `<mem size="0x10000">` but 16KB file on disk → pages 1-3 = `abbr*` (method 2)
  - ROM with `<rom_visibility>` narrower than `<mem>` → pages outside visibility = `abbr*` (method 1)
  - `<Mirror>` element pointing to another slot → cross-slot abbr + `*` (method 3, two-pass)
  - SHA1 not found in `all_sha1s.txt` → `[WARN]`; skip mirror detection for that ROM; other cells unaffected
  - Machine with no `<devices>` element → all 64 cells `~`; no exception
- Business rules:
  - All 64 cells are always present in the output, defaulting to `~`
  - LUT matching: element tag matches pipe-separated `element` field; `id` attribute (case-insensitive) matches `id_pattern` regex; first rule wins; `id_pattern: null` means match any id
  - `CS{N}`: derived from `slot="N"` attribute on `<primary external="true">`; not a LUT entry
  - `~` sentinel: used for missing/empty sub-slots; a LUT entry exists for it but it is never matched against real devices — only written as default
  - Mirror cells: written as `{abbr}*` where `abbr` is the abbreviation of the origin device
  - Overlap rule: page assignment from `<mem base size>` — page N covered when `[N×0x4000, (N+1)×0x4000)` intersects `[base, base+size)`
  - Unknown device: element tag not matched by any LUT rule → `[WARN] Unmatched device: <tag> id="<id>" in <filename>`; raw element tag written as cell value
- Integrations:
  - `data/slotmap-lut.json` — loaded once by `build.py`; rules passed into extractor
  - `systemroms/machines/all_sha1s.txt` — optional; used for mirror method 2; gracefully skipped if absent
  - `systemroms/machines/` ROM files — optional; used for mirror method 2; gracefully skipped per ROM if file absent
- Non-functional requirements:
  - No network access in tests
  - `systemroms/` ROM files not required for tests (fixtures use inline SHA1 + temp files)
- Minimal viable increment (MVI): Core extractor without mirrors (chunk 1) already delivers populated slot map columns for most models. Mirror detection (chunk 2) adds accuracy for machines with mirrored ROMs.
- Deferred:
  - msx.org slot map scraping (explicitly out of scope this iteration)
  - Browser tooltip rendering (next feature after this one)

## Executable Specification (Gherkin)

```gherkin
Feature: Slot map XML extractor
  The scraper extracts per-model slot map data from openMSX machine XML files,
  populating 64 cells (4 main slots × 4 sub-slots × 4 pages) per model
  with LUT-matched abbreviations. Mirror cells are annotated with an asterisk.

  Background:
    Given the slot map LUT is loaded from data/slotmap-lut.json

  Scenario: Expanded slot with known devices produces correct cell values
    Given the Sony HB-F1XV XML (slot 3 expanded: MM in 3-0, SUB/KNJ/KNJ/~ in 3-1, ~/DSK/~/~ in 3-2, ~/MUS/~/~ in 3-3)
    When extract_slotmap is called
    Then slotmap_3_0_0 through slotmap_3_0_3 equal "MM"
    And slotmap_3_1_0 equals "SUB", slotmap_3_1_1 and _2 equal "KNJ", slotmap_3_1_3 equals "~"
    And slotmap_3_2_1 equals "DSK", pages 0/2/3 of 3-2 equal "~"
    And slotmap_3_3_1 equals "MUS", pages 0/2/3 of 3-3 equal "~"

  Scenario: External primary slot produces CS{N} abbreviation
    Given a machine with slot 1 declared as external="true"
    When extract_slotmap is called
    Then slotmap_1_0_0 through slotmap_1_0_3 all equal "CS1"
    And slotmap_1_1_0 through slotmap_1_3_3 all equal "~"

  Scenario: All 64 keys are always present, unknown values default to tilde
    Given a machine XML with no <devices> element
    When extract_slotmap is called
    Then the result contains exactly 64 keys matching slotmap_{0-3}_{0-3}_{0-3}
    And all values equal "~"

  Scenario: Unknown device element produces a warning and raw tag in the cell
    Given a machine XML with a device element "FutureTech" not in the LUT
    When extract_slotmap is called
    Then a [WARN] line is printed containing "FutureTech" and the machine filename
    And the affected cell value equals "FutureTech"
    And all other cells are unaffected

  Scenario: ROM file size smaller than mem range produces mirror annotation (method 2)
    Given the Philips NMS 8255 XML where Sub ROM has mem size=0x10000 but the file is 16 KB
    And the SHA1 index maps the Sub ROM SHA1 to a 16 KB file on disk
    When extract_slotmap is called with sha1_index_path pointing to the index
    Then slotmap_3_0_0 equals "SUB" (real content in page 0)
    And slotmap_3_0_1 through slotmap_3_0_3 equal "SUB*" (mirror pages)

  Scenario: Missing systemroms directory does not abort the build
    Given a machine XML with a ROM that has a SHA1
    And the sha1_index_path parameter is None (systemroms not available)
    When extract_slotmap is called
    Then no exception is raised
    And the ROM pages are filled with the plain abbreviation (no mirror annotation)

  Scenario: Mirror element annotates pages in another slot (method 3)
    Given a machine XML where slot 0 non-expanded contains a ROM at pages 0-1
    And a Mirror element at page 3 pointing to slot 3 which contains RAM
    When extract_slotmap is called (two-pass)
    Then slotmap_0_0_0 and slotmap_0_0_1 equal "MAIN"
    And slotmap_0_0_2 equals "~"
    And slotmap_0_0_3 equals "RAM*"
```

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points:
  - `scraper/slotmap.py` — new module; exports `extract_slotmap()`
  - `scraper/openmsx.py` — `parse_machine_xml()` gains optional `lut_rules` + `sha1_index` params; `fetch_all()` gains same params, passes through
  - `scraper/build.py` — passes loaded `lut_rules` and optional `sha1_index` to `fetch_all()`
  - `tests/scraper/test_slotmap.py` — new test file
- Compatibility notes:
  - `parse_machine_xml()` signature change is additive (new optional params, default None); existing tests and calls unaffected
  - `openmsx-raw.json` gains 64 new keys per model — backwards-compatible (consumers ignore unknown keys)

## Observability (Minimum Viable)
- Applicability: Required
- Failure modes:
  - Unknown device element → `[WARN] Unmatched device: <tag> id="<id>" in <filename>` to stdout; continue
  - Page overlap → `[WARN] Page overlap: <tag> id="<id>" overlaps page N in <filename>; first device wins`
  - SHA1 not found in index → `[WARN] SHA1 not found in index: <sha1> in <filename>; skipping mirror detection for this ROM`
  - ROM file not found on disk → `[WARN] ROM file not found: <path> in <filename>; skipping mirror`
  - `<Mirror>` origin slot has no classified device → `[WARN] Mirror origin slot {ps}/{ss} not yet classified in <filename>; skipping`
- Logs:
  - Per-machine: warnings only (no info per machine — too verbose)
  - Summary: existing openMSX summary log (`N models extracted`) already covers the run
- Signals/metrics: warning count surfaced through the existing per-model error count in `fetch_all()` summary log

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): pytest unit tests — XML as inline bytes; SHA1 index and ROM files as temp files; no network; covers all LUT matching rules, page calculation, CS{N}, all three mirror methods, unknown device warn+continue, overlap warn+continue, missing sha1/file graceful skip
- Tier 1 (integration): One build integration test in `test_build.py` — verify a model dict built from a fixture XML with slot map data has slotmap keys present in the `data.js` output
- Tier 2: N/A

## Data and Migrations
- Applicability: Schema only — `openmsx-raw.json` gains 64 new string fields per model; no registry change; no data.js version bump required (additive column values only)

## Rollout and Verify
- Applicability: N/A (offline scraper; no deployment step)

## Cleanup Before Merge
- Remove any debug print statements introduced during development
- Squash intermediate commits into logical commits (one per chunk)
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge (fast-forward only)

## Definition of Done
- [ ] Gherkin specification complete and current
- [ ] `pytest tests/scraper/test_slotmap.py` passes (≥ 30 tests)
- [ ] `pytest tests/scraper/` full suite green
- [ ] Sony HB-F1XV fixture produces correct reference layout
- [ ] Philips NMS 8255 Sub ROM mirror (method 2) verified in tests
- [ ] Cleanup gate satisfied
- [ ] Backlog updated

## Chunks

- **Chunk 1 — Core extractor + wiring (no mirrors)**
  - User value: `openmsx-raw.json` gains 64 slot map keys per model; grid columns populated for most machines
  - Scope: `scraper/slotmap.py` (new); `scraper/openmsx.py` (wire in); `scraper/build.py` (pass params); `tests/scraper/test_slotmap.py` (new)
  - Ship criteria: HB-F1XV fixture produces correct layout; all 64 keys present; unknown device warns + continues; tests green
  - Rollout notes: None

- **Chunk 2 — Mirror detection (all 3 methods)**
  - User value: Mirror cells annotated as `abbr*`; Sub ROM mirrors, BIOS mirrors, and cross-slot hardware mirrors displayed correctly
  - Scope: `scraper/slotmap.py` (extend `extract_slotmap()`); `scraper/openmsx.py` (pass sha1_index); `scraper/build.py` (pass sha1_index_path); additional tests in `test_slotmap.py`
  - Ship criteria: NMS 8255 Sub ROM mirror verified (method 2); rom_visibility mirror verified (method 1); Mirror element cross-slot verified (method 3); missing SHA1/file gracefully skipped
  - Rollout notes: None

## Relevant Files (Expected)
- `scraper/slotmap.py` — new module (core extractor + mirror detection)
- `scraper/openmsx.py` — wire `extract_slotmap()` into `parse_machine_xml()` and `fetch_all()`
- `scraper/build.py` — pass `lut_rules` and `sha1_index_path` to `fetch_all()`
- `scraper/slotmap_lut.py` — already exists; used as-is
- `data/slotmap-lut.json` — already exists; consumed by extractor
- `tests/scraper/test_slotmap.py` — new test file
- `tests/scraper/test_build.py` — add integration test for slotmap keys in output
- `systemroms/machines/all_sha1s.txt` — read-only; used at runtime only

## Notes
- `extract_slotmap()` returns `dict[str, str]` — all 64 keys always present; values are `~`, an abbreviation, `abbr*`, or a raw element tag for unknowns
- SHA1 index is pre-parsed once into `dict[str, Path]` and passed in; avoids re-reading the file per-machine
- Mirror method 2: the ROM covers bytes `[0, file_size)` within its `<mem>` range. Pages beyond `base + file_size` but within `base + mem_size` are mirrors. Only applies when `file_size < mem_size`.
- For `<secondary slot="ss"/>` (self-closing with no device children): treat as empty → all 4 pages `~`
- `<secondary slot="ss">` missing entirely from the XML: all 4 pages `~`
- Both cases are indistinguishable in output: `~`
- The `EXP` LUT entry (element: "secondary") is NOT used for page assignment — it was a design artefact. Expansion is purely structural (the presence of `<secondary>` children determines whether a primary is expanded). Remove the EXP entry consideration from matching logic; it will never match a slottable device.

## Assumptions
- `lxml` already installed (it is — see requirements.txt)
- `systemroms/machines/` exists on the maintainer's machine but not in CI — mirror method 2 gracefully degrades to no-op when sha1_index_path is None
- The EXP ("secondary") LUT entry is structural metadata only and should never be returned by `match_lut()` for actual device elements — guard against it in the matcher

## Validation Script (Draft)
1. `pytest tests/scraper/test_slotmap.py -v` — all tests green
2. `pytest tests/scraper/ -v` — full suite green
3. Manual (optional): `python -m scraper fetch-openmsx -o /tmp/openmsx.json` — spot-check Sony_HB-F1XV.xml entry for slotmap keys

## Tasks
- [x] T-001 Create and checkout a local branch (`feature/slotmap-xml-extractor`)

- [x] Implement: Chunk 1 — Core extractor + wiring
  - [x] T-010 Write `scraper/slotmap.py`: `match_lut()`, `pages_for_mem()`, and `extract_slotmap()` skeleton initialising all 64 cells to `~`
  - [x] T-011 Implement primary slot walk in `extract_slotmap()`: external primary → CS{N}; non-expanded primary → classify direct device children; expanded primary → iterate secondary slots 0-3
  - [x] T-012 Implement `_classify_devices()`: iterate device children of a slot element, match each via LUT, assign pages via `pages_for_mem()`, warn on overlap (first wins), warn on unknown element
  - [x] T-013 Wire into `scraper/openmsx.py`: add `lut_rules` optional param to `parse_machine_xml()` and `fetch_all()`; call `extract_slotmap()` and merge 64 keys into result dict when lut_rules provided
  - [x] T-014 Wire into `scraper/build.py`: pass `lut_rules` to `fetch_all()` in the build step
  - [x] T-015 Tests: expanded primary fixture (HB-F1XV-like) — verify MAIN, CS1/CS2, MM, SUB, KNJ, DSK, MUS cells
  - [x] T-016 Tests: non-expanded primary, empty secondary, missing devices element, unknown device warn+continue, page overlap warn+continue
  - [x] T-017 Build integration test: model dict in `data.js` output has 64 slotmap keys

- [x] Implement: Chunk 2 — Mirror detection
  - [x] T-020 Add `load_sha1_index(path) → dict[str, Path]` to `slotmap.py`: parse `all_sha1s.txt` → SHA1 → relative path; return empty dict if path is None
  - [x] T-021 Implement mirror method 1 (`<rom_visibility>`): after page assignment for each ROM, check for `<rom_visibility>`; mark pages in `[mem]` but outside `[rom_visibility]` as `abbr*`
  - [x] T-022 Implement mirror method 2 (ROM file size): for each ROM device, look up SHA1 in index, find file on disk, measure size; mark pages beyond file coverage as `abbr*`; warn if SHA1 missing or file absent; skip gracefully
  - [x] T-023 Implement mirror method 3 (`<Mirror>` element, two-pass): after first pass, iterate all `<Mirror>` elements in the XML; resolve `<ps>`/`<ss>` to origin abbreviation from first-pass result; write `abbr*` to mirror pages; warn if origin slot unresolved
  - [x] T-024 Wire sha1_index_path through: `build.py` loads SHA1 index if `systemroms/machines/all_sha1s.txt` exists, passes to `fetch_all()`; `parse_machine_xml()` and `extract_slotmap()` accept sha1_index param
  - [x] T-025 Tests: method 1 (rom_visibility narrower than mem → pages outside = abbr*)
  - [x] T-026 Tests: method 2 (NMS 8255-like — 16KB file mapped to 64KB → pages 1-3 = SUB*); SHA1 not found → warn, skip; file absent → warn, skip
  - [x] T-027 Tests: method 3 (Mirror element — page 3 in slot 0 mirrors RAM from slot 3 → RAM*); missing origin → warn, skip

- [x] Quality gate
  - [x] T-900 Run formatters (N/A — no formatter configured)
  - [x] T-901 Run linters (N/A — no linter configured)
  - [x] T-902 Run tests (`python -m pytest tests/scraper/ -v`) — 228 passed

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits (one per chunk)
  - [ ] T-951 Ensure all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)

## Open Questions
- None

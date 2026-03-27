# Plan: Data Schema + Seed Data

## Metadata
- Date: 2026-03-27
- Backlog item: Data schema + seed data
- Feature slug: data-schema-seed

## Context
- Intended outcome: TypeScript types for the data model are defined and exported; a hand-curated `public/data.js` file with 10 representative MSX2/MSX2+/turboR models is committed and loadable by the web page; column IDs are permanently assigned in `data/id-registry.json`; the schema is documented in `data/schema.md`. All subsequent features (grid rendering, URL codec, filtering) can build against concrete types and real data.

## Functional Snapshot
- Problem: The web page has no data and no types. No grid feature can be built or tested until the data shape is defined and sample data exists.
- Target user: bengalack (developer building the grid UI); MSX enthusiasts as the eventual page visitors
- Success criteria (observable):
  - `npm run typecheck` exits 0 with all types and the seed data declaration in place
  - Opening `docs/index.html` via `file://` in a browser shows no console errors; `window.MSX_DATA` is defined and has exactly 10 models
  - `window.MSX_DATA.columns` has 29 entries, each with a unique `id` integer
  - `window.MSX_DATA.groups` has exactly 8 entries (Identity through Emulation)
  - `data/id-registry.json` exists and contains the pre-assigned column IDs matching `window.MSX_DATA.columns`
  - `data/schema.md` documents every field in the schema including the stable ID contract
- Primary user flow:
  1. Developer writes a grid renderer that imports types from `src/types.ts`
  2. Page loads `public/data.js` (via `<script>` tag before `bundle.js`) — sets `window.MSX_DATA`
  3. App reads `window.MSX_DATA`, iterates `groups`, `columns`, `models`
  4. Grid renders 10 rows — one per model
- Must never happen:
  - Two columns assigned the same `id`
  - Two models assigned the same `id`
  - `data.js` loaded via `fetch()` (blocked on `file://`)
  - Column IDs changed after initial assignment (schema version bump required for any change)
- Key edge cases:
  - A model has `null` for some field values (not all specs are known) → `values[]` entry is `null`; no error
  - `docs/data.js` is missing when page is opened as `file://` → app logs a clear error; does not crash silently
- Business rules:
  - Column IDs are stable integers assigned once and never reassigned or reused
  - Model IDs are stable integers assigned once; `id-registry.json` is the source of truth
  - `values[]` array in each `ModelRecord` is positionally aligned with `MSXData.columns[]`
  - All CSS uses `var(--...)` tokens; no hardcoded hex in component styles (not directly relevant here — noted for grid work)
  - `docs/data.js` is NOT built by Vite; it lives in `public/` (Vite copies it to `docs/` on build); the scraper later overwrites `docs/data.js`
- Integrations: none (seed data is hand-curated; no external calls)
- Non-functional requirements:
  - Privacy/Security: no PII; data is public hardware specs
  - Performance: N/A for scaffold data
  - Reliability: `npm run typecheck` and `npm run build` must pass after each chunk
- Minimal viable increment (MVI): TypeScript types + `data/schema.md` + `public/data.js` with 10 models + `data/id-registry.json` pre-seeded with column IDs
- Deferred:
  - Full model dataset (scraper provides this later)
  - ID registry Python module (match-before-create logic is a Later backlog item)
  - `defaultView` field in MSXData (low priority; defined as optional for now)
  - scraper-generated `docs/data.js` (scraper is a Later item)

## Executable Specification (Gherkin)

```gherkin
Feature: Data schema and seed data
  The web page has a well-typed data contract and a hand-curated seed dataset
  that allows grid development to proceed against real MSX model data.

  Scenario: Page loads seed data without errors
    Given docs/index.html has been built with npm run build
    And public/data.js contains the 10-model seed dataset
    When the developer opens docs/index.html via the file:// protocol
    Then window.MSX_DATA is defined
    And window.MSX_DATA.models has exactly 10 entries
    And window.MSX_DATA.columns has exactly 29 entries
    And window.MSX_DATA.groups has exactly 8 entries
    And no JavaScript errors appear in the browser console

  Scenario: TypeScript types enforce the schema contract at compile time
    Given src/types.ts defines MSXData, ColumnDef, GroupDef, and ModelRecord
    And public/data.js declares window.MSX_DATA with the correct structure
    When the developer runs npm run typecheck
    Then the command exits with code 0 and reports zero type errors

  Scenario: Model with unknown field values is valid
    Given a ModelRecord where some entries in values[] are null
    When the TypeScript compiler checks the type
    Then the type is accepted without error (null is a valid value type)

  Scenario: Duplicate column IDs must never exist
    Given data/id-registry.json contains pre-assigned column IDs
    When the developer inspects window.MSX_DATA.columns
    Then every column has a unique integer id
    And every column id matches its entry in data/id-registry.json

  Scenario: Duplicate model IDs must never exist
    Given public/data.js contains 10 seed models
    When the developer inspects window.MSX_DATA.models
    Then every model has a unique integer id
    And no two models share the same id value

  Scenario: Missing data.js does not crash silently
    Given docs/index.html is opened via file:// without data.js present
    When the page loads
    Then a clear error message is visible (or logged to console)
    And no uncaught TypeError is thrown by the application code
```

## Baseline Gate
- Start from clean, green trunk (currently at scaffold commits — trivially green).
- All npm commands exit 0 before branching.

## Architecture Fit
- Touch points:
  - `src/types.ts` — new file; imported by all future grid modules
  - `public/data.js` — new file in `public/`; Vite copies to `docs/` on build
  - `index.html` — add `<script src="/data.js">` before the app module script
  - `src/main.ts` — add `window.MSX_DATA` type declaration + minimal validation
  - `data/id-registry.json` — new committed file; column IDs pre-seeded
  - `data/schema.md` — new documentation file
- Compatibility notes:
  - `public/data.js` is in Vite's public directory → copied verbatim to `docs/` on every build (not processed by TypeScript or bundler)
  - The scraper (Later) will overwrite `docs/data.js` after a build; re-running `npm run build` will restore the seed version from `public/data.js`
  - `window.MSX_DATA` type must be declared globally in TypeScript (`declare global { interface Window { MSX_DATA: MSXData; } }`) to avoid TS errors

## Observability (Minimum Viable)
- Applicability: Minimal — data loading only
- Failure modes:
  - `data.js` missing → `window.MSX_DATA` is undefined; app must check and log `[ERROR] MSX_DATA not found — is data.js loaded?`
  - Malformed `data.js` (syntax error) → browser console shows parse error; app must not silently swallow it
- Logs: `console.error('[MSX Models DB] MSX_DATA not found. Is data.js loaded before bundle.js?')` if `window.MSX_DATA` is undefined at app init

## Testing Strategy (Tier 0/1/2)
- Tier 0: `npm run typecheck` validates the full type contract at build time; this is the primary correctness check for the schema
- Tier 1: N/A (no runtime integration — data is static)
- Tier 2: N/A
- Note: The URL codec tests (a later backlog item) will rely on the types defined here; no separate test files are needed for this feature beyond typecheck

## Data and Migrations
- Applicability: Schema only
- Up migration: initial schema at version 1; `MSXData.version = 1`
- Down migration: N/A — no prior version
- Backfill plan: N/A — hand-curated seed data is the initial state
- Rollback considerations: If the schema changes in a future feature, bump `MSXData.version`; the URL codec checks the version byte on decode

## Rollout and Verify
- Applicability: N/A — local development only; no deployment in this step
- Note: `docs/data.js` (the seed copy in docs/) should be committed after `npm run build` so GitHub Pages serves the seed data immediately

## Cleanup Before Merge
- Remove any debug `console.log` statements added during development
- Ensure `public/data.js` uses consistent null (not `undefined`) for unknown values
- All commits follow Conventional Commits (`feat:` prefix)

## Definition of Done
- `npm run typecheck` exits 0
- `npm run build` exits 0; `docs/` contains `data.js` (copied from `public/`)
- Opening `docs/index.html` via `file://` shows no console errors; `window.MSX_DATA` has 10 models
- `data/id-registry.json` exists and all 29 column IDs match `window.MSX_DATA.columns`
- `data/schema.md` documents every field

## Column Schema (canonical, established here)

### Groups (IDs 0–7, fixed)
| id | key | label |
|---|---|---|
| 0 | identity | Identity |
| 1 | memory | Memory |
| 2 | video | Video |
| 3 | audio | Audio |
| 4 | media | Media |
| 5 | cpu | CPU/Chipsets |
| 6 | other | Other |
| 7 | emulation | Emulation |

### Columns (IDs 1–29, permanent)
| id | key | label | groupId | type |
|---|---|---|---|---|
| 1 | manufacturer | Manufacturer | 0 | string |
| 2 | model | Model | 0 | string |
| 3 | year | Year | 0 | number |
| 4 | region | Region/Market | 0 | string |
| 5 | standard | MSX Standard | 0 | string |
| 6 | form_factor | Form Factor | 0 | string |
| 7 | main_ram_kb | Main RAM (KB) | 1 | number |
| 8 | vram_kb | VRAM (KB) | 1 | number |
| 9 | rom_kb | ROM/BIOS (KB) | 1 | number |
| 10 | mapper | Mapper | 1 | string |
| 11 | vdp | VDP | 2 | string |
| 12 | max_resolution | Max Resolution | 2 | string |
| 13 | max_colors | Max Colors | 2 | number |
| 14 | max_sprites | Max Sprites | 2 | number |
| 15 | psg | PSG | 3 | string |
| 16 | fm_chip | FM Chip | 3 | string |
| 17 | audio_channels | Audio Channels | 3 | number |
| 18 | floppy_drives | Floppy Drive(s) | 4 | string |
| 19 | cartridge_slots | Cartridge Slots | 4 | number |
| 20 | tape_interface | Tape Interface | 4 | string |
| 21 | other_storage | Other Storage | 4 | string |
| 22 | cpu | CPU | 5 | string |
| 23 | cpu_speed_mhz | CPU Speed (MHz) | 5 | number |
| 24 | sub_cpu | Sub-CPU | 5 | string |
| 25 | keyboard_layout | Keyboard Layout | 6 | string |
| 26 | built_in_software | Built-in Software | 6 | string |
| 27 | connectivity | Connectivity/Ports | 6 | string |
| 28 | openmsx_id | openMSX Machine ID | 7 | string |
| 29 | fpga_support | FPGA/MiSTer Support | 7 | string |

## Seed Models (IDs 1–10)
| id | Manufacturer | Model | Year | Region | Standard |
|---|---|---|---|---|---|
| 1 | Sony | HB-75P | 1985 | Europe | MSX2 |
| 2 | Philips | VG-8235/00 | 1985 | Netherlands | MSX2 |
| 3 | Panasonic | FS-A1 | 1986 | Japan | MSX2 |
| 4 | Panasonic | FS-A1F | 1987 | Japan | MSX2 |
| 5 | Toshiba | HX-33 | 1986 | Japan | MSX2 |
| 6 | Sony | HB-F1XDJ | 1988 | Japan | MSX2+ |
| 7 | Panasonic | FS-A1WX | 1988 | Japan | MSX2+ |
| 8 | Panasonic | FS-A1WSX | 1989 | Japan | MSX2+ |
| 9 | Panasonic | FS-A1ST | 1990 | Japan | turboR |
| 10 | Panasonic | FS-A1GT | 1991 | Japan | turboR |

## Chunks

- Chunk 1: TypeScript types + schema documentation
  - User value: All future grid modules can import concrete types; schema contract is documented
  - Scope: `src/types.ts` (MSXData, ColumnDef, GroupDef, ModelRecord, IDRegistry), `data/schema.md`
  - Ship criteria: `npm run typecheck` exits 0; schema doc covers all fields
  - Rollout notes: none

- Chunk 2: Column definitions + initial ID registry
  - User value: Column IDs are permanently assigned; id-registry.json is the canonical reference
  - Scope: `src/columns.ts` (group and column constant arrays typed against ColumnDef/GroupDef), `data/id-registry.json` (pre-seeded with all 29 column IDs)
  - Ship criteria: `npm run typecheck` exits 0; id-registry.json columns map has 29 entries matching the column schema table above
  - Rollout notes: none

- Chunk 3: Seed data.js + index.html wiring
  - User value: Opening `docs/index.html` shows `window.MSX_DATA` with 10 real MSX models; grid development can start
  - Scope: `public/data.js` (window.MSX_DATA seed), `index.html` (`<script src="/data.js">` before app script), `src/main.ts` (read MSX_DATA, guard against missing, log count), global type declaration for `window.MSX_DATA`
  - Ship criteria: `npm run build` exits 0; `docs/data.js` exists; opening `docs/index.html` via `file://` shows no errors; `window.MSX_DATA.models.length === 10`
  - Rollout notes: none

- Chunk 4: Commit docs/ with seed data
  - User value: GitHub Pages serves the seed data immediately after push
  - Scope: run `npm run build`, commit updated `docs/`
  - Ship criteria: `docs/data.js` committed; `docs/index.html` references `data.js` before `bundle.js`
  - Rollout notes: GitHub Pages auto-serves from `docs/` on main branch

## Relevant Files (Expected)
- `src/types.ts` — MSXData, ColumnDef, GroupDef, ModelRecord, IDRegistry TypeScript interfaces + window declaration
- `src/columns.ts` — typed constant arrays for all 8 groups and 29 columns; used at runtime by the grid
- `data/schema.md` — human-readable schema documentation; stable ID contract
- `data/id-registry.json` — initial registry with 29 column IDs pre-assigned; model section starts empty (seed models use hand-assigned IDs not in the registry yet)
- `public/data.js` — seed `window.MSX_DATA` with 10 models; lives in Vite's public dir
- `index.html` — add `<script src="/data.js">` before `<script type="module" src="/src/main.ts">`
- `src/main.ts` — add guard: if `!window.MSX_DATA` log error; else log model count

## Assumptions
- The column list (29 columns, 8 groups) is the canonical schema for this iteration; future columns get new IDs appended
- Seed model data is approximate (sourced from memory); the scraper will provide accurate data later
- `public/data.js` is the authoritative seed; `docs/data.js` is its build-time copy (overwritten by scraper after a run)

## Validation Script (Draft)
1. Run `npm run typecheck` — exits 0
2. Run `npm run build` — exits 0; `docs/data.js` exists
3. Open `docs/index.html` via `file://` in Chrome — no console errors; open DevTools console and confirm `window.MSX_DATA.models.length === 10`
4. Confirm `window.MSX_DATA.columns.length === 29`
5. Confirm `window.MSX_DATA.groups.length === 8`
6. Inspect `data/id-registry.json` — `columns` map has 29 entries; `next_column_id === 30`
7. Run `npm run lint` — exits 0

## Tasks
- [x] T-001 Create and checkout a local branch `feature/data-schema-seed`

- [x] Chunk 1: TypeScript types + schema documentation
  - [x] T-010 Create `src/types.ts`: define and export `ColumnDef`, `GroupDef`, `ModelRecord`, `MSXData`, `IDRegistry` interfaces; add `declare global { interface Window { MSX_DATA: MSXData } }`
  - [x] T-011 Create `data/schema.md`: document MSXData structure, all fields, stable ID contract, values[] alignment rule, null semantics, versioning
  - [x] T-012 Verify `npm run typecheck` exits 0
  - [x] T-013 Commit: `feat: define MSXData TypeScript types and schema documentation`

- [x] Chunk 2: Column definitions + initial ID registry
  - [x] T-020 Create `src/columns.ts`: export `GROUPS` (GroupDef[]) and `COLUMNS` (ColumnDef[]) constants with all 8 groups and 29 columns using IDs from the schema table above
  - [x] T-021 Create `data/id-registry.json`: initial registry with `version: 1`, `columns` map (key → id for all 29 columns), `next_column_id: 30`, `models: {}`, `retired_models: []`, `next_model_id: 11` (seed models 1–10 are pre-registered)
  - [x] T-022 Verify `npm run typecheck` exits 0
  - [x] T-023 Commit: `feat: add column definitions with stable IDs and seed id-registry`

- [ ] Chunk 3: Seed data.js + index.html wiring
  - [ ] T-030 Create `public/data.js`: assign `window.MSX_DATA` with `version: 1`, `generated: "2026-03-27"`, `groups` array (8 entries), `columns` array (29 entries), `models` array (10 entries with values[] aligned to columns)
  - [ ] T-031 Update `index.html`: add `<script src="/data.js"></script>` immediately before `<script type="module" src="/src/main.ts">`
  - [ ] T-032 Update `src/main.ts`: guard `window.MSX_DATA` at startup — if undefined, log error and return; if defined, log `[MSX Models DB] Loaded N models` to console
  - [ ] T-033 Verify `npm run typecheck` and `npm run lint` exit 0
  - [ ] T-034 Verify `npm run build` exits 0; confirm `docs/data.js` exists with 10 models
  - [ ] T-035 Commit: `feat: add seed data with 10 MSX models`

- [ ] Chunk 4: Commit docs/ with seed data
  - [ ] T-040 Run `npm run build` to ensure latest `docs/` reflects the seed data
  - [ ] T-041 Commit: `chore: update docs/ build output with seed data`

- [ ] Quality gate
  - [ ] T-900 Run `npm run lint` — confirm 0 errors
  - [ ] T-901 Run `npm run typecheck` — confirm 0 errors
  - [ ] T-902 Run `npm test -- --run` — confirm exits 0
  - [ ] T-903 Run `npm run build` — confirm `docs/data.js` exists and has 10 models

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Confirm all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge fast-forward only

## Open Questions
- None

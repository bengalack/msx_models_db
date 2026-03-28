# Plan: URL State Codec + Sync

## Metadata
- Date: 2026-03-28
- Backlog item: URL state codec + sync / Unit tests (web)
- Feature slug: url-state-codec

## Context
- Intended outcome: Every view configuration (sort, filters, hidden columns/rows, collapsed groups, selected cells) is encoded into the URL hash automatically. Users can bookmark, share, or copy the URL and any recipient opening it sees exactly the same view. Unit tests provide a regression harness for the codec logic.

## Functional Snapshot
- Problem: All view state is ephemeral in-memory. Refreshing the page or sharing a URL loses every filter, sort, hidden column, and selection the user set up. There is no way to share or bookmark a specific view.
- Target user: Any visitor who wants to share a filtered/sorted view, or restore their last working configuration after a page reload
- Success criteria (observable):
  - After any state change (sort, filter, hide, collapse, select), the URL hash updates after a short debounce (~300 ms idle)
  - Copying the URL and opening it in a new tab/window restores the identical view
  - Refreshing the page restores the view exactly
  - If the URL hash is absent or unreadable, the page loads with default (show-all) state — no error shown
  - Unknown column/model IDs in the hash (retired data) are silently ignored; the rest of the state is still applied
  - `npm test --run`, `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
- Primary user flow:
  1. User configures a view (sort by year, filter by "turboR", hide audio columns)
  2. URL hash updates after each interaction (within ~300 ms)
  3. User copies URL and sends it to a colleague
  4. Colleague opens the link and sees the identical view
- Must never happen:
  - A corrupt or tampered hash causes a JavaScript error or blank page
  - The page loads slower because of URL decode work on startup
  - Any state change fails to eventually update the URL (within the debounce window)
  - `history.replaceState` is called more than once per 300 ms during rapid interactions (filter typing, cell drag-select)
  - localStorage or any persistent storage is used for view state (theme stays in localStorage, view state goes in URL only)
- Key edge cases:
  - Empty/absent hash → load default (show-all) state, no hash written until first interaction
  - Unknown codec version byte → fall back to empty state, `console.warn`
  - Unknown column/model IDs → silently drop those specific entries, restore rest of state
  - Filter active in restored state → filter bar is made visible automatically
  - `history.replaceState` unavailable (sandboxed embed) → catch silently, state still applied in-memory
  - Encoding throws → `console.warn`, URL stays stale, view still correct visually
- Business rules:
  - Codec version byte is `0x01`; unknown versions fall back to empty state
  - All IDs in the encoded payload are stable integer IDs (column IDs, model IDs, group IDs) — never positional indices
  - URL hash format: `#` + URL-safe base64 string (replace `+`→`-`, `/`→`_`, strip `=` padding)
  - history.replaceState is used (not pushState) — no back-button history entries created
  - View state is never written to localStorage; only theme uses localStorage
- Non-functional requirements:
  - Performance: decode on load is synchronous and must complete before first render; codec operates on small byte arrays (< 500 bytes typical) so encode/decode cost is negligible; URL writes are debounced (300 ms idle) to avoid churning `history.replaceState` during rapid interactions (filter typing at 10–20 Hz, cell drag-select at 30–60 Hz)
  - Reliability: decoder never throws; all error paths are caught and fall back to empty state
- Minimal viable increment (MVI): codec + grid state extraction + sync wired in main.ts + codec unit tests
- Deferred:
  - "Share this view" copy-URL button (currently in Inbox — the URL is already shareable; a dedicated button is UX polish)
  - `defaultView` config from MSXData (separate backlog item)

## Executable Specification (Gherkin)

```gherkin
Feature: URL state codec and sync
  The page encodes the full view configuration into the URL hash after every
  state change. Opening or reloading a URL with a hash restores the view exactly.

  Scenario: URL hash updates after a sort interaction (debounced)
    Given the page is loaded with no URL hash
    When the user clicks a column header to sort ascending
    And 300 ms pass without further interaction
    Then the URL hash is non-empty
    And reloading the page restores the same sort column and direction

  Scenario: Rapid filter typing produces only one URL update
    Given the page is loaded with no URL hash
    When the user types "turboR" quickly into a filter input (6 keystrokes in under 300 ms)
    Then the URL hash updates only once after the last keystroke + 300 ms idle
    And the hash encodes the full filter string "turboR"

  Scenario: Full view state round-trips across a page reload
    Given the user has sorted by year descending
    And hidden the Audio and Emulation column groups
    And applied a filter "turboR" on the MSX Standard column
    And collapsed the Memory group
    When the user copies the URL and opens it in a new tab
    Then the new tab shows year sorted descending
    And the Audio and Emulation groups are hidden
    And the filter row is visible with "turboR" in the MSX Standard input
    And the Memory group is collapsed

  Scenario: Corrupt hash does not crash the page
    Given the URL contains a hash of "###not_valid_base64###"
    When the page loads
    Then the page renders in default show-all state
    And no JavaScript error is thrown
    And a console.warn is emitted describing the decode failure

  Scenario: Unknown codec version falls back to default state
    Given the URL hash encodes a payload whose version byte is 0xFF
    When the page loads
    Then the page renders in default show-all state
    And a console.warn is emitted indicating the unknown version

  Scenario: Unknown column and model IDs are silently dropped
    Given the URL hash encodes state referencing column ID 999 and model ID 9999
    And neither ID exists in the current dataset
    When the page loads
    Then the page renders successfully
    And the unknown IDs are silently ignored
    And any valid IDs in the same hash are correctly applied

  Scenario: Empty hash loads default state without error
    Given the URL has no hash fragment
    When the page loads
    Then the page renders in default show-all state
    And no console.warn is emitted

  Scenario: Codec round-trip preserves all state dimensions
    Given a ViewState with sort, filters, hidden columns, hidden rows,
          collapsed groups, and selected cells all populated
    When the state is encoded to a base64 hash and decoded back
    Then the decoded ViewState is structurally equal to the original
    And no data is lost or corrupted
```

## Baseline Gate
- Start from clean, green trunk (`main`). All npm commands exit 0 before branching.

## Architecture Fit
- Touch points:
  - `src/types.ts` — add `ViewState` interface
  - `src/url/codec.ts` — new; `encodeViewState`, `decodeViewState`, `encodeToHash`, `decodeFromHash`
  - `src/grid.ts` — add `getViewState()` to return; accept `opts?: { initialState?: ViewState; onStateChange?: () => void }`; call `onStateChange` after every mutation; seed state from `initialState` before first render
  - `src/main.ts` — decode hash on load → pass `initialState` to `buildGrid`; pass `onStateChange` callback that encodes + calls `history.replaceState`; show filter bar if initial state has filters
  - `tests/web/codec.test.ts` — new; Vitest tests (no DOM needed — codec is pure)
  - `tsconfig.json` — extend `include` to cover `tests/**/*`
  - `eslint.config.js` — extend files glob to include `tests/**/*.ts`
- Compatibility notes:
  - `buildGrid` signature gains an optional second parameter; all existing call sites pass no second argument and remain valid
  - The grid's internal state uses column indices (0-based) and model IDs; `getViewState()` translates to ID-based ViewState for the codec; `initialState` application translates back to indices
  - `selectedCells` key format is currently `"${modelId}:${colIdx}"` (index); `getViewState` maps colIdx → colId for the codec payload

## Binary Format
```
Byte 0:     version (0x01)
Byte 1:     flags (reserved, 0x00)
Bytes 2–3:  sort_column_id (uint16; 0x0000 = no sort)
Byte 4:     sort_direction (0x00 = asc, 0x01 = desc)
Bytes 5–8:  collapsed_groups bitmask (uint32; bit N = group ID N collapsed)
Bytes 9–10: hidden_columns bitset byte length L1 (uint16)
Bytes …:    hidden_columns bitset (L1 bytes; bit N = column ID N hidden)
Bytes …:    hidden_rows bitset byte length L2 (uint16)
Bytes …:    hidden_rows bitset (L2 bytes; bit N = model ID N hidden)
Bytes …:    filter_count (uint16)
  Per filter:
    column_id (uint16)
    string_byte_length (uint16)
    UTF-8 bytes
Bytes …:    selection_count (uint16)
  Per selected cell:
    model_id (uint16)
    column_id (uint16)
```
Base64 encoding: replace `+`→`-`, `/`→`_`, strip `=`; reverse on decode.
All multi-byte integers are big-endian (DataView default).

## Observability (Minimum Viable)
- Applicability: Minimal (static SPA; no server, no metrics pipeline)
- Failure modes:
  - Corrupt/truncated hash → decoder catches, falls back to empty state; `console.warn` with hash length and error message
  - Unknown version byte → decoder detects, falls back to empty state; `console.warn` with received vs expected version
  - `encodeViewState` throws during a state change → `console.warn` with error + interaction context; URL goes stale but view is still correct visually
  - `history.replaceState` unavailable → catch silently; URL stays stale; view is still correct
- Logs:
  - `[url-codec] decode failed` — warn — fields: `error`, `hashLength`, `versionByte`
  - `[url-codec] unknown version` — warn — fields: `received`, `expected`
  - `[url-codec] encode failed` — warn — fields: `error`

## Testing Strategy (Tier 0/1/2)
- Tier 0: `npm run typecheck` (extend tsconfig include to cover tests/); `npm run lint` (extend ESLint files glob to tests/)
- Tier 1: `tests/web/codec.test.ts` — Vitest, no jsdom needed (codec is pure). Key cases:
  - Round-trip: empty state, sort asc/desc, no-sort sentinel (null ↔ 0), collapsed groups bitmask, hidden cols bitset (sparse + dense), hidden rows bitset, single filter, multiple filters, UTF-8 multibyte filter, selected cells, kitchen-sink all-fields
  - Boundary: uint16 max column ID, bit 0 (ID 0) in bitset, empty selection_count section, empty filter string handling
  - Version/compat: version byte is 0x01, unknown version → empty state no throw, flags byte is 0x00
  - Resilience: truncated buffer, empty buffer, unknown col IDs in bitset dropped, unknown model IDs dropped, unknown filter col IDs dropped, unknown selection IDs dropped, corrupted base64, valid base64 with garbage bytes
  - URL layer: `encodeToHash` returns string starting with `#`, `decodeFromHash('')` → empty state, `decodeFromHash('#')` → empty state
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — ViewState is ephemeral; no persistent store is changed

## Rollout and Verify
- Applicability: N/A (static commit-to-deploy; no staged rollout needed)
- Verification (manual smoke path after build):
  1. Open `docs/index.html` via `file://` — URL hash is absent, default state loads
  2. Click a column header to sort — URL hash appears immediately
  3. Add a filter, hide a column — hash updates after each action
  4. Copy URL, open in new tab — identical view (sort + filter + hidden col restored; filter bar visible)
  5. Corrupt the hash in the address bar, reload — default state, no error dialog; DevTools shows `console.warn`
  6. `npm test --run` — all codec tests green

## Cleanup Before Merge
- No debug `console.log` (only `console.warn` in the 3 specified error paths)
- All commits follow Conventional Commits (`feat:` or `test:` prefix)

## Definition of Done
- Gherkin specification is complete and current in the plan artifact
- All codec tests green (`npm test --run` exits 0)
- `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
- Manual smoke test passes (sort → URL hash → reload → state restored)
- Backlog updated

## Chunks

- Chunk 1: ViewState type + codec + tests
  - User value: The codec logic is proven correct and locked down before any wiring. Developers can import and use the codec from day one.
  - Scope: `src/types.ts` (ViewState interface), `src/url/codec.ts` (encode/decode), `tests/web/codec.test.ts`, extend `tsconfig.json` + `eslint.config.js`
  - Ship criteria: `npm test --run` exits 0 with all codec tests green; `npm run typecheck` and `npm run lint` exit 0
  - Rollout notes: none

- Chunk 2: Grid exposes state + accepts initial state + fires onStateChange
  - User value: The grid is now a stateful component that can be initialised from a saved view and notifies callers of every change — the prerequisite for URL sync.
  - Scope: `src/grid.ts` — add `getViewState()` to return value; add `opts?: { initialState?: ViewState; onStateChange?: () => void }` parameter; seed all internal state sets/maps from `initialState` before first render; call `opts.onStateChange?.()` after every mutation (sort, filter, hide col, hide row, collapse group, select)
  - Ship criteria: `npm run typecheck` exits 0; existing build and tests still green
  - Rollout notes: none

- Chunk 3: Wire URL sync in main.ts + update docs/
  - User value: The feature is complete end-to-end — every view change updates the URL; opening a URL with a hash restores the view.
  - Scope: `src/main.ts` — decode `window.location.hash` on load; pass `initialState` and `onStateChange` (encode → `history.replaceState`) to `buildGrid`; call `toggleFilters()` if initial state has active filters; `docs/` rebuilt and committed
  - Ship criteria: `npm run build` exits 0; manual smoke path passes (copy URL → new tab → identical view)
  - Rollout notes: none

## Relevant Files (Expected)
- `src/types.ts` — add `ViewState` interface
- `src/url/codec.ts` — new; binary encode/decode + base64 helpers
- `src/grid.ts` — add `getViewState()`, `opts` parameter, `onStateChange` calls, `initialState` seeding
- `src/main.ts` — wire decode on load, encode on change, filter bar show/hide
- `tests/web/codec.test.ts` — new; ~25 Vitest test cases (pure, no DOM)
- `tsconfig.json` — extend `include` to `["src/**/*", "tests/**/*", "vite.config.ts"]`
- `eslint.config.js` — extend files glob to include `tests/**/*.ts`
- `docs/` — rebuilt in Chunk 3

## Assumptions
- `history.replaceState` is available in all supported environments (file://, GitHub Pages); unavailability is caught silently
- The filter row visibility is managed by main.ts — if `initialState.filters.size > 0`, main.ts calls `toggleFilters()` after `buildGrid` returns and syncs its own `filtersOn` boolean
- Bitset length for hidden_columns is `Math.ceil((maxId + 1) / 8)` where `maxId` is the maximum set ID; empty set encodes as length 0 with no bytes
- `selectedCells` decode order matches encode order (array, not set); no de-dup needed since the grid never allows duplicate selection entries

## Validation Script (Draft)
1. Run `npm test --run` — all tests green
2. Run `npm run typecheck` — exits 0
3. Run `npm run lint` — exits 0
4. Run `npm run build` — exits 0
5. Open `docs/index.html` via `file://` — no hash, default state
6. Click Year column header to sort — verify URL hash appears
7. Type "turboR" in MSX Standard filter — verify hash updates
8. Hide the Memory group via Columns panel — verify hash updates
9. Copy URL, open in new tab — verify: sort, filter, hidden group all restored; filter bar visible
10. Clear hash from URL bar, reload — verify: default state, no error
11. Append `#!!!bad!!!` to URL, reload — verify: default state, `console.warn` in DevTools

## Tasks
- [x] T-001 Create and checkout local branch `feature/url-state-codec`

- [x] Chunk 1: ViewState type + codec + tests
  - [x] T-010 Add `ViewState` interface to `src/types.ts` (sort, filters, hiddenColumns, hiddenRows, collapsedGroups, selectedCells — all ID-based)
  - [x] T-011 Create `src/url/codec.ts`: `encodeViewState(state, columns)` → base64 string; `decodeViewState(base64, data)` → ViewState (catch all errors, return empty state); `encodeToHash` / `decodeFromHash` thin wrappers
  - [x] T-012 Extend `tsconfig.json` include to `["src/**/*", "tests/**/*", "vite.config.ts"]`; extend `eslint.config.js` files glob to include `tests/**/*.ts`
  - [x] T-013 Create `tests/web/codec.test.ts` with round-trip, boundary, version/compat, resilience, and URL-layer test cases (covering all cases in Testing Strategy above)
  - [x] T-014 Verify `npm test --run` exits 0; `npm run typecheck` exits 0; `npm run lint` exits 0
  - [ ] T-015 Commit: `feat: add ViewState type and binary URL codec with unit tests`

- [ ] Chunk 2: Grid state extraction + initial state + onStateChange
  - [ ] T-020 Add `getViewState(): ViewState` to `buildGrid` return value (translates internal index-based state to ID-based ViewState using `data.columns`)
  - [ ] T-021 Add `opts?: { initialState?: ViewState; onStateChange?: () => void }` parameter to `buildGrid`; seed `collapsedGroups`, `hiddenCols`, `hiddenRows`, `filters`, `selectedCells`, `sortColIndex`, `sortDirection` from `initialState` before first `renderRows()` call (translate IDs → indices where needed; silently skip unknown IDs)
  - [ ] T-022 Call `opts.onStateChange?.()` after each of the 6 mutation points: sort change, filter change, column visibility change, row hide/unhide, group collapse/expand, cell selection change
  - [ ] T-023 Verify `npm run typecheck` exits 0 and `npm run build` exits 0; no existing tests broken
  - [ ] T-024 Commit: `feat: expose view state from grid and accept initial state + onChange callback`

- [ ] Chunk 3: Wire URL sync in main.ts + rebuild docs/
  - [ ] T-030 In `src/main.ts`: on load, call `decodeFromHash(window.location.hash)` → `initialState`; pass to `buildGrid`; if `initialState.filters.size > 0`, call `toggleFilters()` after grid build and set `filtersOn = true`
  - [ ] T-031 Pass `onStateChange` callback to `buildGrid` that **debounces** URL writes (300 ms idle timeout). The callback resets a `setTimeout`; when the timer fires, it calls `encodeToHash(grid.getViewState())` and updates URL via `history.replaceState(null, '', hash)` (wrapped in try/catch → `console.warn` on failure). Rationale: filter typing and cell drag-select fire at 10–60 Hz; the URL should reflect settled state, not every transient frame.
  - [ ] T-032 Verify full smoke path: sort → URL hash updates; copy URL → new tab → state restored; corrupt hash → default state; `npm run build` exits 0
  - [ ] T-033 Commit: `feat: wire URL hash sync — encode on change, restore on load`
  - [ ] T-034 Commit built `docs/`: `chore: update docs/ build output with URL state sync`

- [ ] Quality gate
  - [ ] T-900 Run `npm run lint` — confirm 0 errors
  - [ ] T-901 Run `npm run typecheck` — confirm 0 errors
  - [ ] T-902 Run `npm test --run` — confirm exits 0
  - [ ] T-903 Run `npm run build` — confirm exits 0

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Confirm all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge fast-forward only

## Open Questions
- None

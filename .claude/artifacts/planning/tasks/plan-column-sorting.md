# Plan: Column Sorting

## Metadata
- Date: 2026-03-27
- Backlog item: Column sorting
- Feature slug: column-sorting

## Context
- Intended outcome: Users can click any column header to sort all rows by that column, with a clear visual indicator of the active sort direction. Clicking again toggles direction; a third click clears the sort.

## Functional Snapshot
- Problem: With 10+ models across 29 columns of mixed types (string, number, boolean), it is impossible to compare values without scrolling row by row. Sorting by any column instantly surfaces the best/worst/most contiguous values.
- Target user: Researcher comparing MSX model specs, wanting to rank models by e.g. RAM, clock speed, or manufacturer name.
- Success criteria (observable):
  - Clicking a col-header sorts all data rows by that column ascending; ↑ appears in the header
  - Clicking the same col-header again sorts descending; ↓ appears; ↑ removed
  - Clicking the same col-header a third time clears the sort; rows restore to original order; indicator removed
  - Clicking a different col-header while one is active clears the previous indicator and starts fresh on the new column
  - Gutter row-numbers update to reflect the new visual order (1-based sequence of visible rows)
  - Sort works correctly for all three column types: string (locale-aware), number, boolean
  - null / unknown values always sort last regardless of direction
- Primary user flow:
  1. User sees grid in default (original data) order
  2. User clicks a col-header (e.g. "RAM") → rows re-order ascending; "RAM" header shows ↑
  3. User clicks "RAM" again → rows re-order descending; header shows ↓
  4. User clicks "RAM" a third time → rows restore to original order; no indicator
  5. User clicks a different col-header → previous indicator cleared; new header shows ↑
- Alternate flows:
  - User clicks a col-header in a currently-collapsed group → sort still applies (collapsed groups are a display-only concern)
  - User collapses a group after sorting → sort state unaffected
- Must never happen:
  - Data misalignment: a row's gutter number must always correspond to the correct model after sort
  - Row data is permanently mutated — sort must be non-destructive (original `data.models` order preserved)
  - null values appearing before non-null values in either direction
- Key edge cases:
  - All values in a column are null → sort order is stable (original order) in both directions
  - Column with all identical values → stable sort preserves original relative order
  - Boolean column: false < true ascending; true < false descending; null last either way
  - Number column: numeric comparison, not lexicographic
  - String column with mixed case: locale-aware case-insensitive compare
- Business rules:
  - Single-column sort only (multi-column sort is deferred to a later backlog item)
  - Sort is applied to ALL models, not just visible ones (hidden rows are a later feature)
  - Sort state is NOT persisted to URL in this feature (deferred to URL state codec)
  - Gutter numbers represent the sorted position (1 = top visible row after sort)
- Integrations: None — pure client-side DOM re-render; no external data
- Non-functional requirements:
  - Privacy/Security: N/A
  - Performance: Re-render completes in one synchronous DOM batch; no perceived lag for the current seed size (10 models); acceptable up to ~500 models
  - Reliability: Sort survives group collapse/expand without corruption
- Minimal viable increment (MVI): Click to sort asc → desc → clear; ↑/↓ indicator; null-last; all three types; gutter renumbered
- Deferred:
  - Multi-column sort
  - URL state codec integration (sort state in hash)
  - Keyboard activation of sort (accessibility pass)

## Executable Specification (Gherkin)

Feature: Column sorting
  A user can click any column header to sort data rows by that column.
  Clicking once sorts ascending; again sorts descending; a third click clears the sort.

  Scenario: Sort a numeric column ascending then descending then clear
    Given the grid is rendered in default order
    When the user clicks a numeric column header (e.g. RAM)
    Then the rows are ordered by that column ascending
    And the column header displays ↑
    When the user clicks that column header again
    Then the rows are ordered descending
    And the column header displays ↓
    When the user clicks that column header a third time
    Then the rows are restored to original order
    And no sort indicator is shown

  Scenario: Switching sort column clears the previous indicator
    Given column A is sorted (showing ↑)
    When the user clicks a different column header B
    Then rows are sorted by column B ascending
    And column B shows ↑
    And column A shows no indicator

  Scenario: Null values always sort last
    Given a column where some models have null values
    When the user sorts that column ascending
    Then all non-null values appear before null values
    When the user sorts that column descending
    Then all non-null values still appear before null values

  Scenario: Sort does not corrupt row data alignment
    Given the grid is sorted by a column
    When the user reads any data cell in the sorted grid
    Then that cell contains the value belonging to its row's model

  Scenario: Sort is non-destructive across group collapse
    Given the grid is sorted by a column
    When the user collapses and then expands a group
    Then the sort order is unchanged

  Scenario: All-null column produces stable order
    Given a column where every model has a null value
    When the user clicks that column header to sort
    Then the row order is identical to the original order (stable)
    And the column header shows ↑

  Scenario: Sort is not persisted across page reload
    Given the user has sorted by a column
    When the user reloads the page
    Then all rows are shown in original order with no sort indicator

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points:
  - `src/grid.ts`: `buildColHeaderRow` adds `data-col-index` attribute; `buildGrid` adds sort state + click handler; replaces `tbody` rows on sort
  - `src/styles/grid.css`: `.col-header` gets `cursor: pointer`; `.col-header--sort-asc` / `.col-header--sort-desc` add indicator via `::after` pseudo-element
- Sort state: `{ colIndex: number | null, direction: 'asc' | 'desc' }` in `buildGrid` closure — not exported (URL codec lifts it later)
- Re-render strategy: on sort, clear `tbody` and re-append sorted rows (full tbody swap) — simple and correct for current data size
- Original order preserved: keep a `originalModels` const = `[...data.models]` before any sort mutation
- Compatibility: `data-col-group` and `data-col-order` attributes on data cells are rebuilt on each re-render; no stale state

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM interaction; no server, no async, no failure modes to instrument

## Testing Strategy (Tier 0/1/2)
- Tier 0: No unit tests in this feature — sort is pure DOM re-render; Vitest is not yet configured for DOM (jsdom not set up). Covered by manual smoke path.
- Tier 1: N/A
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — no schema changes; sort state is in-memory only

## Rollout and Verify
- Applicability: Required
- Strategy: All-at-once (static file)
- Verify (smoke path):
  1. Open `docs/index.html`
  2. Click a numeric col-header → rows sort ascending, ↑ shown
  3. Click same header → descending, ↓ shown
  4. Click same header again → original order, no indicator
  5. Click one col-header, then a different one → first indicator cleared, second shows ↑
  6. Sort by a column with some null values → nulls appear at bottom in both directions
  7. Collapse a group while sorted → sort unchanged after expand
  8. Reload page → original order, no indicator
- Signals to watch: gutter numbers renumber correctly; no data-cell misalignment; no JS error on rapid clicks

## Cleanup Before Merge
- Remove any debug console.log statements
- No feature flags, no temporary scaffolding
- Squash intermediate commits into logical commits
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge with fast-forward only

## Definition of Done
- [x] Gherkin specification is complete and current in the plan artifact
- [x] All smoke path steps pass
- [x] No hardcoded hex values added to CSS
- [x] Cleanup gate satisfied
- [x] Backlog updated (shipped item moved to "In product (shipped)")

## Chunks

### Chunk 1 — Sort logic + CSS (T-100 to T-107)
- User value: Users can click any column header to sort rows; indicator shows direction
- Scope:
  - `src/grid.ts`: `data-col-index` on col-header `<th>`; sort state in `buildGrid`; `sortModels()` helper; tbody re-render on click; gutter renumber
  - `src/styles/grid.css`: `cursor: pointer` on `.col-header`; `::after` indicators for sort-asc / sort-desc modifier classes
- Ship criteria: Click col-header → sorted rows + indicator; click again → reversed; third click → cleared; nulls always last

### Chunk 2 — Build output (T-200)
- User value: Built `docs/bundle.js` updated so the feature is live
- Scope: `npm run build` → commit `docs/bundle.js`
- Ship criteria: Build exits 0

## Tasks

### T-100 — Add data-col-index to col-header cells
- [x] In `buildColHeaderRow`, add `th.dataset.colIndex = String(index)` where `index` is the position in `columns[]` (use `columns.forEach` or indexed for-loop)

### T-101 — Add sortModels helper
- [x] Add a module-level `sortModels` function:
  ```ts
  function sortModels(
    models: ModelRecord[],
    colIndex: number,
    direction: 'asc' | 'desc'
  ): ModelRecord[] {
    return [...models].sort((a, b) => {
      const av = colIndex < a.values.length ? a.values[colIndex] : null;
      const bv = colIndex < b.values.length ? b.values[colIndex] : null;
      // null always last, regardless of direction
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      let cmp: number;
      if (typeof av === 'number' && typeof bv === 'number') {
        cmp = av - bv;
      } else if (typeof av === 'boolean' && typeof bv === 'boolean') {
        cmp = (av === bv ? 0 : av ? 1 : -1);
      } else {
        cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' });
      }
      return direction === 'asc' ? cmp : -cmp;
    });
  }
  ```

### T-102 — Add sort state to buildGrid + click handler on col-headers
- [x] In `buildGrid`, declare sort state:
  ```ts
  let sortColIndex: number | null = null;
  let sortDirection: 'asc' | 'desc' = 'asc';
  ```
- [x] Keep a reference to the original models order: `const originalModels = [...data.models];`
- [x] After building thead, query `thead.querySelectorAll<HTMLTableCellElement>('th.col-header')` and attach a click listener to each that:
  1. Reads `colIndex` from `th.dataset.colIndex`
  2. Determines next state: if `colIndex !== sortColIndex` → set asc; if same + asc → set desc; if same + desc → clear (null)
  3. Clears `col-header--sort-asc` / `col-header--sort-desc` from all col-header `<th>` elements
  4. If not clearing: sets the appropriate class on the clicked `th`
  5. Calls `renderRows()`

### T-103 — Add renderRows helper inside buildGrid
- [x] Extract tbody population into a `renderRows()` closure inside `buildGrid`
- [x] Replace the original `data.models.forEach(...)` call with `renderRows()`

### T-104 — Re-apply collapsed group display state after re-render
- [x] After `tbody.replaceChildren(...)` in `renderRows()`, iterate `collapsedGroups` and hide the appropriate cells in each new row
- [x] Ensure `renderRows` is defined after `collapsedGroups` is in scope (both in `buildGrid` closure)

### T-105 — CSS: col-header interactive + sort indicators
- [x] Add to `.col-header` in `src/styles/grid.css`: `cursor: pointer; user-select: none;`
- [x] Add hover rule
- [x] Add sort indicator rules for `::after`

### T-106 — Commit chunk 1
- [x] `npm run typecheck && npm run lint && npm run build` — must be green
- [x] `git add src/grid.ts src/styles/grid.css`
- [x] `git commit -m "feat: sort rows by column with ascending/descending/clear cycle"`

### T-200 — Build and commit docs/bundle.js
- [x] `git add docs/bundle.js && git commit -m "chore: update docs/ build output with column sorting"`

### T-950 — Smoke test
- [x] Run all 8 smoke path steps from Rollout and Verify

### T-951 — Squash, merge, clean up
- [x] Squash branch commits into one logical commit
- [x] Fast-forward merge to main
- [x] Delete feature branch

### T-952 — Update backlog
- [x] Move "Column sorting" to "In product (shipped)" in `product-backlog.md`

## Relevant Files (Expected)
- `src/grid.ts` — sort helper, sort state, click handlers, renderRows, tbody re-render
- `src/styles/grid.css` — cursor/hover on col-header; sort indicator ::after rules
- `docs/bundle.js` — built output; committed after build

## Notes
- `originalModels` must be a shallow copy (`[...data.models]`) taken once at grid construction — never reassigned
- `sortModels` returns a new array; the original is never mutated
- `renderRows` must re-apply collapsed group state after each re-render (T-104) — this is the integration point between sort and group collapse
- `tbody.replaceChildren()` is supported in all modern browsers and is the cleanest full-tbody swap API
- The `data-col-index` attribute carries the 0-based positional index into `columns[]` / `values[]` — this is what drives value lookup in `sortModels`

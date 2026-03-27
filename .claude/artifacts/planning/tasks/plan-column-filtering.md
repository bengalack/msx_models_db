# Plan: Column Filtering

## Metadata
- Date: 2026-03-27
- Backlog item: Column filtering
- Feature slug: column-filtering

## Context
- Intended outcome: Users can toggle a filter row via the toolbar, type into per-column text inputs, and see rows narrow down immediately. An active-filter indicator keeps the state visible, and a clear (×) button per input removes individual filters quickly.

## Functional Snapshot
- Problem: With many models and 29 columns, finding models that match a specific value (e.g. all models with "Panasonic" manufacturer, or "256" KB RAM) requires scanning every row manually. Per-column text filtering lets users narrow the grid to the relevant subset instantly.
- Target user: Researcher or enthusiast who knows a specific attribute value and wants to find all matching models.
- Success criteria (observable):
  - Toolbar "⌃ Filters" button toggles the filter row visible/hidden; re-clicking hides it and clears all filters
  - Typing in a filter input immediately hides non-matching rows (case-insensitive substring match on the displayed cell text)
  - Active filter input has an accent border; a clear (×) button appears and clears that input when clicked
  - A "⊘" gutter indicator appears in the col-header gutter corner when any rows are filtered out; disappears when all filters are empty
  - Filters compose: multiple active filters narrow rows to only those matching ALL filters simultaneously
  - Sort and filter compose: sorted order is preserved among filtered rows
  - Group collapse does not break filter inputs — hidden column filter cells are simply not visible
- Primary user flow:
  1. User clicks "⌃ Filters" in the toolbar → filter row appears below column headers
  2. User types "pan" in the Manufacturer input → only Panasonic rows remain visible
  3. Gutter indicator shows "⊘" in the col-header gutter corner
  4. User clicks × on the input → input cleared, all rows restored, gutter indicator disappears
  5. User clicks "⌃ Filters" again → filter row hides, any remaining filters cleared
- Alternate flows:
  - User sorts while filters are active → sorted order preserved among filtered rows
  - User collapses a group that has an active filter → filter stays active (cells hidden, filter still applied to data)
  - User types in a filter for a boolean column → typing "yes" shows only true rows; "no" shows only false rows; "—" shows only null rows
- Must never happen:
  - Row data misalignment after filter (gutter number must correspond to the correct model)
  - Filtered-out rows leaking into clipboard copy or URL state (those are later features, but filter state must be in `renderRows`)
  - Clearing filters via the × button causing a page scroll jump
- Key edge cases:
  - Filter term that matches no rows → grid body is empty; gutter indicator still shows "⊘"; no JS error
  - All filters cleared → all rows restored; gutter indicator removed
  - Filter on a collapsed group's column → column is hidden but filter still applies to data rows
  - Filter input in a collapsed group → input cell is hidden (`.col-group-stub` / `display:none`), but filter map entry is still honoured
  - Reopening filter row after hide → inputs are empty (cleared on hide)
- Business rules:
  - Match is case-insensitive substring of `cellText(value)` — the same text already shown in the cell
  - Null/empty values show "—" in cells; "—" is therefore the search text for null. A filter of "—" would match null cells.
  - Filters compose with AND semantics (all active filters must match for a row to be visible)
  - Filter state is NOT persisted to URL in this feature (deferred to URL state codec)
  - The filter row is hidden by default; opening it does not affect existing sort state
- Integrations: None — pure client-side DOM; no external data
- Non-functional requirements:
  - Privacy/Security: N/A
  - Performance: `input` event fires synchronously; re-render completes in one pass; acceptable for current data size and up to ~500 rows
  - Reliability: Filters survive sort changes without corruption; sort survives filter changes without corruption
- Minimal viable increment (MVI): Toggle shows/hides filter row; per-column text inputs filter rows on `input` event; active-filter accent border + × button; gutter indicator when rows are filtered; clear on hide
- Deferred:
  - URL state codec integration (filter state in hash)
  - Keyboard shortcut to open/close filter row
  - Filter row visibility animating open/closed
  - Dropdown/select filters for boolean columns (text match on "Yes"/"No" is sufficient for MVI)

## Executable Specification (Gherkin)

Feature: Column filtering
  A user can open a filter row from the toolbar and type into per-column inputs
  to narrow the visible rows immediately. Closing the filter row clears all filters.

  Scenario: Toggle filter row open and closed
    Given the grid is rendered with the filter row hidden
    When the user clicks the "⌃ Filters" toolbar button
    Then the filter row becomes visible below the column headers
    When the user clicks "⌃ Filters" again
    Then the filter row is hidden and all rows are shown

  Scenario: Filter rows by typing in a column input
    Given the filter row is visible
    When the user types "pan" in the Manufacturer filter input
    Then only rows whose Manufacturer cell contains "pan" (case-insensitive) are visible
    And the Manufacturer filter input has an accent border
    And a clear (×) button is visible on the Manufacturer input
    And a "⊘" gutter indicator appears in the col-header gutter corner

  Scenario: Clear a single filter with the × button
    Given a filter input contains "pan" and rows are filtered
    When the user clicks the × button on that input
    Then the input is cleared
    And all rows matching remaining filters (if any) are restored
    And if no other filters are active the gutter indicator disappears

  Scenario: Multiple filters compose with AND semantics
    Given the filter row is visible
    When the user types "panasonic" in Manufacturer and "256" in RAM
    Then only rows matching both terms simultaneously are shown

  Scenario: No rows match the filter
    Given the filter row is visible
    When the user types "zzznomatch" in any filter input
    Then the grid body is empty
    And the "⊘" gutter indicator is visible
    And no JavaScript error occurs

  Scenario: Hiding the filter row clears all filters
    Given a filter is active and rows are narrowed
    When the user clicks "⌃ Filters" to hide the filter row
    Then all rows are restored to the pre-filter state
    And filter inputs are empty when the row is next opened

  Scenario: Sort and filter compose correctly
    Given the grid is sorted by a column and the filter row is visible
    When the user types a filter term
    Then only matching rows are shown, in the current sort order

  Scenario: Filter does not corrupt row data alignment
    Given a filter is active and some rows are hidden
    When the user reads any visible data cell
    Then that cell contains the value belonging to its row's model

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points:
  - `src/toolbar.ts`: `buildToolbar` gains an `onFiltersToggle: () => void` callback parameter; the Filters button is enabled and wired to it
  - `src/grid.ts`: `buildGrid` return type changes to `{ element: HTMLElement; toggleFilters: () => void }`; `buildFilterRow` gains `<input>` + `<button class="filter-clear">` per cell; `filters: Map<number, string>` added to closure; `renderRows` extended to apply filter + sort; gutter indicator on col-header gutter updated
  - `src/main.ts`: destructures `{ element, toggleFilters }` from `buildGrid`; passes `toggleFilters` to `buildToolbar`
  - `src/styles/grid.css`: filter input + active state + clear button styles
- Compatibility:
  - `buildGrid` return type change requires updating `main.ts` — only one call site
  - `buildToolbar` signature change is backward-compatible if `onFiltersToggle` is typed non-optionally (one call site in `main.ts`)
  - `renderRows` already centralises row output — filter logic is additive

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM interaction

## Testing Strategy (Tier 0/1/2)
- Tier 0: No unit tests — DOM-only feature; Vitest jsdom not yet configured. Covered by manual smoke path.
- Tier 1: N/A
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — no schema changes; filter state is in-memory only

## Rollout and Verify
- Applicability: Required
- Strategy: All-at-once (static file)
- Verify (smoke path):
  1. Open `docs/index.html` — filter row is hidden; "⌃ Filters" button is enabled
  2. Click "⌃ Filters" → filter row appears
  3. Type a partial manufacturer name → only matching rows shown; accent border + × visible; "⊘" in gutter
  4. Click × → input cleared; rows restored; indicator gone
  5. Type a term in two columns simultaneously → AND filtering works
  6. Type "zzz" → empty grid, no error
  7. Click "⌃ Filters" again → filter row hidden; all rows restored
  8. Sort by a column, then open filters and type → filtered rows hold sorted order
  9. Collapse a group that has an active filter → filter stays active; collapsed cells hidden
- Signals to watch: no JS errors; gutter indicator appears/disappears correctly; inputs empty after close

## Cleanup Before Merge
- No debug console.log statements
- No feature flags, no temporary scaffolding
- Squash intermediate commits into logical commits
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge with fast-forward only

## Definition of Done
- [ ] Gherkin specification is complete and current in the plan artifact
- [ ] All smoke path steps pass
- [ ] No hardcoded hex values added to CSS
- [ ] Cleanup gate satisfied
- [ ] Backlog updated (shipped item moved to "In product (shipped)")

## Chunks

### Chunk 1 — Filter row DOM + CSS (T-100 to T-102)
- User value: Filter row contains inputs and × buttons; styled correctly
- Scope: `buildFilterRow` adds `<input>` + `<button class="filter-clear">`; CSS for `.filter-input`, `.filter-input--active`, `.filter-clear`, `.filter-clear--hidden`, gutter indicator
- Ship criteria: Filter row inputs render when row is made visible; styled per design tokens

### Chunk 2 — Filter logic + toolbar wiring (T-103 to T-108)
- User value: Typing filters rows; × clears; toolbar toggles row; gutter indicator updates; sort composes
- Scope: `filters` map in `buildGrid`; `renderRows` extended; `buildGrid` returns `{ element, toggleFilters }`; `buildToolbar` wired; `main.ts` updated; gutter indicator in col-header gutter
- Ship criteria: All smoke path steps pass

### Chunk 3 — Build output (T-200)
- User value: Live in `docs/`
- Scope: `npm run build` → commit `docs/bundle.js`
- Ship criteria: Build exits 0

## Tasks

### T-100 — Update buildFilterRow to populate inputs and clear buttons
- [x] Change `buildFilterRow` to accept `columns: ColumnDef[]` (already does — keep signature)
- [x] Replace the empty `<td>` body with: for each column, create a `<td>` containing an `<input>` and a `<button class="filter-clear filter-clear--hidden">`
- [x] Keep `data-col-group` and `data-col-order` on the `<td>` (for group collapse)

### T-101 — CSS: filter input + active state + clear button + gutter indicator
- [x] `.filter-row td` gets `position: relative; padding: 0;`
- [x] `.filter-input`, `.filter-input--active`, `.filter-clear`, `.filter-clear--hidden`, `.gutter--filtered` added

### T-102 — Commit chunk 1
- [x] `npm run typecheck && npm run lint && npm run build` — green
- [x] `git add src/grid.ts src/styles/grid.css && git commit -m "feat: add filter inputs and clear buttons to filter row"`

### T-103 — Add filters map and extend renderRows in buildGrid
- [ ] Add `const filters = new Map<number, string>();` to `buildGrid` closure
- [ ] In `renderRows`, after computing `models` (sorted), add a filter pass:
  ```ts
  const filtered = filters.size === 0 ? models : models.filter(model =>
    [...filters.entries()].every(([colIdx, term]) => {
      const raw = colIdx < model.values.length ? model.values[colIdx] : null;
      return cellText(raw).toLowerCase().includes(term.toLowerCase());
    })
  );
  ```
- [ ] Replace `models` with `filtered` in `tbody.replaceChildren(...)`
- [ ] Renumber rows 1…N using `filtered.map((model, i) => buildDataRow(model, data.columns, i + 1))`

### T-104 — Wire input events and × buttons in buildGrid
- [ ] After building thead, query `thead.querySelectorAll<HTMLInputElement>('input.filter-input')` and for each input:
  - On `input` event: update `filters` map (set if value non-empty, delete if empty); toggle `filter-input--active` class; toggle `filter-clear--hidden` on sibling button; call `renderRows()`; update gutter indicator
- [ ] Query `thead.querySelectorAll<HTMLButtonElement>('button.filter-clear')` and for each button:
  - On `click`: clear sibling input value; delete entry from `filters`; remove `filter-input--active`; add `filter-clear--hidden`; call `renderRows()`; update gutter indicator

### T-105 — Gutter indicator on col-header gutter corner
- [ ] In `buildGrid`, keep a reference to the gutter corner `<th>` in the col-header row (second `<tr>` in thead — `thead.rows[1].cells[0]`)
- [ ] Add an `updateGutterIndicator()` helper: if `filters.size > 0` add class `gutter--filtered` (sets color to `var(--color-gutter-indicator)`), else remove it
- [ ] Call `updateGutterIndicator()` from input event handler and × click handler

### T-106 — Add toggleFilters and change buildGrid return type
- [ ] In `buildGrid`, add:
  ```ts
  function toggleFilters(): void {
    const filterRow = thead.querySelector<HTMLTableRowElement>('.filter-row')!;
    const isVisible = filterRow.style.display === 'table-row';
    if (isVisible) {
      // Hide and clear all filters
      filterRow.style.display = 'none';
      filters.clear();
      thead.querySelectorAll<HTMLInputElement>('input.filter-input').forEach(inp => {
        inp.value = '';
        inp.classList.remove('filter-input--active');
        inp.nextElementSibling?.classList.add('filter-clear--hidden');
      });
      updateGutterIndicator();
      renderRows();
    } else {
      filterRow.style.display = 'table-row';
    }
  }
  ```
- [ ] Change return statement from `return wrap;` to `return { element: wrap, toggleFilters };`
- [ ] Update the return type annotation on `buildGrid` (TypeScript will infer, but be explicit): `): { element: HTMLElement; toggleFilters: () => void }`

### T-107 — Update buildToolbar and main.ts
- [ ] In `src/toolbar.ts`: change signature to `buildToolbar(onFiltersToggle: () => void): HTMLElement`; remove `disabled` and `title="Coming soon"` from the filters button; add `filtersBtn.addEventListener('click', onFiltersToggle)`; keep Columns button disabled
- [ ] In `src/main.ts`: destructure `const { element: gridEl, toggleFilters } = buildGrid(window.MSX_DATA);`; pass `toggleFilters` to `buildToolbar(toggleFilters)`; append `gridEl` instead of the raw result

### T-108 — Commit chunk 2
- [ ] `npm run typecheck && npm run lint && npm run build` — green
- [ ] `git add src/grid.ts src/styles/grid.css src/toolbar.ts src/main.ts && git commit -m "feat: wire column filter inputs to toolbar toggle with gutter indicator"`

### T-200 — Build and commit docs/bundle.js
- [ ] `git add docs/bundle.js && git commit -m "chore: update docs/ build output with column filtering"`

### T-950 — Smoke test
- [ ] Run all 9 smoke path steps from Rollout and Verify

### T-951 — Squash, merge, clean up
- [ ] Squash branch commits into one logical commit
- [ ] Fast-forward merge to main
- [ ] Delete feature branch

### T-952 — Update backlog
- [ ] Move "Column filtering" to "In product (shipped)" in `product-backlog.md`

## Relevant Files (Expected)
- `src/grid.ts` — filters map, renderRows extension, toggleFilters, return type change, input/button event wiring, gutter indicator
- `src/styles/grid.css` — filter input, active state, clear button, gutter indicator styles
- `src/toolbar.ts` — enable Filters button, accept callback
- `src/main.ts` — destructure buildGrid result, pass toggleFilters to buildToolbar
- `docs/bundle.js` — built output

## Notes
- `cellText()` is already a module-level function — use it in the filter predicate to match the displayed value
- `filters` is a `Map<number, string>` keyed on 0-based column index (same as `sortColIndex`)
- The `filter-row` is currently hidden via `display: none` in CSS; `toggleFilters` sets it to `display: table-row` explicitly (not `display: ''`) to override the CSS default
- When `filters.size === 0`, skip the filter pass entirely in `renderRows` for performance
- The gutter corner in the col-header row is `thead.rows[1].cells[0]` — the gutter `<th>` that has `rowSpan = 3` is in `thead.rows[0]`, so `thead.rows[1]` has no gutter cell; the gutter indicator instead goes on the group-header row's gutter (the rowspan=3 cell). Use `thead.rows[0].cells[0]` (the gutter corner with rowSpan=3).

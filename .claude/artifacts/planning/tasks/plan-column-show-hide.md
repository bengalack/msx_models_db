# Plan: Column Show / Hide

## Metadata
- Date: 2026-03-27
- Backlog item: Column show / hide
- Feature slug: column-show-hide

## Context
- Intended outcome: Users can open a column picker panel from the toolbar and toggle individual columns visible or hidden. The panel is grouped by column group. Group headers in the grid show a visual indicator when one or more of their columns are individually hidden.

## Functional Snapshot
- Problem: The grid has 29 columns across 8 groups. For any given research question, most columns are irrelevant noise. Users need to hide distracting columns to focus on the subset they care about.
- Target user: Researcher or enthusiast who wants to compare a specific subset of attributes across models.
- Success criteria (observable):
  - "⊞ Columns" toolbar button opens a panel listing all columns grouped by group, each with a checkbox
  - Unchecking a column hides it immediately in the grid (col-header, filter-row cell, all data cells)
  - Rechecking a column restores it immediately
  - A "partial" indicator appears on the group header strip when one or more of the group's columns are individually hidden; disappears when all are restored
  - Panel closes on outside click or pressing Escape
  - Hiding all columns in a group is permitted; the group header collapses to 0 width (group header hidden)
  - Column hiding composes correctly with group collapse and column filtering
- Primary user flow:
  1. User clicks "⊞ Columns" in the toolbar → picker panel opens below
  2. User unchecks "VRAM (KB)" → that column disappears from the grid; Memory group header shows partial indicator
  3. User unchecks remaining Memory columns → Memory group header is gone
  4. User re-checks a column → it reappears; group header partial indicator shown / removed accordingly
  5. User clicks outside the panel → panel closes
- Alternate flows:
  - User opens panel while a group is collapsed → checkboxes for collapsed columns are still visible in the panel; toggling them takes effect when the group is later expanded
  - User hides a column that has an active filter → column is hidden but filter remains active (row filtering continues to work)
  - User presses Escape while the panel is open → panel closes
- Must never happen:
  - Hiding a column corrupts data alignment in other columns
  - Group header `colSpan` becomes 0 without hiding the header (causes rendering artifacts)
  - Panel left open after navigation or page unload (not applicable — static page; no navigation)
  - Un-hiding a collapsed column un-collapses its group
- Key edge cases:
  - Hiding all columns in a group → group header must not be left with colSpan=0; it must be hidden via `display: none`
  - Showing a column in a collapsed group → column remains visually hidden (the group hide state takes priority); the group header colSpan is updated correctly for when the group is later expanded
  - Filtering active on a hidden column → filter result is correct; the filter cell simply isn't visible
  - Group collapsed AND some columns individually hidden → expand restores only the non-hidden columns
- Business rules:
  - Hidden columns are excluded from view only — they remain in the data model; sort and filter on hidden columns are preserved
  - Group header `colSpan` = count of non-hidden, non-collapsed columns in the group; if 0, the group header is hidden
  - Hidden-column state is in-memory only (not persisted to URL in this feature — deferred to URL state codec)
- Integrations: None — pure client-side DOM
- Non-functional requirements:
  - Performance: Toggle fires synchronously; re-render is one `renderRows()` pass + DOM attribute updates
  - Accessibility: Picker panel uses `<input type="checkbox">` + `<label>`; focusable; Escape closes panel
- MVI: toggle visibility per column; group header partial indicator; panel opens/closes; composes with group collapse and column filtering
- Deferred:
  - "Select all / Deselect all" per group buttons
  - Animation on panel open/close
  - URL state codec integration
  - Reset-to-default button in panel

## Executable Specification (Gherkin)

Feature: Column show / hide
  A user can open a column picker panel and toggle individual columns visible or hidden.
  Changes are reflected immediately in the grid without a page reload.

  Scenario: Open and close the column picker
    Given the grid is rendered with all columns visible
    When the user clicks the "⊞ Columns" toolbar button
    Then the column picker panel opens, showing all 29 columns grouped by group
    When the user clicks outside the panel
    Then the panel closes

  Scenario: Hide a single column
    Given the column picker is open
    When the user unchecks "VRAM (KB)"
    Then the VRAM column disappears from the col-header row, filter row, and all data rows
    And the Memory group header shows a partial indicator
    And the column picker checkbox for "VRAM (KB)" remains unchecked after the panel is closed and reopened

  Scenario: Restore a hidden column
    Given the "VRAM (KB)" column is hidden
    When the user opens the picker and rechecks "VRAM (KB)"
    Then the VRAM column reappears in its original position
    And the Memory group header partial indicator is removed if no other Memory columns are hidden

  Scenario: Hide all columns in a group
    Given the column picker is open
    When the user unchecks all columns in the "Memory" group
    Then the Memory group header is hidden (not a zero-width artefact)
    And the Memory column headers and filter cells are all hidden

  Scenario: Hidden column with active filter still filters rows
    Given an active filter on the "VRAM (KB)" column that narrows the row set
    When the user hides the "VRAM (KB)" column
    Then the filter remains active and the row set remains narrowed
    And the VRAM column cell is not visible in any row

  Scenario: Group collapse interacts correctly with hidden columns
    Given "VRAM (KB)" is individually hidden in the Memory group
    When the user collapses the Memory group
    Then the group collapses correctly (same visual result as collapsing with all columns visible)
    When the user expands the Memory group
    Then all Memory columns except "VRAM (KB)" are restored
    And "VRAM (KB)" remains hidden

  Scenario: Escape key closes the panel
    Given the column picker panel is open
    When the user presses Escape
    Then the panel closes

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- `git checkout -b feature/column-show-hide`

## Architecture Fit

### Touch points
- `src/grid.ts`:
  - Add `data-col-index` to filter-row `<td>` and data-row `<td>` (currently only on `<input>` and `<th>`)
  - Add `hiddenCols: Set<number>` to `buildGrid` closure (0-based column index)
  - Add `setColumnVisible(colIdx: number, visible: boolean): void` — hides/shows all cells for that column index; recalculates group header colSpan; toggles `.group-header--partial`
  - Add `getHiddenCols(): ReadonlySet<number>` — for picker to read current state
  - Add `recalcGroupHeader(groupId: number): void` — internal helper; computes visible count for group; updates colSpan and indicator; hides group header entirely if visible count is 0
  - Modify group collapse/expand handlers: on expand, skip cells belonging to `hiddenCols`; on setting colSpan, use `totalInGroup - hiddenInGroup` not raw total
  - Modify `renderRows()`: after `tbody.replaceChildren(...)`, re-apply both `collapsedGroups` and `hiddenCols`
  - Update `buildGrid` return type: `{ element, toggleFilters, setColumnVisible, getHiddenCols }`
- `src/col-picker.ts` (new):
  - `buildColPicker(groups, columns, getHiddenCols, onToggle): HTMLElement`
  - Panel element: `<div class="col-picker">` with group sections; appended to the toolbar (parent is `position: relative`)
  - Checkbox per column; label text = column label; checked state read from `getHiddenCols()` on open
  - On checkbox change: call `onToggle(colIdx, checked)` — picker is display-only; state lives in `buildGrid`
  - A `refresh()` method is NOT needed — the picker reads state from `getHiddenCols()` when it opens (panel is rebuilt or state is copied to checkboxes on open)
- `src/toolbar.ts`:
  - `buildToolbar(onFiltersToggle, onColsToggle): HTMLElement` — enable "⊞ Columns" button; wire click to `onColsToggle`
  - Toolbar root gets `position: relative` (needed to anchor picker panel)
- `src/main.ts`:
  - Destructure `{ element: gridEl, toggleFilters, setColumnVisible, getHiddenCols }` from `buildGrid`
  - Build picker: `const picker = buildColPicker(data.groups, data.columns, getHiddenCols, setColumnVisible)`
  - Append picker to toolbar element (returned from `buildToolbar`)
  - Wire `onColsToggle`: opens/closes picker; toggles panel visibility
  - Outside-click handler on `document`: close picker if click target is outside toolbar

### Compatibility
- `buildGrid` return type gains new fields — `main.ts` is the only call site; destructuring is additive
- `buildToolbar` gets a second required parameter — one call site; easy to update
- `renderRows` already centralises row output — re-applying `hiddenCols` is additive

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM interaction

## Testing Strategy (Tier 0/1/2)
- Tier 0: Manual smoke path only. DOM feature; Vitest jsdom not yet configured.

## Data and Migrations
- Applicability: N/A — no schema changes; hidden-column state is in-memory only

## Rollout and Verify
- Strategy: All-at-once (static file)
- Smoke path:
  1. Open `docs/index.html` — all 29 columns visible; "⊞ Columns" button enabled
  2. Click "⊞ Columns" → panel opens with 29 checkboxes in 8 groups, all checked
  3. Uncheck "VRAM (KB)" → VRAM column disappears from grid; Memory group shows partial indicator
  4. Close and reopen panel → "VRAM (KB)" still unchecked
  5. Recheck "VRAM (KB)" → column restored; partial indicator gone
  6. Uncheck all Memory columns → Memory group header disappears entirely
  7. Re-check one Memory column → Memory group header reappears with partial indicator
  8. Add a filter on Manufacturer, then hide the Manufacturer column → filter remains active; rows still narrowed
  9. Collapse the Memory group, hide a column inside it via picker, then expand → hidden column stays hidden
  10. Click outside panel → panel closes
  11. Press Escape while panel open → panel closes
- Signals to watch: no JS errors; group indicator appears/disappears; colSpan correct after all operations

## Cleanup Before Merge
- No debug console.log statements
- No feature flags, no temporary scaffolding
- Squash intermediate commits into logical commits
- Rebase onto trunk and merge with fast-forward only

## Definition of Done
- [ ] Gherkin specification is complete and current in the plan artifact
- [ ] All smoke path steps pass
- [ ] No hardcoded hex values added to CSS
- [ ] Cleanup gate satisfied
- [ ] Backlog updated (shipped item moved to "In product (shipped)")

## Chunks

### Chunk 1 — Grid infrastructure: hiddenCols in buildGrid (T-100 to T-104)
- User value: Grid can hide/show individual columns; group header updates correctly; composes with group collapse and filter
- Scope: `data-col-index` on all single-column cells; `hiddenCols` Set; `setColumnVisible`; `recalcGroupHeader`; updated collapse/expand handlers; updated `renderRows`; group-header partial indicator CSS
- Ship criteria: Calling `setColumnVisible(colIdx, false)` in the console hides the column and updates the group header indicator

### Chunk 2 — Column picker panel + toolbar wiring (T-200 to T-203)
- User value: Full interactive feature — picker opens, checkboxes toggle columns, panel closes on outside click / Escape
- Scope: `src/col-picker.ts`; updated `buildToolbar`; updated `main.ts`; CSS for picker panel
- Ship criteria: All smoke path steps pass

### Chunk 3 — Build output (T-300)
- User value: Live in `docs/`
- Scope: `npm run build` → commit `docs/bundle.js`
- Ship criteria: Build exits 0

## Tasks

### T-100 — Add data-col-index to filter-row td and data-row td
- [x] In `buildFilterRow`: change `td.dataset.colIndex = String(i)` to be on the `<td>`, not just on the `<input>` (the input keeps its own `data-col-index` for event handlers; the td also gets it for show/hide queries)
- [x] In `buildDataRow`: add `td.dataset.colIndex = String(i)` on each data `<td>` (skip the gutter cell — it has no column index)

### T-101 — Add hiddenCols, setColumnVisible, and recalcGroupHeader to buildGrid
- [x] Add `const hiddenCols = new Set<number>();` to `buildGrid` closure
- [x] Add `recalcGroupHeader(groupId: number): void`
- [x] Add `setColumnVisible(colIdx: number, visible: boolean): void`

### T-102 — Update renderRows to re-apply hiddenCols after tbody re-render
- [x] After the existing `collapsedGroups.forEach(...)` re-application block, add hiddenCols re-application loop

### T-103 — Update collapse/expand handlers to respect hiddenCols
- [x] Expand branch: skip hiddenCols cells; call recalcGroupHeader
- [x] Collapse branch: call recalcGroupHeader after collapsing

### T-104 — CSS: group-header partial indicator; update buildGrid return type
- [x] Add `.group-header--partial::after` CSS rule
- [x] Update `buildGrid` return type to include `setColumnVisible` and `getHiddenCols`
- [x] Add `getHiddenCols()` closure and updated return statement
- [x] Quality gate: `npm run typecheck && npm run lint` — green
- [x] Commit: `feat: add hidden column infrastructure with group header indicator`

### T-200 — Create src/col-picker.ts with buildColPicker
- [x] Create `src/col-picker.ts`
- [x] Export `buildColPicker(...)` returning `{ element, open, close }`
- [x] Build panel DOM with group sections and checkboxes
- [x] Wire checkbox change event to `onToggle`
- [x] Wire Escape keydown to close
- [x] `open()` syncs checkbox states from `getHiddenCols()`

### T-201 — Update buildToolbar to accept onColsToggle
- [x] Change signature to accept `onColsToggle: () => void`
- [x] Remove `colsBtn.disabled` and `colsBtn.title = 'Coming soon'`
- [x] Add `colsBtn.addEventListener('click', onColsToggle)`

### T-202 — Wire col-picker into main.ts + outside-click + toolbar CSS
- [x] Import `buildColPicker` in `main.ts`
- [x] Destructure `setColumnVisible` and `getHiddenCols` from `buildGrid`
- [x] Build picker and wire `onToggle = setColumnVisible`
- [x] `togglePicker()` open/close with `pickerOpen` state flag
- [x] Append `pickerEl` as child of `toolbarEl`
- [x] Outside-click handler closes picker
- [x] Document-level Escape handler closes picker
- [x] Updated `toolbar.css`: button enabled styles, `.col-picker` panel styles

### T-203 — Quality gate + commit Chunk 2
- [x] `npm run typecheck && npm run lint && npm run build` — green
- [ ] Smoke path steps 1–11 pass
- [ ] Commit: `feat: add column picker panel with show/hide toggle`
- [ ] Commit build: `chore: update docs/ build output with column show/hide`

### T-300 — Squash, merge, backlog
- [ ] Squash branch commits → single `feat: add interactive column show/hide with picker panel` commit
- [ ] `git checkout main && git merge --ff-only feature/column-show-hide`
- [ ] `git branch -d feature/column-show-hide`
- [ ] Update backlog: move "Column show / hide" to "In product (shipped)"
- [ ] Commit: `chore: mark column show/hide shipped; update backlog`

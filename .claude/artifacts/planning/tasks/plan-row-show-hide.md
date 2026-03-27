# Plan: Row Show / Hide

## Metadata
- Date: 2026-03-27
- Backlog item: Row show / hide
- Feature slug: row-show-hide

## Context
- Intended outcome: Users can right-click any row's gutter number to hide that row. Gaps between visible rows show an amber ▼▲ indicator in the gutter that, when clicked, unhides the hidden row(s) between those two visible neighbours.

## Functional Snapshot
- Problem: The grid shows all 10 models unconditionally. A researcher who wants to focus on a subset (e.g. "only Panasonic + Sony models") must either mentally filter or use column filtering — but column filtering on model name is awkward since there is no single-column that uniquely identifies a row for exclusion. Direct row hiding gives a fast, precise way to remove distracting rows.
- Target user: Researcher comparing a specific shortlist of models; wants to suppress the rest without losing them permanently.
- Success criteria (observable):
  - Right-clicking a gutter number shows a context menu with "Hide row"; clicking it removes that row from view
  - The context menu disappears on outside click, Escape, or after a menu item is chosen
  - When one or more rows are hidden between two visible rows, the gutter shows a single amber ▼▲ indicator cell spanning the gap
  - Clicking the ▼▲ indicator unhides all rows hidden in that contiguous gap
  - When the first row(s) are hidden, the indicator appears before the first visible row
  - When the last row(s) are hidden, the indicator appears after the last visible row
  - Hiding and unhiding compose correctly with column filtering and column sorting
- Primary user flow:
  1. User right-clicks a row's gutter number → context menu appears with "Hide row"
  2. User clicks "Hide row" → row disappears; ▼▲ indicator appears in the gutter at the gap position
  3. User clicks ▼▲ → all rows in that gap are restored; indicator disappears
- Alternate flows:
  - User right-clicks gutter while filter is active → the context menu still works; hiding the row removes it from the filtered view
  - User hides multiple non-adjacent rows → each gap gets its own ▼▲ indicator
  - User hides multiple adjacent rows → they share one ▼▲ indicator
  - User sorts while some rows are hidden → hidden rows stay hidden; ▼▲ indicators appear in the correct positions in the new sort order
  - User changes a filter while some rows are hidden → rows that were already hidden and now also fail the filter stay hidden; ▼▲ indicators recalculated for the new visible set
- Must never happen:
  - Hiding a row corrupts data alignment in other rows (gutter numbers must match the correct model)
  - Hidden rows being included in clipboard copy output (clipboard is a later feature, but the hidden-rows state must live in `renderRows`)
  - The context menu left open after the row is hidden
  - A ▼▲ indicator for a gap that has no hidden rows
- Key edge cases:
  - Hiding all rows → grid body contains only ▼▲ indicator(s); no data rows visible; no JS error
  - Unhiding restores the row at its original sort/filter position (not appended to the bottom)
  - Right-clicking the ▼▲ indicator itself does nothing special (no nested context menu)
  - Sorting changes the display order — hidden rows are tracked by model ID, not by DOM row index
- Business rules:
  - Hidden rows are tracked by stable model ID (not row index or DOM position)
  - A row can be hidden regardless of whether it currently passes the active filter
  - Row visibility is independent of column visibility (hiding a row does not affect columns)
  - Hidden-row state is in-memory only (not persisted to URL in this feature — deferred to URL state codec)
  - `renderRows` remains the single source of truth for what appears in the tbody
- MVI: right-click gutter → hide row; ▼▲ indicator in gutter at gap; click ▼▲ to unhide; composes with sort and filter
- Deferred:
  - Right-click to unhide from context menu on indicator
  - "Show all hidden rows" button in toolbar
  - URL state codec integration
  - Keyboard shortcut for hide/show

## Executable Specification (Gherkin)

Feature: Row show / hide
  A user can hide individual rows via the gutter context menu.
  Hidden rows are replaced by an amber indicator that, when clicked, restores them.

  Scenario: Hide a row via the gutter context menu
    Given the grid shows all rows
    When the user right-clicks a row's gutter number
    Then a context menu appears containing "Hide row"
    When the user clicks "Hide row"
    Then that row is no longer visible in the grid
    And an amber ▼▲ indicator appears in the gutter at the position of the gap

  Scenario: Unhide rows by clicking the gap indicator
    Given one or more rows are hidden and a ▼▲ indicator is visible in the gutter
    When the user clicks the ▼▲ indicator
    Then all rows hidden in that contiguous gap are restored to the grid
    And the ▼▲ indicator disappears

  Scenario: Context menu closes on Escape or outside click
    Given the context menu is open
    When the user presses Escape or clicks outside the menu
    Then the context menu closes without hiding any row

  Scenario: Multiple non-adjacent hidden rows produce separate indicators
    Given the grid shows rows 1 through 10
    When the user hides row 3 and also hides row 7
    Then a ▼▲ indicator appears between rows 2 and 4
    And a separate ▼▲ indicator appears between rows 6 and 8

  Scenario: Hiding composes with sort — model stays hidden after re-sort
    Given row for model "FS-A1ST" is hidden
    When the user sorts by a different column
    Then the "FS-A1ST" row remains hidden in the new sort order
    And the ▼▲ indicator appears at the correct position in the sorted sequence

  Scenario: Hiding composes with filter — hidden row absent regardless of filter
    Given row for model "FS-A1ST" is hidden
    When the user types a filter term that would otherwise match "FS-A1ST"
    Then "FS-A1ST" remains hidden
    And if no other rows match, the grid body shows only the ▼▲ indicator

  Scenario: Hiding all rows leaves only indicators — no JS error
    Given the grid shows all rows
    When the user hides every row one by one
    Then the grid body contains only ▼▲ indicator(s)
    And no JavaScript error occurs

  Scenario: Row data alignment is preserved after hiding
    Given rows 2 and 4 are visible after row 3 is hidden
    When the user reads any cell in those visible rows
    Then each cell contains the correct value for its model

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- `git checkout -b feature/row-show-hide`

## Architecture Fit

### Touch points
- `src/grid.ts`:
  - Add `hiddenRows: Set<number>` to `buildGrid` closure — keyed by stable model ID (`model.id`)
  - Modify `renderRows()`:
    - After computing `filtered`, further exclude `hiddenRows`: `const visible = filtered.filter(m => !hiddenRows.has(m.id))`
    - After building visible rows, insert ▼▲ indicator `<tr>` cells at every gap (see indicator logic below)
    - Gutter numbers continue to use the visible-row rank (1, 2, 3...) as before
  - Add context menu: on `contextmenu` event on gutter `<td>` cells, show a menu `<div>` with "Hide row"; on click call `hideRow(modelId)` and remove menu; close menu on `mousedown` outside and `keydown Escape`
  - Add `hideRow(modelId: number): void` — adds to `hiddenRows`, calls `renderRows()`
  - Add `unhideRowsInGap(modelIds: number[]): void` — removes all from `hiddenRows`, calls `renderRows()`
  - ▼▲ indicator row: a `<tr class="row-gap-indicator">` with a single `<td colspan="N+1">` (gutter + all columns) containing the ▼▲ button; clicking calls `unhideRowsInGap` with the IDs hidden in that gap
  - Update `buildGrid` return type: add `getHiddenRows(): ReadonlySet<number>`
- `src/styles/grid.css`:
  - `.row-gap-indicator td` — zero padding, amber color, cursor pointer
  - `.row-gap-indicator__btn` — the actual clickable ▼▲ element

### Gap indicator logic (inside renderRows)
After computing `visible: ModelRecord[]` (post-sort, post-filter, post-hiddenRows):

The "original sequence" for gap detection is the sorted+filtered list BEFORE applying `hiddenRows`. Walk this sequence with a pointer; whenever one or more consecutive entries are in `hiddenRows`, collect their IDs and emit a gap indicator row. Then emit the next visible row. Handle leading and trailing gaps too.

```
originalSeq = sortModels(...).filter(passesFilter)  // same as `filtered`
visible     = filtered.filter(m => !hiddenRows.has(m.id))

Walk originalSeq:
  buffer = []
  for each model in originalSeq:
    if hiddenRows.has(model.id):
      buffer.push(model.id)
    else:
      if buffer.length > 0: emit gap indicator(buffer); buffer = []
      emit data row
  if buffer.length > 0: emit trailing gap indicator(buffer)
```

### Column count for colspan
The indicator `<td>` colspan must equal 1 (gutter) + total columns. Hidden columns are still present in the DOM as zero-width stubs — colspan should span the full table width, so use `data.columns.length + 1`.

### Compatibility
- `renderRows` is the only place tbody is built — change is additive
- `hiddenRows` is a new independent Set; no interaction with `hiddenCols` or `collapsedGroups` beyond both being re-applied in `renderRows`
- Context menu is a new DOM overlay; does not share state with the col-picker panel

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM

## Testing Strategy
- Tier 0: Manual smoke path only. No Vitest jsdom yet.

## Data and Migrations
- Applicability: N/A — hidden-row state is in-memory only

## Rollout and Verify
- Strategy: All-at-once (static file)
- Smoke path:
  1. Open `docs/index.html` — all rows visible; no ▼▲ indicators
  2. Right-click a gutter number → context menu appears with "Hide row"
  3. Click "Hide row" → row disappears; ▼▲ indicator in gutter
  4. Click ▼▲ → row restored; indicator gone
  5. Hide two adjacent rows → single ▼▲ indicator; click it → both restored
  6. Hide two non-adjacent rows → two separate ▼▲ indicators
  7. Sort by a column, then hide a row → row stays hidden after re-sort; indicator in correct position
  8. Filter rows, hide a visible row, then clear filter → hidden row stays hidden
  9. Right-click while Escape or click outside → menu closes without hiding
  10. Hide all rows → only indicators remain; no JS error
  11. Column show/hide and group collapse still work alongside hidden rows

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

### Chunk 1 — Hidden rows data model + renderRows gap logic (T-100 to T-102)
- User value: Rows can be hidden programmatically; gap indicators appear in the correct positions; sort and filter compose
- Scope: `hiddenRows` Set; modified `renderRows` with gap-walking logic; `.row-gap-indicator` CSS; `unhideRowsInGap` wired to indicator clicks; `getHiddenRows` on return type
- Ship criteria: Calling `hideRow(id)` in the console hides the row and shows a ▼▲ indicator; clicking it restores

### Chunk 2 — Gutter context menu (T-200 to T-202)
- User value: Full interactive feature — right-click hides row via native-style menu
- Scope: Context menu DOM + CSS; `contextmenu` listener on gutter cells; close-on-outside-click + Escape; `hideRow` called on menu click
- Ship criteria: All smoke path steps pass

### Chunk 3 — Build + merge (T-300)
- User value: Live in `docs/`
- Scope: `npm run build` → commit docs/; squash; merge

## Tasks

### T-100 — Add hiddenRows, hideRow, unhideRowsInGap, getHiddenRows to buildGrid
- [x] Add `const hiddenRows = new Set<number>();` (keyed by model ID) to closure
- [x] Add `function hideRow(modelId: number): void { hiddenRows.add(modelId); renderRows(); }`
- [x] Add `function unhideRowsInGap(modelIds: number[]): void { modelIds.forEach(id => hiddenRows.delete(id)); renderRows(); }`
- [x] Add `function getHiddenRows(): ReadonlySet<number> { return hiddenRows; }` (for future URL codec)
- [x] Update `buildGrid` return type to include `getHiddenRows` and `hideRow`; update return statement

### T-101 — Update renderRows with gap-walking logic and indicator rows
- [x] Add `buildGapIndicator(hiddenIds, colCount, onUnhide)` function above `buildGrid`
- [x] Replace `tbody.replaceChildren(...filtered.map(...))` with gap-walking loop
- [x] Row numbers use a separate counter incremented only for non-indicator rows
- [x] Add `gutter.dataset.modelId` in `buildDataRow`
- [x] Re-apply collapsedGroups and hiddenCols as before (unchanged)

### T-102 — CSS for gap indicator + quality gate + commit chunk 1
- [x] Add `.row-gap-indicator` and `.row-gap-indicator__btn` CSS (uses `--color-gutter-indicator`)
- [x] Add `.ctx-menu` and `.ctx-menu__item` CSS to `grid.css`
- [x] `npm run typecheck && npm run lint` — green
- [ ] Commit: `feat: add row hide/unhide with gap indicator in gutter`

### T-200 — Gutter context menu DOM + event wiring
- [x] Event delegation on `tbody` for `contextmenu` events on `td.gutter` cells
- [x] `buildContextMenu` inline; menu positioned `position: fixed` at cursor
- [x] `hideRow(modelId)` called on menu item click
- [x] Close on outside `mousedown` and `Escape` keydown (document-level listeners)
- [x] `gutter.dataset.modelId` set in `buildDataRow`

### T-201 — CSS for context menu
- [x] `.ctx-menu` and `.ctx-menu__item` added to `src/styles/grid.css` (in T-102, combined with gap indicator CSS)

### T-202 — Quality gate + commit chunk 2
- [x] `npm run typecheck && npm run lint && npm run build` — green
- [ ] Smoke path steps 1–11 pass
- [ ] Commit: `feat: add right-click context menu to hide rows`
- [ ] Commit build: `chore: update docs/ build output with row show/hide`

### T-300 — Squash, merge, backlog
- [ ] Squash branch commits → single `feat: add interactive row show/hide with gap indicator and context menu`
- [ ] `git checkout main && git merge --ff-only feature/row-show-hide`
- [ ] `git branch -d feature/row-show-hide`
- [ ] Update backlog: move "Row show / hide" to "In product (shipped)"
- [ ] Commit: `chore: mark row show/hide shipped; update backlog`

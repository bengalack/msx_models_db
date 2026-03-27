# Plan: Cell Selection

## Metadata
- Date: 2026-03-27
- Backlog item: Cell selection
- Feature slug: cell-selection

## Context
- Intended outcome: Users can select individual cells, multi-select with Ctrl/Cmd, extend a rectangular selection with Shift, and drag to cover a range — laying the groundwork for clipboard copy.

## Functional Snapshot
- Problem: The grid is read-only with no way to pick a subset of cells for comparison or copying. A researcher who wants to extract a few values (e.g. "CPU and RAM for my three shortlisted models") has no way to mark those cells, and clipboard copy (next feature) relies on selection state.
- Target user: Researcher comparing specific attribute values across a shortlist of models; wants to lasso a block of cells to copy into a spreadsheet.
- Success criteria (observable):
  - Clicking a data cell highlights it (accent-dim fill + solid accent border); all previously selected cells are cleared
  - Ctrl/Cmd+clicking a cell toggles it in/out of the selection without clearing other cells
  - Shift+clicking a cell selects the rectangular block between the anchor cell and the clicked cell
  - Click+dragging across cells selects every cell the pointer crosses, forming a rectangle from the drag start to current position
  - Selected cells are visually distinct in both dark and light themes (dark mode: accent-dim fill + glow)
  - Selection survives sort and filter changes (cells are re-highlighted after `renderRows`)
  - Pressing Escape clears the entire selection
  - Clicking in any non-cell area (toolbar, header, gutter) clears selection
- Primary user flow:
  1. User clicks a data cell → that cell is highlighted, anchor is set
  2. User Shift+clicks another cell → entire rectangular region is highlighted
  3. User presses Ctrl/Cmd+C (next feature) to copy
- Alternate flows:
  - User Ctrl/Cmd+clicks multiple scattered cells → each toggled independently; anchor moves to last clicked
  - User click+drags across a block → rectangle covered by the drag is selected
  - User sorts while cells are selected → same cells (by model ID + column index) are re-highlighted in new row order
  - User hides a selected column → cells in that column remain in `selectedCells` Set but are not visible; unhiding that column re-shows them highlighted
  - User hides a row whose cells are selected → same: cells stay in `selectedCells`; unhiding restores highlight
- Must never happen:
  - Selecting a cell in a collapsed group column (only the stub is clickable; stub is treated as a normal data cell)
  - Drag interaction triggering text selection in the browser (must call `preventDefault`)
  - Selection being silently cleared when `renderRows` is called (filter/sort must preserve selection)
  - Clicking the gutter, gap indicator, or any non-data cell affecting selection state
- Key edge cases:
  - Shift+click when no anchor exists → treat like plain click (set anchor + select that cell)
  - Drag starts on a non-data cell (gutter, indicator) → do not start drag selection
  - Shift+click to a cell whose model is currently hidden → anchor is not in visible rows; treat like plain click
  - All selected cells become hidden (all rows hidden or all columns hidden) → `selectedCells` retains state; cells re-highlight when restored
  - Escape clears selection even when no cells selected → no error
- Business rules:
  - Selection is keyed by `"${modelId}:${colIdx}"` — stable across sort/filter/render
  - Only visible data cells (non-gutter, non-indicator) are clickable for selection
  - Gutter clicks, group header clicks, column header clicks do not affect selection
  - Collapsed group stubs are selectable (they are visible data cells)
  - Shift+click always replaces the entire selection with the new rectangle (no additive rectangle)
  - Drag always replaces the entire selection with the current drag rectangle
  - `renderRows` is the single place that pushes selection state back to the DOM
- MVI: plain click single-cell, Ctrl/Cmd+click toggle, Shift+click rectangle, click+drag rectangle, Escape to clear; accent-dim fill + selection-border style; selection survives re-renders
- Deferred:
  - Ctrl+drag (additive drag)
  - Keyboard selection (arrow keys, Shift+arrow)
  - URL state codec integration (deferred to URL state feature)
  - "Select all" shortcut (Ctrl+A)

## Executable Specification (Gherkin)

Feature: Cell selection
  A user can select data cells individually or as a rectangle.
  The selection is preserved across sort/filter changes and can be cleared with Escape.

  Scenario: Plain click selects a single cell and clears previous selection
    Given two cells A and B are selected
    When the user clicks cell C
    Then only cell C is highlighted
    And cells A and B are no longer highlighted

  Scenario: Ctrl/Cmd+click toggles a cell without clearing others
    Given cell A is selected
    When the user Ctrl+clicks cell B
    Then cells A and B are both highlighted
    When the user Ctrl+clicks cell A
    Then only cell B is highlighted

  Scenario: Shift+click selects a rectangle from anchor to clicked cell
    Given the user has clicked cell at row 2, column "RAM" (anchor set)
    When the user Shift+clicks the cell at row 5, column "VRAM"
    Then all cells in the rectangle rows 2-5 × columns RAM-VRAM are highlighted

  Scenario: Drag selects cells covered by the drag path
    Given no cells are selected
    When the user presses and holds on cell at row 1, column "CPU"
    And drags to cell at row 3, column "RAM"
    Then all cells in rows 1-3 × columns CPU-RAM are highlighted

  Scenario: Escape clears the entire selection
    Given three cells are selected
    When the user presses Escape
    Then no cells are highlighted

  Scenario: Selection survives a sort change
    Given cells in row "FS-A1ST" are selected
    When the user sorts by a different column
    Then the cells in the "FS-A1ST" row are still highlighted at their new position

  Scenario: Clicking the gutter does not affect selection
    Given one cell is selected
    When the user clicks a gutter number
    Then the selected cell remains highlighted

  Scenario: Shift+click with no prior anchor acts like plain click
    Given no cells are selected (no anchor)
    When the user Shift+clicks a cell
    Then only that one cell is highlighted and becomes the anchor

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- `git checkout -b feature/cell-selection`

## Architecture Fit

### Touch points
- `src/grid.ts`:
  - `buildDataRow`: add `data-model-id` to the `<tr>` element (currently only on gutter `<td>`)
  - New closure state: `selectedCells: Set<string>` (keyed `"${modelId}:${colIdx}"`), `anchor: { modelId: number; colIdx: number } | null`, `isDragging: boolean`
  - New helper `selKey(modelId: number, colIdx: number): string` → `"${modelId}:${colIdx}"`
  - New `applySelectionToDOM(): void` — iterates `tbody.querySelectorAll('td[data-col-index]')`, reads `tr.dataset.modelId` + `td.dataset.colIndex`, toggles `.cell--selected`; called at end of `renderRows` and after every selection mutation
  - New `selectRectangle(a: {modelId:number;colIdx:number}, b: {modelId:number;colIdx:number}): void` — reads visible row order from `tbody.querySelectorAll('tr[data-model-id]')`, reads visible col indices (excluding `hiddenCols`), computes min/max row + col within those sets, populates `selectedCells`
  - New `getSelectedCells(): ReadonlySet<string>` — accessor for clipboard copy
  - New `clearSelection(): void` — clears `selectedCells`, calls `applySelectionToDOM()`
  - Updated `renderRows`: call `applySelectionToDOM()` at the end (after re-applying collapsedGroups + hiddenCols)
  - Updated return type: add `getSelectedCells`
  - Event delegation on `tbody` for `mousedown` on `td[data-col-index]` (not gutter):
    - Plain click (no modifier): `clearSelection()`, add clicked cell, set anchor, call `applySelectionToDOM()`
    - Ctrl/Cmd+click: toggle cell in `selectedCells`, update anchor, call `applySelectionToDOM()`
    - Shift+click: if anchor exists call `selectRectangle(anchor, target)`, else treat as plain click
    - All clicks: call `e.preventDefault()` to suppress browser text selection
  - Drag selection:
    - `mousedown` on data cell: if not Shift/Ctrl, set `isDragging = true`; drag anchor = clicked cell
    - `mouseenter` event delegation on `tbody td[data-col-index]` (checked `isDragging` + `e.buttons === 1`): call `selectRectangle(dragAnchor, current)` → `applySelectionToDOM()`
    - `mouseup` on `document`: `isDragging = false`
  - Escape handler (already on document for context menu) extended: if no active menu, call `clearSelection()`
  - Document `mousedown` at capture: if target is not a data cell (`td[data-col-index]` inside `tbody`) and not the col picker, call `clearSelection()` — **but do NOT clear when clicking the gutter, group headers, or col headers**

  > **Note**: the existing `document.addEventListener('keydown', ...)` for Escape closes the context menu when `activeMenu` is set. We extend it: when `activeMenu` is null, Escape clears selection. No conflict.

### Key implementation detail — `applySelectionToDOM`
```
function applySelectionToDOM(): void {
  tbody.querySelectorAll<HTMLTableCellElement>('td[data-col-index]').forEach(td => {
    const tr = td.closest('tr') as HTMLTableRowElement | null;
    const modelId = tr?.dataset.modelId;
    if (!modelId) return;
    td.classList.toggle('cell--selected', selectedCells.has(selKey(Number(modelId), Number(td.dataset.colIndex))));
  });
}
```

### Key implementation detail — `selectRectangle`
```
function selectRectangle(
  a: { modelId: number; colIdx: number },
  b: { modelId: number; colIdx: number }
): void {
  const visibleModelIds = [...tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]')]
    .map(tr => Number(tr.dataset.modelId));
  const visibleColIdxs = data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i));

  const ar = visibleModelIds.indexOf(a.modelId);
  const br = visibleModelIds.indexOf(b.modelId);
  const ac = visibleColIdxs.indexOf(a.colIdx);
  const bc = visibleColIdxs.indexOf(b.colIdx);
  // If anchor or target is not in the current visible set, fall back to single-cell
  if (ar === -1 || br === -1 || ac === -1 || bc === -1) {
    selectedCells.clear();
    selectedCells.add(selKey(b.modelId, b.colIdx));
    anchor = b;
    return;
  }
  const minR = Math.min(ar, br); const maxR = Math.max(ar, br);
  const minC = Math.min(ac, bc); const maxC = Math.max(ac, bc);
  selectedCells.clear();
  for (let r = minR; r <= maxR; r++) {
    for (let c = minC; c <= maxC; c++) {
      selectedCells.add(selKey(visibleModelIds[r], visibleColIdxs[c]));
    }
  }
}
```

### CSS tokens used
- `--color-accent-dim` — background fill for selected cell
- `--color-selection-border` — border color (defined in both themes)
- `--color-accent-glow` — box-shadow for dark mode glow (defined as `none` in light mode — no extra logic needed)

- `src/styles/grid.css`:
  - `.cell--selected` — `background: var(--color-accent-dim); outline: 1px solid var(--color-selection-border); outline-offset: -1px; box-shadow: var(--color-accent-glow);`
  - `.grid-wrap` (or `table`): `user-select: none;` — prevents browser text-drag during cell selection

### Compatibility
- `applySelectionToDOM` is additive to `renderRows`; no existing logic is removed
- Context menu Escape handler is extended, not replaced
- `getSelectedCells()` on the return type is additive; callers that don't destructure it are unaffected
- `data-model-id` on `<tr>` is additive; existing gutter `data-model-id` on `<td>` is kept

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM

## Testing Strategy
- Tier 0: Manual smoke path only. No Vitest jsdom in this feature.

## Data and Migrations
- Applicability: N/A — selection state is in-memory only

## Rollout and Verify
- Strategy: All-at-once (static file)
- Smoke path:
  1. Open `docs/index.html` — click a data cell → highlights with accent-dim fill + border; no other cells highlighted
  2. Click a different cell → first cell clears, new one highlights
  3. Ctrl+click a second cell → both highlighted
  4. Ctrl+click the first cell again → deselected, only second highlighted
  5. Click one cell (anchor set), Shift+click another cell 3 rows down and 2 columns right → 3×3 rectangle highlighted
  6. Click+drag from top-left to bottom-right across 2×4 block → all 8 cells highlighted during drag
  7. Press Escape → all cells deselected
  8. Sort by a column while cells highlighted → same model/column cells still highlighted in new order
  9. Filter rows while cells highlighted → visible selected cells still highlighted; hidden ones retain state
  10. Clear filter → cells re-highlighted in original positions
  11. Click a gutter number → selection unchanged
  12. Click a group header or column header → selection unchanged
  13. Hide a column that contains selected cells → cells hidden but state preserved; unhide → highlights return
  14. Dark mode: selected cells have visible glow; light mode: no glow, accent border present
  15. Row context menu still works (right-click gutter → hide row); no conflict with selection

## Cleanup Before Merge
- No debug console.log statements
- No feature flags, no temporary scaffolding
- Squash intermediate commits into logical commits
- Rebase onto trunk and merge with fast-forward only

## Definition of Done
- [x] Gherkin specification is complete and current in the plan artifact
- [x] All smoke path steps pass
- [x] No hardcoded hex values added to CSS
- [x] Cleanup gate satisfied
- [x] Backlog updated (shipped item moved to "In product (shipped)")

## Chunks

### Chunk 1 — Selection state, click/ctrl-click, CSS (T-100 to T-103)
- User value: Single-cell and multi-cell selection via click / Ctrl+click; visual feedback in both themes; selection survives re-renders
- Scope: `data-model-id` on `<tr>`; `selectedCells` Set; `anchor`; `applySelectionToDOM`; `getSelectedCells`; `clearSelection`; `renderRows` integration; `mousedown` delegation for plain + Ctrl/Cmd click; Escape clears; CSS `.cell--selected` + `user-select: none`
- Tasks:
  - [x] T-100: In `buildDataRow`, set `tr.dataset.modelId = String(model.id)` (row-level attribute for selection hit-testing)
  - [x] T-101: Add `selectedCells`, `anchor`, `isDragging` state; add `selKey()`, `applySelectionToDOM()`, `clearSelection()`, `selectRectangle()` helpers; call `applySelectionToDOM()` at end of `renderRows`; add `getSelectedCells` to return type and return value
  - [x] T-102: Add `mousedown` event delegation on `tbody` for `td[data-col-index]`; handle plain click (clear + select + anchor) and Ctrl/Cmd+click (toggle + anchor); call `e.preventDefault()`; extend document Escape handler to clear selection when `activeMenu` is null
  - [x] T-103: Add `.cell--selected` CSS to `grid.css` using `--color-accent-dim`, `--color-selection-border`, `--color-accent-glow`; add `user-select: none` to `.grid` table (or `.grid-wrap`)

### Chunk 2 — Shift-click + drag (T-200 to T-201)
- User value: Full rectangular selection (Shift+click) and drag selection for power users; completes the selection interaction model required before clipboard copy
- Scope: Shift+click calls `selectRectangle`; drag via `mousedown` + `mouseenter` delegation + `mouseup` on document
- Tasks:
  - [x] T-200: Extend `mousedown` handler: detect Shift+click → if anchor exists call `selectRectangle(anchor, target)` + `applySelectionToDOM()`, else treat as plain click; set `isDragging = true` on non-modifier clicks; store `dragStart` cell reference
  - [x] T-201: Add `mouseenter` event delegation on `tbody td[data-col-index]` checking `isDragging && e.buttons === 1` → call `selectRectangle(dragStart, current)` + `applySelectionToDOM()`; add `document.addEventListener('mouseup', () => { isDragging = false; })`

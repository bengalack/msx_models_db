# Plan: Selection Column and Row Header Highlight

## Metadata
- Date: 2026-04-11
- Backlog item: Selection column and row header highlight (new — not yet in backlog)
- Feature slug: selection-header-highlight

## Context
- Intended outcome: When cells are selected, the corresponding column header(s) and row number cell(s) show inverted colors, giving users an immediate visual anchor for the active selection across the full grid.

## Functional Snapshot
- Problem: Selected cells are highlighted, but there is no visual cue in the column header or row number gutter to show which columns and rows are involved — especially useful when the selection spans many rows or columns.
- Target user: MSX enthusiast comparing specs; wants to see at a glance which columns and rows are active in their selection.
- Success criteria (observable):
  - Every column header whose column contains at least one selected cell shows inverted colors (text ↔ background).
  - Every row number cell whose row contains at least one selected cell shows inverted colors.
  - Clearing the selection immediately reverts all headers and row number cells to normal.
- Primary user flow:
  1. User clicks or drags to select one or more cells.
  2. The column header(s) for those columns invert.
  3. The row number cell(s) for those rows invert.
  4. User clears the selection (Escape, plain click elsewhere) → headers and row numbers revert.
- Alternate flows:
  - Full-row selection (gutter click): all visible column headers invert; the row number cell inverts (two classes will coexist on the gutter `<td>`, both producing the same visual result).
  - Drag selection extending across multiple columns and rows: all affected headers/gutters update live during drag.
  - Sort/filter while cells selected: `renderRows` calls `applySelectionToDOM()` which re-applies the classes in the new layout.
- Must never happen:
  - Stale inverted column header or row number cell after selection is cleared.
  - An inverted column header for a column with zero selected cells.
- Key edge cases:
  - Multi-column selection: all unique column indices derived from `selectedCells` get `col-header--active`.
  - Full-row selection via gutter: `syncCellsFromRowSelection()` fills `selectedCells` → `applySelectionToDOM()` handles both the gutter and all column headers.
  - `renderRows` (after sort/filter): existing call to `applySelectionToDOM()` at end of `renderRows` handles re-application.
  - Hidden column selected: its `<th>` is `display:none` — toggling the class is harmless; it becomes visible if the column is un-hidden.
- Business rules:
  - Inversion is purely visual — no state is stored, no URL encoding.
  - Both CSS classes are toggled by `applySelectionToDOM()` only; no other code path sets them.
  - The `gutter--cell-active` class coexists with `gutter--row-selected` when row selection is also active; both produce the same inverted look (no conflict).
- Integrations: none.
- Non-functional requirements:
  - Performance: class toggling is O(visible columns + visible rows) on each selection change — negligible.
  - Accessibility: no ARIA changes required; color inversion is supplemental to existing selection styling.
- Minimal viable increment (MVI): extend `applySelectionToDOM()` to toggle two new CSS classes; add those classes to `grid.css`.
- Deferred: nothing — the feature is fully defined.

## Executable Specification (Gherkin)

Feature: Selection column and row header highlight
  When cells are selected the corresponding column headers and row number cells
  show inverted colors so the user can see which dimensions are active at a glance.

  Scenario: Selecting a cell inverts its column header and row number cell
    Given no cells are selected
    When the user clicks the cell at row "FS-A1ST", column "RAM"
    Then the "RAM" column header shows inverted colors
    And the row number cell for "FS-A1ST" shows inverted colors
    And all other column headers show normal colors
    And all other row number cells show normal colors

  Scenario: Clearing selection reverts all headers and row number cells
    Given cells in multiple columns and rows are selected
    When the user presses Escape
    Then all column headers show normal colors
    And all row number cells show normal colors

  Scenario: Multi-cell selection inverts every affected column header and row number cell
    Given no cells are selected
    When the user Shift+clicks to select a 2×3 rectangle (2 columns, 3 rows)
    Then exactly 2 column headers show inverted colors
    And exactly 3 row number cells show inverted colors

  Scenario: Full-row selection via gutter inverts all visible column headers
    Given no cells are selected
    When the user clicks a row number in the gutter (selecting the full row)
    Then all visible column headers show inverted colors
    And the clicked row number cell shows inverted colors

  Scenario: Live update during drag
    Given the user starts dragging from column "CPU", row 1
    When the drag extends to column "RAM", row 3
    Then the "CPU" and "RAM" column headers show inverted colors
    And row number cells for rows 1–3 show inverted colors

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- `git checkout -b feature/selection-header-highlight`

## Architecture Fit
- Touch points:
  - `src/grid.ts`: extend `applySelectionToDOM()` only — no new state, no new event handlers.
  - `src/styles/grid.css`: two new CSS rule blocks.
- Compatibility notes:
  - `applySelectionToDOM()` is additive — existing `cell--selected` toggling is unchanged.
  - New classes `col-header--active` and `gutter--cell-active` are purely additive; no existing class or selector is modified.
  - The existing `gutter--row-selected` class and its CSS rules are untouched.

### Key implementation detail — extended `applySelectionToDOM`
```ts
function applySelectionToDOM(): void {
  // Existing: toggle cell--selected on body cells
  tbody.querySelectorAll<HTMLTableCellElement>('td[data-col-index]').forEach(td => {
    const tr = td.closest<HTMLTableRowElement>('tr[data-model-id]');
    if (!tr?.dataset.modelId) return;
    td.classList.toggle(
      'cell--selected',
      selectedCells.has(selKey(Number(tr.dataset.modelId), Number(td.dataset.colIndex)))
    );
  });

  // New: derive active column indices and model IDs
  const activeColIdxs = new Set<number>();
  const activeModelIds = new Set<number>();
  for (const key of selectedCells) {
    const colon = key.indexOf(':');
    activeModelIds.add(Number(key.slice(0, colon)));
    activeColIdxs.add(Number(key.slice(colon + 1)));
  }

  // New: invert matching column headers
  thead.querySelectorAll<HTMLTableCellElement>('th.col-header[data-col-index]').forEach(th => {
    th.classList.toggle('col-header--active', activeColIdxs.has(Number(th.dataset.colIndex)));
  });

  // New: invert matching row number (gutter) cells
  tbody.querySelectorAll<HTMLTableCellElement>('td.gutter[data-model-id]').forEach(td => {
    td.classList.toggle('gutter--cell-active', activeModelIds.has(Number(td.dataset.modelId)));
  });
}
```

### CSS additions (`src/styles/grid.css`)
```css
/* Column header — active (any cell in this column is selected) */
/* Specificity matches .col-header:hover — placed after it so active wins */
.col-header--active {
  background: var(--color-text-heading);
  color: var(--color-header-bg);
}

/* Gutter row number — active (any cell in this row is selected) */
/* Same pattern as gutter--row-selected; both may coexist on the same cell */
.grid tbody td.gutter--cell-active {
  background: var(--color-gutter-text);
  color: var(--color-gutter-bg);
}

/* Beat even-row stripe (same pattern as gutter--row-selected override) */
.grid tbody tr:nth-child(even) td.gutter--cell-active {
  background: var(--color-gutter-text);
  color: var(--color-gutter-bg);
}
```

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM manipulation; no server interaction, no persistent state.

## Testing Strategy
- Tier 0: Manual smoke path only (consistent with cell-selection and other grid features).
- Tier 1/2: N/A.

## Data and Migrations
- Applicability: N/A — visual-only change; no data file or schema modifications.

## Rollout and Verify
- Strategy: All-at-once (static file change).
- Smoke path:
  1. Open `docs/index.html` — confirm no column headers or gutter cells are inverted.
  2. Click a data cell → its column header inverts; its row number cell inverts; all others are normal.
  3. Ctrl+click a cell in a different column and row → that column header and row number also invert.
  4. Press Escape → all column headers and row number cells revert to normal immediately.
  5. Click a cell, then Shift+click 2 columns right and 3 rows down → exactly 3 column headers and 4 row numbers are inverted.
  6. Click+drag across a 2×4 block → headers/gutters update live during drag.
  7. Click a gutter number to select a full row → all visible column headers invert; that row's gutter cell inverts.
  8. Sort by a column while cells are selected → after re-render, headers and gutters still reflect the same selection.
  9. Filter rows to hide some selected rows → column headers for selected columns remain inverted (cells still in `selectedCells`).
  10. Dark mode: verify contrast is acceptable (inverted header uses `--color-text-heading` as background).

## Cleanup Before Merge
- No debug statements.
- No temporary code.
- Squash intermediate commits into logical commits.
- Ensure all commits follow Conventional Commits.
- Rebase onto trunk and merge (fast-forward only).

## Definition of Done
- [ ] Gherkin specification is complete and current in this plan artifact.
- [ ] All smoke path steps pass in both light and dark mode.
- [ ] No hardcoded hex colors added to CSS.
- [ ] Cleanup gate satisfied.
- [ ] Backlog updated (item added and moved to "In product (shipped)").

## Chunks

### Chunk 1 — Extend `applySelectionToDOM` + CSS (single deliverable)
- User value: Column headers and row number cells invert immediately when cells are selected.
- Scope: `src/grid.ts` (`applySelectionToDOM` only) + `src/styles/grid.css` (two new rule blocks).
- Ship criteria: All 10 smoke path steps pass in both themes.
- Rollout notes: none.

## Relevant Files (Expected)
- `src/grid.ts` — extend `applySelectionToDOM()` (lines ~373–382)
- `src/styles/grid.css` — add `.col-header--active` and `.gutter--cell-active` rules

## Assumptions
- `thead` is accessible as a closure variable in the same scope as `applySelectionToDOM` (confirmed — it is declared at the top of `createGrid`).
- `--color-text-heading` provides sufficient contrast against `--color-header-bg` when used as background in both themes (to be verified in smoke path step 10).

## Tasks
- [ ] T-001 Create and checkout a local branch: `git checkout -b feature/selection-header-highlight`

- [ ] Implement: Chunk 1 — extend applySelectionToDOM + CSS
  - [x] T-010 In `src/grid.ts`, extend `applySelectionToDOM()`: after the existing `cell--selected` loop, derive `activeColIdxs` and `activeModelIds` from `selectedCells`; toggle `col-header--active` on `thead th.col-header[data-col-index]`; toggle `gutter--cell-active` on `tbody td.gutter[data-model-id]`
  - [x] T-011 In `src/styles/grid.css`, add `.col-header--active` (background: `--color-text-heading`, color: `--color-header-bg`) and `.grid tbody td.gutter--cell-active` + even-row override (same inverted pattern as `gutter--row-selected`)

- [ ] Quality gate
  - [ ] T-900 Run formatters
  - [ ] T-901 Run linters
  - [ ] T-902 Run tests

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Ensure all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)

## Open Questions
- None.

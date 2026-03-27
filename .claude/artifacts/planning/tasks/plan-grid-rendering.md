# Plan: Grid Rendering (Display Only)

## Metadata
- Date: 2026-03-27
- Backlog item: Grid rendering (display only)
- Feature slug: grid-rendering

## Context
- Intended outcome: The page renders a fully populated, scrollable spreadsheet-like grid showing all MSX models and columns. Header rows (group names, column names) and the left gutter (row numbers) are sticky. Null values show as —. Cell text overflows with ellipsis and a native tooltip. A toolbar strip sits below the page header with placeholder ⊞ Columns and ⌃ Filters buttons. No interactive features (sort, filter, select) are implemented in this feature.

## Functional Snapshot
- Problem: The page shows only a header bar with no data. Users cannot see any model specifications. Every subsequent interactive feature requires a rendered grid to operate on.
- Target user: MSX enthusiasts / collectors opening the page for the first time to compare model specs.
- Success criteria (observable):
  - All models in MSX_DATA appear as rows (10 in seed data)
  - All 29 columns appear under their 8 group headers
  - Left gutter shows row numbers
  - Group header cells span their child columns
  - Column headers row displays column labels
  - Null/missing values render as `—` in muted text color
  - Long cell values clip with ellipsis; full value shown in native tooltip
  - Filter row is rendered but invisible by default
  - Toolbar strip shows `⊞ Columns` and `⌃ Filters` placeholder buttons (non-functional)
  - Page header shows data timestamp from `MSX_DATA.generated`
  - `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
  - No hardcoded hex in any CSS file other than `theme.css`
- Primary user flow:
  1. User opens `docs/index.html`
  2. Grid renders immediately with all models and columns visible
  3. User scrolls horizontally to see all column groups; sticky gutter and headers stay fixed
  4. User scrolls vertically through model rows; sticky header rows stay fixed
- Must never happen:
  - Grid not rendering when `MSX_DATA` is present and valid
  - Hardcoded hex colors in `grid.css` or `toolbar.css`
  - Group header spanning the wrong number of columns
  - `values[]` data misaligned with column definitions (column positions must match COLUMNS array order)
- Key edge cases:
  - `null` cell value → render `—` in `var(--color-text-muted)`, no `title` attribute
  - Non-null cell value that is an empty string → treat as null, render `—`
  - Very long string value (e.g. connectivity ports) → ellipsis clip + `title` tooltip
  - Boolean `true`/`false` values → render as string `"Yes"` / `"No"`
  - `MSX_DATA` missing → show `Failed to load data.` error, do not render grid
- Business rules:
  - Column order in the grid matches the `COLUMNS` array index order (already guaranteed by `values[]` positional alignment)
  - Group order follows `GroupDef.order` (ascending)
  - Row heights: group header 28px, column header 28px, filter row 28px (hidden), data rows 24px
  - Left gutter 32px wide; row numbers are 1-based
  - Toolbar strip 32px high
  - All 4 header rows + left gutter remain sticky during both axes of scroll
  - The grid body (below toolbar + headers) scrolls freely in both directions
- Integrations:
  - `window.MSX_DATA` — data already loaded by `data.js` script tag before `bundle.js`
  - Failure behavior: `MSX_DATA` undefined → existing error handling in `main.ts` shows error message; grid module is never called
- Non-functional requirements:
  - WCAG 2.1 AA — all text ≥ 4.5:1 contrast (inherited from theme tokens)
  - No CSS transitions/animations on grid render
  - Grid must be usable at 1280px viewport width minimum
- Minimal viable increment (MVI): Static read-only grid with all rows, columns, groups, gutter, null/em-dash, overflow tooltip, toolbar strip placeholders, and hidden filter row.
- Deferred:
  - Column group collapse/expand (chevron renders as static ▼ but has no click handler)
  - Sort indicators (column headers render text only, no ↑/↓)
  - Filter row inputs (row structure rendered but empty — no `<input>` elements)
  - Toolbar button functionality (⊞ Columns, ⌃ Filters render but do nothing)
  - Row show/hide gutter indicator
  - Cell hover/selection styles (tokens defined, no event handlers)
  - Status bar (bottom 24px) — deferred to clipboard copy feature

## Executable Specification (Gherkin)

```gherkin
Feature: Grid rendering (display only)
  The page renders MSX model data as a scrollable spreadsheet-like grid.
  All models appear as rows; all columns appear under sticky group and column headers.
  The grid is read-only at this stage — no sort, filter, or selection.

  Background:
    Given MSX_DATA is loaded with 10 models and 29 columns across 8 groups

  Scenario: All models appear as rows with row numbers
    Given the page is opened
    When the grid renders
    Then 10 data rows are visible, one per model
    And the left gutter shows row numbers 1 through 10

  Scenario: Column group headers span their child columns
    Given the page is opened
    When the grid renders
    Then 8 group header cells are visible above the column headers
    And each group header cell spans exactly its number of child columns
    And group header cells appear in group order (Identity, Memory, Video, Audio, Media, CPU/Chipsets, Other, Emulation)

  Scenario: Null values are rendered as an em-dash
    Given a model has a null value for the "FM Chip" column
    When the grid renders that cell
    Then the cell displays "—"
    And the cell text is styled in muted color

  Scenario: Long cell content is clipped with a native tooltip
    Given a model has a "Connectivity/Ports" value longer than the column width
    When the grid renders that cell
    Then the visible cell text ends with an ellipsis
    And hovering the cell shows the full value in a native browser tooltip

  Scenario: Filter row is hidden by default
    Given the page is opened
    When the grid renders
    Then the filter row is not visible to the user

  Scenario: Toolbar strip shows placeholder buttons
    Given the page is opened
    When the grid renders
    Then a toolbar strip is visible below the page header
    And it contains a "⊞ Columns" button and a "⌃ Filters" button

  Scenario: Missing data file shows error instead of grid
    Given MSX_DATA is not defined at page load
    When the page loads
    Then no grid is rendered
    And the page displays an error message indicating data could not be loaded
```

## Baseline Gate
- Start from clean, green trunk.
- All npm commands exit 0 before branching.

## Architecture Fit
- Touch points:
  - `src/styles/toolbar.css` — new; toolbar strip layout + placeholder button styles; all via `var(--...)`
  - `src/styles/grid.css` — new; table, thead, tbody, tr, th, td styles; scrollable wrapper; sticky rows + gutter; alternating rows; ellipsis; null cell; all via `var(--...)`
  - `src/grid.ts` — new; `buildGrid(data: MSXData): HTMLElement` returns the fully rendered scrollable grid
  - `src/toolbar.ts` — new; `buildToolbar(): HTMLElement` returns the 32px toolbar strip
  - `src/main.ts` — updated; call `buildToolbar()` and `buildGrid()`, append to body; add data timestamp to header
  - `docs/` — rebuilt after final chunk
- Compatibility notes:
  - `values[]` is positionally aligned with `MSXData.columns[]` — do not sort or reorder the columns array before accessing values
  - Boolean tooth values in `values[]` must be coerced to `"Yes"` / `"No"` for display
  - The `<html data-theme>` attribute is already set by `initTheme()` before any DOM append — grid CSS tokens are immediately available

## Observability (Minimum Viable)
- Applicability: N/A — static client-side rendering, no server, no metrics infrastructure
- Failure modes:
  - `MSX_DATA` undefined → existing `console.error` in `main.ts`; error message rendered in page
  - `values[]` length mismatch with `columns[]` → cell silently renders as `—` (treat out-of-range index as null)

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): `npm run typecheck` (validates grid.ts and toolbar.ts types); `npm run lint` (no-console, no hardcoded hex)
- Tier 1 (if applicable): N/A — no DOM testing framework configured; visual correctness verified manually via `docs/index.html`
- Tier 2 (if applicable): N/A

## Data and Migrations
- Applicability: N/A — reads `window.MSX_DATA` as-is; no schema changes; no localStorage; no migrations

## Rollout and Verify
- Applicability: N/A — local development only; `docs/` committed for GitHub Pages
- Manual validation steps (see Validation Script below)

## Cleanup Before Merge
- Remove any debug `console.log` statements
- Confirm no hardcoded hex in `grid.css` or `toolbar.css`
- All commits follow Conventional Commits

## Definition of Done
- `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
- Opening `docs/index.html` via `file://` shows the full grid populated with seed data
- Group headers span correct columns; column headers show correct labels
- Row numbers appear in left gutter
- At least one null cell shows `—` in muted text
- A long cell value clips with ellipsis and shows full value on hover
- Toolbar strip shows ⊞ Columns and ⌃ Filters buttons (non-functional)
- Filter row not visible on load
- Page header shows `MSX_DATA.generated` date
- Zero hardcoded hex in `grid.css` and `toolbar.css`

## Chunks

### Chunk 1: CSS scaffold
- User value: All grid visual rules in place; developer can inspect layout without writing DOM
- Scope: `src/styles/toolbar.css` (toolbar strip + placeholder button styles), `src/styles/grid.css` (scrollable wrapper, table, thead, tbody, sticky positioning, alternating rows, left gutter, cell overflow, null cell color, filter row hidden state)
- Ship criteria: `npm run build` exits 0; no hardcoded hex
- Rollout notes: none

### Chunk 2: Toolbar strip + header timestamp
- User value: Toolbar strip is visible below the page header; data freshness date shown
- Scope: `src/toolbar.ts` (buildToolbar()); update `src/main.ts` to append toolbar and add `.generated` date to header title span
- Ship criteria: `npm run typecheck` + `npm run lint` exit 0; toolbar strip visible in both themes

### Chunk 3: Grid DOM — group headers, column headers, filter row, data rows, left gutter
- User value: Full grid visible with all models and columns; null → em-dash; overflow tooltip
- Scope: `src/grid.ts` (buildGrid(data)); update `src/main.ts` to call buildGrid and append it; import grid.css
- Ship criteria: All 10 seed models visible; group headers spanning correct columns; null values show `—`; long values clip; filter row hidden; `npm run build` exits 0

### Chunk 4: Update docs/ build
- User value: GitHub Pages / file:// deployment reflects the new grid
- Scope: `npm run build` → commit `docs/` output
- Ship criteria: `docs/bundle.js` updated; `npm run build` exits 0

## Relevant Files (Expected)
- `src/styles/toolbar.css` — toolbar strip layout and placeholder button styles
- `src/styles/grid.css` — all table/grid styles; sticky rows; alternating rows; overflow; null cell; filter row hidden
- `src/toolbar.ts` — `buildToolbar(): HTMLElement`
- `src/grid.ts` — `buildGrid(data: MSXData): HTMLElement`
- `src/main.ts` — updated to call buildToolbar(), buildGrid(), add timestamp to header
- `docs/` — rebuilt after Chunk 4

## Assumptions
- No DOM testing framework (Vitest + jsdom) is configured — visual validation is manual via `docs/index.html`
- `values[]` positions align 1:1 with `MSXData.columns[]` — this invariant is guaranteed by the data schema and need not be re-validated in the renderer
- Boolean values in `values[]` are rendered as "Yes" / "No" (no boolean columns in current seed have `true`/`false`, but the rule is applied defensively)
- The chevron (▼) in group headers is static text at this stage; no click handler added until "Column group collapse/expand"
- Placeholder toolbar buttons render as styled `<button>` elements with `disabled` attribute or `pointer-events: none` until their respective features are implemented — to avoid confusing the user, add `title="Coming soon"` tooltips

## Validation Script
1. Run `npm run build` — exits 0
2. Open `docs/index.html` via `file://` in Chrome
3. Verify: dark background, header bar with `◐` button and a date string (e.g. "2026-03-27")
4. Verify: toolbar strip row visible below header with `⊞ Columns` and `⌃ Filters` buttons
5. Verify: grid table rendered below toolbar; 8 group header cells visible in the top row
6. Verify: column names visible in the second sticky header row
7. Verify: 10 data rows visible; left gutter shows 1–10
8. Scroll right → sticky left gutter stays; all group/column headers remain at top
9. Scroll down past visible rows → group/column headers stay sticky at top
10. Locate a cell with null value → confirm it shows `—` in muted text
11. Locate a cell with a long string → confirm ellipsis; hover to confirm full value in tooltip
12. Confirm filter row is not visible
13. `npm run typecheck` → exits 0
14. `npm run lint` → exits 0
15. Grep `src/styles/grid.css src/styles/toolbar.css` for `#` → expect 0 matches

## Tasks

- [x] T-001 Create and checkout a local branch `feature/grid-rendering`

- [ ] Chunk 1: CSS scaffold
  - [x] T-010 Create `src/styles/toolbar.css`: `.toolbar` strip (flexbox, 32px height, sticky, `--color-header-bg` bg, `--color-border` bottom border, gap 8px, padding 0 12px); `.toolbar__btn` placeholder button reset (same style as `.theme-toggle` but with label text, `disabled` cursor, muted color)
  - [x] T-011 Create `src/styles/grid.css`: `.grid-wrap` (overflow: auto; height: calc(100vh - 68px)); `.grid` table (border-collapse: collapse; width: max-content); group header `th` (height 28px, sticky top: 0, `--color-header-bg`, uppercase 11px, `--color-text-muted`, border-right `--color-border`); column header `th.col-header` (height 28px, sticky top: 28px, `--color-header-bg`, 11px, `--color-text-heading`, uppercase); filter row `tr.filter-row` (display: none; height 28px, sticky top: 56px); data `td` (height 24px, 12px, `--color-text`, `--color-surface`, padding 0 6px, border-bottom `--color-border`, max-width: 160px, overflow: hidden, text-overflow: ellipsis, white-space: nowrap); alternating rows (`tr:nth-child(even) td`: `--color-surface-alt`); gutter cell `.gutter` (width 32px, sticky left: 0, `--color-gutter-bg`, `--color-gutter-text`, 10px, text-align: right, padding 0 4px)
  - [x] T-012 Verify `npm run build` exits 0; grep `src/styles/grid.css src/styles/toolbar.css` for `#` → 0 matches
  - [x] T-013 Commit: `style: add grid and toolbar CSS scaffold`

- [ ] Chunk 2: Toolbar strip + header timestamp
  - [x] T-020 Create `src/toolbar.ts`: export `buildToolbar(): HTMLElement` — returns a `<div class="toolbar">` with two `<button class="toolbar__btn" disabled title="Coming soon">` elements labelled `⊞ Columns` and `⌃ Filters`
  - [x] T-021 Update `src/main.ts`: import `toolbar.css`; call `buildToolbar()` and `document.body.appendChild(toolbar)` immediately after the header; also update the header title span to include `MSX_DATA.generated` as a muted date suffix (e.g. `MSX Models DB  ·  2026-03-27`)
  - [x] T-022 Verify `npm run typecheck` exits 0 and `npm run lint` exits 0
  - [x] T-023 Commit: `feat: add toolbar strip with placeholder buttons and data timestamp`

- [ ] Chunk 3: Grid DOM
  - [x] T-030 Create `src/grid.ts`: export `buildGrid(data: MSXData): HTMLElement` — builds and returns `.grid-wrap > table.grid`; internally constructs:
    - `<thead>`: row 1 = group header `<th>` cells (one per group, `colspan` = group's column count, static `▼` suffix, gutter cell at position 0); row 2 = column header `<th class="col-header">` cells (one per column, gutter cell at position 0); row 3 = `<tr class="filter-row">` with empty `<td>` cells (hidden via CSS)
    - `<tbody>`: one `<tr>` per model; first cell is `<td class="gutter">` with 1-based row index; remaining cells are `<td>` per column — value from `model.values[i]`; null/empty string/undefined → `—` (no `title`); boolean → `"Yes"`/`"No"`; all others → `String(value)` with `title` attribute set to full value
  - [x] T-031 Update `src/main.ts`: import `grid.css`; import `buildGrid` from `./grid.js`; call `buildGrid(window.MSX_DATA)` and append to body inside the MSX_DATA branch
  - [x] T-032 Verify `npm run typecheck` exists 0, `npm run lint` exits 0, `npm run build` exits 0; open `docs/index.html` — all 10 rows visible, group headers correct, null cells show `—`
  - [x] T-033 Commit: `feat: render full grid with group headers, column headers, data rows, and left gutter`

- [ ] Chunk 4: Update docs/ build
  - [x] T-040 Run `npm run build` to ensure `docs/` output is current
  - [x] T-041 Commit: `chore: update docs/ build output with grid rendering`

- [ ] Quality gate
  - [x] T-900 `npm run lint` — 0 errors
  - [x] T-901 `npm run typecheck` — 0 errors
  - [x] T-902 `npm test -- --run` — exits 0
  - [x] T-903 `npm run build` — exits 0
  - [x] T-904 Grep `src/styles/grid.css src/styles/toolbar.css` for hex — 0 matches

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Confirm all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge fast-forward only

## Open Questions
- None

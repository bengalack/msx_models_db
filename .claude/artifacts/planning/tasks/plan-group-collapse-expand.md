# Plan: Column Group Collapse / Expand

## Metadata
- Date: 2026-03-27
- Backlog item: Column group collapse / expand
- Feature slug: group-collapse-expand

## Context
- Intended outcome: Users can click a group header to collapse all child columns, reducing visual noise when comparing a focused subset of attributes. Click again to expand.

## Functional Snapshot
- Problem: With 29 columns across 8 groups, the grid is wide. Users comparing only a few attribute categories must scroll past irrelevant groups. There is no way to temporarily hide an entire group.
- Target user: Researcher or enthusiast comparing MSX2/2+/turboR models, focused on one or two attribute categories at a time.
- Success criteria (observable):
  - Clicking any group header collapses that group's data columns (they become invisible); colSpan on the header shrinks to 1; chevron shows ▶
  - Clicking the same group header again restores all data columns; colSpan restored to original; chevron shows ▼
  - All groups can be collapsed simultaneously; the group header row (with ▶ stubs) remains visible and sticky
  - Expanding restores columns in the same position (no reordering)
  - Row data alignment (positional values[]) is never corrupted — only CSS visibility changes
- Primary user flow:
  1. User sees the grid with all 8 groups expanded (▼ on each)
  2. User clicks a group header they want to hide (e.g. "Video")
  3. All columns under "Video" disappear; "Video" header shrinks to a narrow stub with ▶
  4. User clicks the stub again → columns reappear, ▼ restored
- Alternate flows:
  - User collapses all groups → only 8 stubs visible in the group header row; tbody rows collapse to gutter-only width
  - User rapidly clicks same group → each click toggles consistently (no stuck state)
- Must never happen:
  - Values misalignment — hiding columns must never shift which value maps to which column (DOM-only operation via display:none)
  - A collapsed group header becoming unclickable (colSpan=0 or removed from DOM)
  - Sticky header rows losing correct top offset during collapse/expand
- Key edge cases:
  - All groups collapsed → group header row still visible with 8 narrow stubs; page is still usable
  - Single-column group → collapses/expands identically to multi-column groups
  - Rapid toggle → Set<number> state is always consistent with DOM
- Business rules:
  - Group-level collapse only — individual column visibility is a separate feature (Column show/hide)
  - Hidden-column indicator in group header (when individual columns are hidden) is deferred to Column show/hide feature
  - Collapsed state is NOT persisted to URL in this feature (deferred to URL state codec)
- Integrations: None — pure client-side DOM manipulation; no external data flows
- Non-functional requirements:
  - Privacy/Security: N/A
  - Performance: Collapse/expand completes in a single synchronous DOM update; no reflow cascade
  - Reliability: Collapsed state survives scroll but not page reload (localStorage not used; URL sync deferred)
- Minimal viable increment (MVI): Click to collapse, click to expand; chevron indicator; colSpan update; all cells hidden via display:none only
- Deferred:
  - URL state codec integration (collapsed groups in hash)
  - Hidden-column indicator in group header strip (belongs to Column show/hide)
  - Keyboard accessibility for collapse (will be addressed in a later accessibility pass)

## Executable Specification (Gherkin)

Feature: Column group collapse / expand
  A user can click a group header to collapse all child columns in that group,
  reducing grid width, and click again to expand them.

  Scenario: Collapse a group
    Given the grid is rendered with all groups expanded
    When the user clicks a group header
    Then all data columns in that group disappear from view
    And the group header shrinks to a 1-column stub
    And the chevron changes from ▼ to ▶

  Scenario: Expand a previously collapsed group
    Given a group header is collapsed (showing ▶)
    When the user clicks that group header
    Then all data columns in that group reappear in their original positions
    And the group header colSpan is restored to the original column count
    And the chevron changes from ▶ to ▼

  Scenario: All groups collapsed simultaneously
    Given the grid is rendered with all groups expanded
    When the user collapses every group in sequence
    Then each group header shows a 1-column stub with ▶
    And the group header row remains visible and sticky
    And data rows have only the gutter column visible

  Scenario: Single-column group collapses correctly
    Given a group with exactly one data column
    When the user clicks that group header
    Then the single column disappears
    And the group header shows a stub with ▶

  Scenario: Collapsed state does not corrupt row data alignment
    Given the user collapses one or more groups
    When the user expands them again
    Then each column displays the same values as before collapse

  Scenario: Collapsed state is not persisted across page reload
    Given the user has collapsed one or more groups
    When the user reloads the page
    Then all groups are expanded (default show-all state)

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points: `src/grid.ts` (add data attributes + click handlers), `src/styles/grid.css` (cursor + collapsed visual state)
- Collapsed state lives in a `Set<number>` in `buildGrid` closure scope — no separate state module needed at this stage (URL codec will lift it later)
- Compatibility notes: `values[]` positional alignment must not be touched — cells gain `display:none` only; `colSpan` on the group header `<th>` changes but does not alter sibling row structure

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM interaction; no server, no async, no failure modes to instrument

## Testing Strategy (Tier 0/1/2)
- Tier 0: No unit tests in this feature — collapse/expand is pure DOM mutation; Vitest is not yet set up for DOM (jsdom). Covered by manual smoke path below.
- Tier 1: N/A
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — no data schema changes; collapsed state is in-memory only

## Rollout and Verify
- Applicability: Required
- Strategy: All-at-once (static file, served via GitHub Pages or file://)
- Verify (smoke path):
  1. Open `docs/index.html` in a browser
  2. Click a group header → columns disappear, stub shows ▶
  3. Click the stub → columns reappear, ▼ restored
  4. Collapse all 8 groups → only stubs visible in header row
  5. Scroll grid while groups are collapsed → sticky headers remain correct
  6. Reload page → all groups expanded
- Signals to watch: colSpan restores correctly; no horizontal scrollbar jump; no misaligned data after expand

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

### Chunk 1 — Collapse/expand logic + CSS (T-100 to T-106)
- User value: Users can click group headers to collapse and expand column groups
- Scope:
  - `src/grid.ts`: add `data-col-group` to col-header/filter/data cells; add `data-group-id` + `data-col-count` to group header `<th>`; wire click handler in `buildGrid` that toggles collapsed state
  - `src/styles/grid.css`: `.group-header { cursor: pointer; }` + hover fill + `.group-header.collapsed` width/padding
- Ship criteria: Clicking any group header in the browser collapses and expands it; chevron toggles ▼/▶; all data cells hidden/shown correctly; sticky rows unaffected

### Chunk 2 — Build output (T-200)
- User value: Built `docs/bundle.js` updated so the feature is live in the deployed page
- Scope: `npm run build` → commit `docs/bundle.js`
- Ship criteria: `docs/bundle.js` reflects chunk 1 changes; build exits 0

## Tasks

### T-100 — Add data-col-group to col-header cells
- [x] In `buildColHeaderRow`, set `th.dataset.colGroup = String(col.groupId)` on each column `<th>`

### T-101 — Add data-col-group to filter-row cells
- [x] In `buildFilterRow`, accept `columns: ColumnDef[]` parameter (replace `columns.length` loop with proper array); set `td.dataset.colGroup = String(columns[i].groupId)` on each `<td>`

### T-102 — Add data-col-group to data-row cells
- [x] In `buildDataRow`, set `td.dataset.colGroup = String(columns[i].groupId)` on each data `<td>` (already using index loop — add one line per cell)

### T-103 — Add data attributes to group header cells
- [x] In `buildGroupHeaderRow`, set `th.dataset.groupId = String(group.id)` and `th.dataset.colCount = String(groupCols.length)` on each group `<th>`

### T-104 — Wire collapse/expand click handler in buildGrid
- [x] In `buildGrid`, after building `thead`, query all group header `<th>` elements
- [x] Attach a click listener to each that:
  1. Reads `groupId` and `colCount` from the element's dataset
  2. Toggles a `Set<number>` (`collapsedGroups`) for that groupId
  3. If now collapsed: `th.colSpan = 1`; `th.classList.add('collapsed')`; `th.querySelector('.chevron')!.textContent = '▶'`; query `table.querySelectorAll('[data-col-group="<groupId>"]')` and set `style.display = 'none'`
  4. If now expanded: `th.colSpan = colCount`; `th.classList.remove('collapsed')`; `th.querySelector('.chevron')!.textContent = '▼'`; restore `style.display = ''`

### T-105 — CSS: group-header interactive state
- [x] In `src/styles/grid.css`, add to `.group-header`: `cursor: pointer; user-select: none;`
- [x] Add `.group-header:hover { background: var(--color-hover); }` (reuse existing hover token)
- [x] Add `.group-header.collapsed { color: var(--color-text-muted); }` to visually dim the stub

### T-106 — Commit chunk 1
- [x] `git add src/grid.ts src/styles/grid.css`
- [x] `git commit -m "feat: collapse/expand column groups on group header click"`

### T-200 — Build and commit docs/bundle.js
- [x] `npm run typecheck && npm run lint && npm run build`
- [x] Verify build exits 0 and bundle size is reasonable
- [x] `git add docs/bundle.js && git commit -m "chore: update docs/ build output with group collapse/expand"`

### T-950 — Smoke test
- [x] Open `docs/index.html`; click each group header; verify collapse/expand behaviour

### T-951 — Squash, merge, clean up
- [x] Squash branch commits into one logical commit
- [x] Fast-forward merge to main
- [x] Delete feature branch

### T-952 — Update backlog
- [x] Move "Column group collapse / expand" to "In product (shipped)" in `product-backlog.md`

## Relevant Files (Expected)
- `src/grid.ts` — all DOM construction functions need data attribute additions; buildGrid needs click handler
- `src/styles/grid.css` — add cursor/hover/collapsed styles to .group-header
- `docs/bundle.js` — built output; committed after build

## Notes
- `data-col-group` uses numeric group IDs (matching `GroupDef.id`) as strings in the data attribute
- The `collapsedGroups: Set<number>` lives in `buildGrid` closure scope; it is NOT exported — URL codec is a later feature that will lift state management to a shared module
- `buildFilterRow` currently does not receive individual column definitions (just uses `columns.length`). T-101 changes the logic to use the columns array directly so groupId is available
- Do not use `visibility: hidden` or `width: 0` — `display: none` is the correct CSS property for removing cells from table layout

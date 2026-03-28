# Plan: Clipboard Copy

## Metadata
- Date: 2026-03-27
- Backlog item: Clipboard copy
- Feature slug: clipboard-copy

## Context
- Intended outcome: Pressing Ctrl+C / Cmd+C copies the currently selected cells as TSV to the clipboard. A status bar at the bottom of the page confirms the action with "Copied N cell(s)".

## Functional Snapshot
- Problem: Cell selection is now in place but has no output path. A researcher who has selected a block of cells cannot get those values out of the page. The goal is standard spreadsheet copy behaviour: Ctrl+C writes a TSV string to the clipboard so values can be pasted directly into a spreadsheet or text editor.
- Target user: Researcher who has selected a region of the grid and wants to paste it into a spreadsheet for further analysis.
- Success criteria (observable):
  - Pressing Ctrl+C (or Cmd+C on Mac) while cells are selected writes a TSV string to the clipboard
  - A status bar at the very bottom of the viewport shows "Copied N cell(s)" briefly after a successful copy
  - Pressing Ctrl+C with nothing selected does nothing (no error, no status update)
  - TSV format: columns in a row tab-separated, rows newline-separated; column order follows visible order (left to right by colIdx); row order follows visible sort order
  - Works in modern browsers via `navigator.clipboard.writeText`; falls back silently to `document.execCommand('copy')` when the async API is unavailable (e.g. file:// origins in some browsers)
- Primary user flow:
  1. User selects cells via click/drag/Shift+click
  2. User presses Ctrl+C / Cmd+C
  3. Clipboard receives TSV; status bar shows "Copied N cell(s)" for ~2 seconds
  4. User pastes into a spreadsheet
- Alternate flows:
  - No selection: Ctrl+C is a no-op; browser default copy (selected text) is not suppressed
  - Single cell selected: clipboard receives single value with no tab or newline; status shows "Copied 1 cell(s)"
  - Sparse (non-contiguous) selection via Ctrl+click: cells are emitted in row-major + col-major order; rows with no selected cells in between are skipped; no padding for gaps within a row (each row only emits its selected columns, tab-separated)
  - Selected cells include hidden or filtered-out rows: those model IDs are not in the visible DOM; they are still in `selectedCells` Set — skip them (only copy visible cells)
  - Selected cells in a hidden column: the colIdx is still in `selectedCells` — skip hidden cols in TSV output
- Must never happen:
  - Ctrl+C suppressed when no cells are selected (must not hijack browser's normal copy behaviour)
  - TSV emitting stale or wrong values (must read from `data.models`, not from cell innerText)
  - Status bar persisting indefinitely if another copy is triggered quickly (timer must be reset)
  - JS error if clipboard API rejects (e.g. permissions denied) — catch and silently fall back
- Key edge cases:
  - All selected cells become hidden → copy produces no output; no error; no status update (nothing to copy)
  - Single model, multiple adjacent columns selected → one TSV row, multiple tab-separated values
  - Multiple models, single column selected → one value per line
  - `''` / `null` values → emit `—` (em dash) via `cellText()` consistent with display, OR emit empty string? **Decision: emit empty string for null/empty (not `—`) so pasted values are clean in spreadsheets**
- Business rules:
  - Only cells visible in the current DOM (via `tbody.querySelectorAll('tr[data-model-id]')`) are included in copy
  - Hidden columns (`hiddenCols`) are excluded from TSV output even if their keys are in `selectedCells`
  - Row order in TSV matches current visible sort order (not model array order)
  - Column order in TSV matches column index order (ascending `colIdx`)
  - Null/empty values emit as empty string in TSV (not `—`)
  - Ctrl+C with empty selection does not `e.preventDefault()` — browser's own copy still works
- MVI: Ctrl+C/Cmd+C copies visible selected cells as TSV; status bar "Copied N cell(s)"; Clipboard API with execCommand fallback; no copy on empty selection
- Deferred:
  - Column headers in copy output (first row is headers)
  - "Copy" button in toolbar
  - Keyboard shortcut customisation
  - URL state codec integration

## Executable Specification (Gherkin)

Feature: Clipboard copy
  A user can copy selected cells to the clipboard as TSV by pressing Ctrl+C.
  A status bar confirms the action.

  Scenario: Ctrl+C copies selected cells as TSV
    Given cells in rows "FS-A1GT" and "FS-A1ST", columns "CPU" and "RAM" are selected
    When the user presses Ctrl+C
    Then the clipboard contains a TSV string with two rows and two columns
    And the status bar shows "Copied 4 cell(s)"

  Scenario: Ctrl+C does nothing when no cells are selected
    Given no cells are selected
    When the user presses Ctrl+C
    Then the clipboard is unchanged
    And the status bar shows no message

  Scenario: Copy is skipped for hidden rows
    Given a cell in a hidden row is part of the selection
    When the user presses Ctrl+C
    Then the TSV output does not include values from the hidden row
    And the count in the status bar reflects only visible cells

  Scenario: Copy is skipped for hidden columns
    Given a cell in a hidden column is part of the selection
    When the user presses Ctrl+C
    Then the TSV output does not include values from the hidden column
    And the count in the status bar reflects only visible cells

  Scenario: Status bar resets timer on repeated copy
    Given a copy was made 1 second ago (status bar still showing)
    When the user presses Ctrl+C again
    Then the status bar resets and shows the new count for another 2 seconds

  Scenario: Null cell values are emitted as empty string in TSV
    Given a selected cell has no value (displays "—" in the grid)
    When the user presses Ctrl+C
    Then the TSV field for that cell is an empty string (not "—")

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- `git checkout -b feature/clipboard-copy`

## Architecture Fit

### Touch points

**`src/grid.ts`**
- New `copySelection(): string` function in `buildGrid` closure:
  - Gets visible row order: `Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]')).map(tr => Number(tr.dataset.modelId))`
  - Gets visible col indices: `data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i))`
  - Iterates visible rows in order; for each, finds selected colIdxs in the intersection of `selectedCells` keys and visible col indices; if any, emits a tab-joined row
  - Cell value lookup: `data.models.find(m => m.id === modelId)?.values[colIdx] ?? null`; emits empty string for null/empty (NOT `cellText()` — avoids `—`)
  - Returns TSV string (may be empty string if nothing visible is selected)
- Updated return type: add `copySelection: () => string`

**`src/main.ts`**
- Import `src/styles/statusbar.css`
- Build `statusBar` element (`<div class="status-bar">`) and `document.body.appendChild(statusBar)` after `gridEl`
- `showStatus(msg: string, durationMs = 2000)`: sets `statusBar.textContent = msg`, `statusBar.classList.add('status-bar--visible')`, clears any pending timer, sets `setTimeout` to remove `--visible` class and clear text
- Destructure `copySelection` from `buildGrid(...)` return value
- `document.addEventListener('keydown', ...)` for `(e.ctrlKey || e.metaKey) && e.key === 'c'`:
  - Call `copySelection()` → TSV string
  - If TSV is empty string, return without `e.preventDefault()`
  - Count cells: `tsv.split('\n').flatMap(row => row.split('\t')).length` — **actually count via `selectedCells` visible count inside `copySelection` and return it alongside TSV, OR count lines×cols** — simplest: return `{ tsv, count }` from `copySelection` or keep it as just `string` and count from the string. Use `string` + count from string: `tsv.split('\n').reduce((n, row) => n + row.split('\t').length, 0)`
  - Otherwise: `e.preventDefault()`; write to clipboard:
    ```
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(tsv).catch(() => execCommandFallback(tsv));
    } else {
      execCommandFallback(tsv);
    }
    ```
  - `execCommandFallback(text)`: create `<textarea>`, set value, append to body, `select()`, `document.execCommand('copy')`, remove textarea
  - Call `showStatus(\`Copied ${count} cell(s)\`)`

**`src/styles/statusbar.css`** (new file)
- `.status-bar` — `position: fixed; bottom: 0; left: 0; right: 0; height: 24px; ...`; hidden by default (`opacity: 0; pointer-events: none; transition: opacity 0.15s`)
- `.status-bar--visible` — `opacity: 1`

### Compatibility
- `copySelection()` is additive to the return type; no existing callers break
- The Ctrl+C keydown does not conflict with any existing keydown handlers (`Escape`, picker `Escape`)
- `execCommandFallback` is self-contained; no shared state with grid or picker

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM

## Testing Strategy
- Tier 0: Manual smoke path only.

## Data and Migrations
- Applicability: N/A — clipboard state is ephemeral

## Rollout and Verify
- Strategy: All-at-once (static file)
- Smoke path:
  1. Open `docs/index.html` — no status bar visible
  2. Click one data cell → Ctrl+C → status bar shows "Copied 1 cell(s)"; paste into text editor → correct value (no `—` for null cells)
  3. Click+drag across 2×3 block → Ctrl+C → "Copied 6 cell(s)"; paste → 2 tab-separated rows
  4. Press Ctrl+C again → status bar resets to another 2-second display
  5. Press Escape to clear selection → Ctrl+C → no status bar, clipboard unchanged
  6. Sort by a column, select cells, Ctrl+C → paste confirms row order matches sorted order
  7. Filter rows, select cells, Ctrl+C → hidden rows not in TSV
  8. Hide a column, Shift+click across that column's position, Ctrl+C → TSV skips the hidden column
  9. Status bar disappears after ~2 seconds
  10. Dark + light themes: status bar readable in both

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

### Chunk 1 — TSV builder + status bar DOM (T-100 to T-102)
- User value: `copySelection()` is wired and returns correct TSV; status bar element is present and styled in both themes
- Scope: `copySelection()` in `buildGrid`; `status-bar.css`; status bar element in `main.ts`; `showStatus()` helper

- Tasks:
  - [x] T-100: Add `copySelection(): string` to `buildGrid` closure — iterates visible rows/cols, emits TSV with empty string for null values; add to return type
  - [x] T-101: Create `src/styles/statusbar.css` with `.status-bar` (fixed bottom, 24px, hidden) and `.status-bar--visible` (opacity: 1); import in `main.ts`; append `<div class="status-bar">` to `document.body`
  - [x] T-102: Add `showStatus(msg, duration?)` helper in `main.ts` with timer-reset logic; wire it to a no-op test call (to be replaced with Ctrl+C in T-200)

### Chunk 2 — Clipboard write + Ctrl+C handler (T-200 to T-201)
- User value: Pressing Ctrl+C actually copies to the system clipboard and shows the status bar
- Scope: `document keydown` handler in `main.ts`; `navigator.clipboard` + `execCommand` fallback

- Tasks:
  - [x] T-200: Add `execCommandFallback(text: string): void` in `main.ts`; add `document keydown` handler for `(ctrlKey || metaKey) && key === 'c'`: call `copySelection()`, early-return if empty, `e.preventDefault()`, write to clipboard with async API + fallback, call `showStatus()`
  - [x] T-201: Remove the no-op `showStatus` test call from T-102 if added; verify smoke path; no debug logs

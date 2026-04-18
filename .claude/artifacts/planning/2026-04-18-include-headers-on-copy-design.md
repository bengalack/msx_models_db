# Design: Include Headers on Copy

## Metadata
- Date: 2026-04-18
- Author: bengalack
- Status: Approved

## Summary

Add a toolbar toggle button "Include headers on copy" that, when active, prepends a header row (column short labels) to the TSV output produced by CTRL+C. Toggle state is local only — not saved to the URL.

## Button

- Label: `" Include headers on copy"`
- Icon: `fa fa-plus` (always, both states)
- Position: between `↻ Reset view` and `? Help` in the toolbar
- Toggle behaviour: identical to Filters — `toolbar__btn--active` class applied when ON
- Default state: OFF

## Copy behaviour

`copySelection(includeHeaders?: boolean): string` in `grid.ts`:

- When `includeHeaders` is false/absent: existing behaviour unchanged
- When `includeHeaders` is true and selection is non-empty: prepend one tab-joined line of `col.shortLabel ?? col.label` for each selected visible column, in visible order — same column set as the data rows
- When selection is empty: return `''` regardless of flag (no phantom header row)

## State management

- `let headersOnCopy = false` in `main.ts`
- `handleHeadersCopyToggle()` flips the boolean and toggles `toolbar__btn--active`
- Keydown handler passes `copySelection(headersOnCopy)`
- `handleResetView()` does **not** reset this toggle — it is not a view-state item
- URL codec: no changes

## Files changed

| File | Change |
|------|--------|
| `src/toolbar.ts` | Add `onHeadersCopyToggle` param, create button, return `headersCopyBtn` |
| `src/grid.ts` | Add `includeHeaders?` param to `copySelection()` |
| `src/main.ts` | Wire toggle, pass flag to `copySelection` |
| `tests/web/copy-headers.test.ts` | New test file |
| `.claude/artifacts/planning/product-requirements.md` | Add FR entry |
| `.claude/artifacts/planning/ux-design-guide.md` | Update Toolbar and Clipboard copy sections |

## Test cases

1. `copySelection(false)` with selection → no header row
2. `copySelection(true)` with selection → first row is tab-joined short labels matching selected columns
3. `copySelection(true)` with no selection → `''`
4. Non-contiguous column selection → header row columns match data rows exactly

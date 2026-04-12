# Plan: Column Cell Shading (feature slug: column-cell-shading)

## Context
- PRD: `.claude/artifacts/planning/tasks/prd-column-cell-shading.md`
- Add a `shaded` boolean flag to the column definition stack so certain columns render with a subtle tinted background and bold text in the grid.

## Tasks

### Phase 1 — Data model
- [x] Add `shaded: bool = False` to the `Column` dataclass in `scraper/columns.py` (after `truncate_limit`, before `hidden`)
- [x] Set `shaded=True` on all Column instances whose key matches `slotmap_*_1_*` and `slotmap_*_3_*` (IDs 34–37, 50–53, 66–69, 82–85 and 42–45, 58–61, 74–77, 90–93)

### Phase 2 — Serialization
- [x] In `scraper/build.py` js_columns loop, after `truncateLimit` block, add `if col.shaded: entry["shaded"] = True`

### Phase 3 — TypeScript type
- [x] Add `shaded?: boolean` to `ColumnDef` in `src/types.ts`, after `truncateLimit?: number`

### Phase 4 — Rendering
- [x] In `src/grid.ts` `buildDataRow()`, after the `FROZEN_COL_COUNT` block, add `if (col.shaded) td.classList.add('col-shaded')`
- [x] In `src/styles/grid.css`, add `.grid tbody td.col-shaded` (odd row background + bold) and `.grid tbody tr:nth-child(even) td.col-shaded` (even row background) rules
- [x] In `src/styles/theme.css`, define `--color-surface-shaded` and `--color-surface-shaded-alt` in both `[data-theme="dark"]` and `[data-theme="light"]`

### Phase 5 — Tests
- [x] `tests/scraper/test_columns_slotmap.py`: assert all shaded columns match `slotmap_*_1_*` or `slotmap_*_3_*` pattern (no hard count)
- [x] `tests/scraper/test_build.py`: assert shaded columns serialize `"shaded": True`; non-shaded columns omit key — expected set derived from `active_columns()`
- [x] `tests/web/col-shading.test.ts`: Vitest DOM test — fake ColumnDef with one shaded + one non-shaded; assert `col-shaded` class present/absent

## Decisions
- `shaded` omitted from JSON when `False` (same pattern as `linkable`)
- CSS class: `col-shaded`; data cells (`<td>`) only — no header cells
- Two CSS variables per theme (odd + even) to preserve alternation without specificity tricks
- Tests must never assert a hard count of shaded columns — derive expected set from `active_columns()` at test time

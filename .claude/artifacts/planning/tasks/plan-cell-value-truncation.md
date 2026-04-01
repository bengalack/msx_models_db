# Plan: Cell Value Truncation

## Metadata
- Date: 2026-04-01
- Backlog item: Cell value truncation
- Feature slug: cell-value-truncation

## Context
- Intended outcome: Long cell values in the Manufacturer and Model columns are clipped to a readable length with a `…` suffix; the full value is always accessible via a native hover tooltip. Sorting and clipboard copy are unaffected.

## Functional Snapshot
- Problem: Model names like "National CF-2700 (Japan)" and manufacturer names like "Spectravideo" overflow their columns, either causing layout distortion or being silently clipped by CSS with no indication of the missing text.
- Target user: Any grid user who hovers a truncated Manufacturer or Model cell to read the full value, and any user who copies cells expecting the full, untruncated value.
- Success criteria (observable):
  - Cells in the Manufacturer and Model columns whose string value is longer than 10 characters display the first 9 characters followed by `…`.
  - Hovering a truncated cell shows a native tooltip with the full value.
  - Hovering a truncated Model cell with a URL link shows `"<full model name> — <url>"`.
  - Sorting by Manufacturer or Model produces the same order as before this feature.
  - Copying truncated cells via CTRL+C returns the full, untruncated value.
  - Non-truncated cells (≤ 10 characters) are displayed unchanged with no tooltip from this feature.
- Primary user flow:
  1. User opens the page; grid renders with Manufacturer and Model columns.
  2. Values longer than 10 chars display as `<9 chars>…`.
  3. User hovers a truncated cell → native tooltip shows the full value (or full value + URL for Model).
  4. User sorts by Manufacturer or Model → order is alphabetical on the full value.
  5. User selects and copies a truncated cell → clipboard contains the full value.
- Must never happen:
  - Clipboard copy returns the truncated display string instead of the full value.
  - Sort order changes as a result of this feature.
  - A cell value of exactly 10 characters gets truncated.
  - A value shorter than 4 characters (less than `limit − 1` meaningful chars) produces a tooltip-only cell with no visible content.
- Key edge cases:
  - Value length == limit (10) → display unchanged, no tooltip from this feature.
  - Value length == limit + 1 (11) → display `<9 chars>…`, tooltip shows full value.
  - Value length == 1 → display unchanged.
  - `truncate_limit = 0` on a column → no truncation, no change from current behavior.
  - Model cell with URL, value length > 10 → `a.title = "full name — url"`.
  - Model cell with URL, value length ≤ 10 → `a.title = url` (unchanged from current behavior).
- Business rules:
  - Truncation formula: display `text.slice(0, truncateLimit - 1) + '…'` when `text.length > truncateLimit`.
  - Full value stored in `td.dataset.fullValue` only when truncated.
  - Clipboard copy reads `model.values[c]` directly — no change required.
  - Sort reads `model.values[colIndex]` directly — no change required.
  - `truncate_limit` is a Python-side property on `Column`; serialised as `truncateLimit` (camelCase) in `data.js` only when non-zero.
  - Initial values: `manufacturer` (id=1) and `model` (id=2) both get `truncate_limit = 10`.
- Integrations: None — purely a rendering concern within the static web page and its data pipeline.
- Non-functional requirements:
  - Performance: No additional DOM queries per cell; `dataset.fullValue` set at render time, not on hover.
  - Reliability: Truncation must not affect URL codec, filter, or sort state.
- Minimal viable increment (MVI): Truncation in `buildDataRow` + tooltip in mouseenter handler + `truncate_limit` field in Python column config + serialised to `data.js`.
- Deferred:
  - Applying `truncate_limit` to columns other than Manufacturer and Model.
  - Custom tooltip component (native `title` is sufficient for desktop users).

## Executable Specification (Gherkin)

```gherkin
Feature: Cell value truncation
  When a column has a truncate_limit, long cell values are clipped with an ellipsis
  and the full value is always available via tooltip. Sorting and copy are unaffected.

  Background:
    Given the grid is loaded with Manufacturer truncate_limit=10 and Model truncate_limit=10

  Scenario: Value longer than limit is truncated with ellipsis
    Given a model with Manufacturer "Spectravideo"
    When the grid renders
    Then the Manufacturer cell displays "Spectravide…"
    And hovering the cell shows the tooltip "Spectravideo"

  Scenario: Value exactly at limit is not truncated
    Given a model with Manufacturer "Sharp Corp" (10 characters)
    When the grid renders
    Then the Manufacturer cell displays "Sharp Corp" with no truncation tooltip

  Scenario: Value shorter than limit is not truncated
    Given a model with Manufacturer "Canon"
    When the grid renders
    Then the Manufacturer cell displays "Canon" with no truncation tooltip

  Scenario: Truncated Model cell with URL shows combined tooltip
    Given a model with Model "National CF-2700" and a known msx.org URL
    When the grid renders
    Then the Model cell displays "National CF…"
    And the link tooltip is "National CF-2700 — https://www.msx.org/wiki/National_CF-2700"

  Scenario: Non-truncated Model cell with URL shows URL tooltip only
    Given a model with Model "Sony HB-10" (10 characters) and a known msx.org URL
    When the grid renders
    Then the Model cell displays "Sony HB-10" unchanged
    And the link tooltip is "https://www.msx.org/wiki/Sony_HB-10"

  Scenario: Clipboard copy returns untruncated value
    Given a model with Manufacturer "Spectravideo" displayed as "Spectravide…"
    When the user selects the Manufacturer cell and presses CTRL+C
    Then the clipboard contains "Spectravideo"

  Scenario: Sort order uses full untruncated value
    Given models with Manufacturer values "Spectravideo", "Sony", and "Sharp"
    When the user sorts by Manufacturer ascending
    Then the rows appear in order: "Sharp", "Sony", "Spectravideo"
    And truncation does not alter the sort position of any row

  Scenario: Column with truncate_limit=0 has no truncation
    Given a column with truncate_limit=0 and a cell value of 50 characters
    When the grid renders
    Then the cell displays the full 50-character value without ellipsis
```

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branch: `feature/cell-value-truncation`

## Architecture Fit
- Touch points:
  - `scraper/columns.py` — `Column` dataclass (add field)
  - `scraper/build.py` — `ColumnDef` serialiser (emit `truncateLimit` when non-zero)
  - `src/types.ts` — `ColumnDef` interface (add optional field)
  - `src/grid.ts` — `buildDataRow` (apply truncation) + `mouseenter` handler (prefer `data-full-value`)
- Compatibility notes:
  - `truncateLimit` is omitted from `data.js` when zero — existing consumers see no change for columns they don't use.
  - No URL codec changes; no filter changes; no sort changes.
  - `data.js` format version does not need to be bumped (additive optional field, forward-compatible).

## Observability (Minimum Viable)
- Applicability: N/A — this is a pure client-side rendering feature with no network calls, no async paths, and no failure modes that require runtime logging.
- Failure modes:
  - `truncateLimit` field missing in `data.js` (e.g. old cached data) → `truncateLimit` is `undefined`, treated as `0` by the `?? 0` guard → no truncation applied, graceful degradation.

## Testing Strategy (Tier 0/1/2)
- Tier 0 — unit tests (required):
  - **Python** (`tests/scraper/test_columns.py`): `Column` dataclass accepts `truncate_limit`; default is `0`; `manufacturer` and `model` columns in `COLUMNS` list have `truncate_limit = 10`.
  - **Python** (`tests/scraper/test_build.py`): `ColumnDef` serialiser emits `truncateLimit` when non-zero; omits it when zero; value matches `Column.truncate_limit`.
  - **TypeScript** (`tests/web/cell-truncation.test.ts`): pure function `truncateValue(text, limit)` — happy path, exact limit, below limit, limit=0; `buildDataRow` integration: plain cell truncation, `data-full-value` attribute, link cell `a.title` combined format, non-truncated link cell `a.title` unchanged.
- Tier 1 — integration: N/A (no server, no external calls).
- Tier 2 — E2E: Manual smoke — open `docs/index.html`, verify Manufacturer and Model cells truncate at 10, hover tooltip shows full value, CTRL+C returns full value.

## Data and Migrations
- Applicability: Schema only
- Up migration: Add `truncateLimit?: number` to `ColumnDef` in `data.js` (additive, optional). Existing consumers that don't read the field are unaffected.
- Down migration: No — removing the field simply reverts to no truncation; safe to do at any time.
- Backfill plan: None — re-run `python -m scraper build` to regenerate `data.js` with the new field.
- Rollback considerations: Reverting the Python change and rebuilding `data.js` removes `truncateLimit` from output; the browser code will degrade gracefully to no truncation if the field is absent.

## Rollout and Verify
- Applicability: N/A — static file commit; no staged rollout needed.
- Strategy: All-at-once (commit `docs/data.js` + `docs/bundle.js` together).
- Verify (smoke path):
  1. Run `python -m scraper build` and confirm `docs/data.js` contains `"truncateLimit":10` on the `manufacturer` and `model` column entries.
  2. Run `npm run build` and open `docs/index.html` locally.
  3. Find a model with a Manufacturer longer than 10 chars — confirm the cell shows `<9chars>…`.
  4. Hover the cell — confirm native tooltip shows the full manufacturer name.
  5. Find a Model cell with a URL and name > 10 chars — confirm tooltip shows `"<name> — <url>"`.
  6. Select a truncated Manufacturer cell, CTRL+C, paste into a text editor — confirm full value.
- Signals to watch: All Tier 0 tests green; no regressions in existing Vitest or pytest suites.

## Cleanup Before Merge
- Remove: No temporary flags or debug code introduced by this feature.
- Squash intermediate commits into logical commits (one per chunk is fine).
- Ensure all commits follow Conventional Commits.
- Rebase onto trunk and merge with fast-forward only.

## Definition of Done
- Gherkin specification is complete and current in this plan artifact.
- Tier 0 tests green (pytest + Vitest); no regressions in existing suites.
- `docs/data.js` regenerated and committed with `truncateLimit` on `manufacturer` and `model`.
- `docs/bundle.js` rebuilt and committed.
- Smoke path verified locally.
- Backlog updated: item moved to "In product (shipped)".

## Chunks

- Chunk A — Schema + config (Python side)
  - User value: `truncate_limit` field is declared and set; scraper emits `truncateLimit` in `data.js`.
  - Scope: `scraper/columns.py`, `scraper/build.py`, `tests/scraper/test_columns.py`, `tests/scraper/test_build.py`.
  - Ship criteria: `pytest tests/scraper/` green; `data.js` output contains `"truncateLimit":10` on `manufacturer` and `model`.
  - Rollout notes: None — Python-only change, no browser impact until bundle is rebuilt.

- Chunk B — TypeScript types + render + tooltip
  - User value: Truncated cells visible in the browser; hover tooltips work for plain and link cells.
  - Scope: `src/types.ts`, `src/grid.ts`, `tests/web/cell-truncation.test.ts`.
  - Ship criteria: Vitest green; smoke path verified in `docs/index.html`.
  - Rollout notes: Requires `data.js` from Chunk A to be present.

## Relevant Files (Expected)
- `scraper/columns.py` — add `truncate_limit: int = 0` to `Column` dataclass; set `10` on `manufacturer` and `model`
- `scraper/build.py` — serialise `truncateLimit` into `ColumnDef` when non-zero
- `src/types.ts` — add `truncateLimit?: number` to `ColumnDef` interface
- `src/grid.ts` — `buildDataRow`: apply truncation, set `data-full-value`, update `a.title` for link cells; `mouseenter`: prefer `data-full-value`
- `tests/scraper/test_columns.py` — new tests for `truncate_limit` field
- `tests/scraper/test_build.py` — new tests for `truncateLimit` serialisation
- `tests/web/cell-truncation.test.ts` — new Vitest test file

## Assumptions
- `truncateLimit` is treated as `text.length > truncateLimit` (strictly greater than); value at exactly the limit is not truncated.
- `truncate_limit` is character-count based (not pixel-width); consistent with the decision log.
- The `manufacturer` column has no `linkable` flag today; combined tooltip logic (`fullValue — url`) only applies when `col.linkable` is true and a URL is present.

## Validation Script (Draft)
1. `pytest tests/scraper/` — all green
2. `python -m scraper build` — check `data/data.js` (or `docs/data.js`) for `"truncateLimit":10`
3. `npm test -- --run` — all Vitest tests green
4. `npm run build` — clean build
5. Open `docs/index.html` — verify Manufacturer "Spectravideo" renders as "Spectravide…"
6. Hover the cell — verify tooltip "Spectravideo"
7. Find a Model cell with URL, name > 10 chars — verify combined tooltip
8. Select truncated cell, CTRL+C, paste — verify full value

## Tasks

- [x] T-001 Create and checkout a local branch `feature/cell-value-truncation`

- [x] Chunk A — Schema + config (Python side)
  - [x] T-010 Add `truncate_limit: int = 0` to the `Column` dataclass in `scraper/columns.py`
  - [x] T-011 Set `truncate_limit = 10` on `manufacturer` (id=1) and `model` (id=2) in `COLUMNS`
  - [x] T-012 In `scraper/build.py`, serialise `truncateLimit` into the `ColumnDef` dict when `col.truncate_limit > 0`
  - [x] T-013 Tests: extend `tests/scraper/test_columns.py` — default is `0`; `manufacturer` and `model` have `truncate_limit = 10`
  - [x] T-014 Tests: extend `tests/scraper/test_build.py` — `truncateLimit` emitted when non-zero; omitted when zero
  - [x] T-015 Rebuild `data.js`: run `python -m scraper build` and commit updated `docs/data.js`

- [x] Chunk B — TypeScript types + render + tooltip
  - [x] T-020 Add `truncateLimit?: number` to `ColumnDef` interface in `src/types.ts`
  - [x] T-021 In `buildDataRow` (`src/grid.ts`): after computing `text`, apply truncation — `if (col.truncateLimit && text.length > col.truncateLimit) { td.dataset.fullValue = text; displayText = text.slice(0, col.truncateLimit - 1) + '…'; } else { displayText = text; }` — use `displayText` everywhere `text` was used
  - [x] T-022 For link cells in `buildDataRow`: when `td.dataset.fullValue` is set, replace `a.title = url` with `a.title = td.dataset.fullValue + ' — ' + url`
  - [x] T-023 In `mouseenter` handler (`src/grid.ts`): add `if (td.dataset.fullValue) { td.title = td.dataset.fullValue; return; }` as the first check after the existing `a.cell-link` guard
  - [x] T-024 Create `tests/web/cell-truncation.test.ts`: 12 Vitest tests across 3 describe blocks — plain cell truncation (6), link cell truncation (4), mouseenter handler (2)

- [x] Quality gate
  - [x] T-900 Run `npm run lint` — N/A (no lint script configured)
  - [x] T-901 Run `npm run typecheck` — 7 pre-existing errors in unrelated test files, 0 new errors
  - [x] T-902 Run `npm test -- --run` — 88 Vitest tests green (76 pre-existing + 12 new)
  - [x] T-903 Run `pytest tests/scraper/` — 238 pytest tests green
  - [x] T-904 Run `npm run build` — clean build, bundle 94.98 kB

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits (one per chunk)
  - [ ] T-951 Verify all commits follow Conventional Commits (`feat:` for T-010..T-024, `test:` for test-only commits)
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)
  - [x] T-953 Update `product-backlog.md` — move "Cell value truncation" to "In product (shipped)"

## Open Questions
- None.

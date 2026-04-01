# Risk & Assumption Review: MSX Models DB

## Metadata
- Date: 2026-04-01
- Reviewed Artifacts:
  - .claude/artifacts/planning/problem-description.md
  - .claude/artifacts/planning/problem-description-slotmap.md
  - .claude/artifacts/planning/product-requirements.md
- Open Questions:
  - .claude/artifacts/decisions/open-questions.md

## Confirmed Truths
- The page must be entirely client-side; no server assistance is available at runtime.
  - Evidence: Static deployment requirement; file:// protocol support.
- Data must be loaded via a `<script>` tag (e.g. data.js sets `window.MSX_DATA = {...}`), not `fetch()`.
  - Evidence: Blogger/Blogspot embed requirement; file:// protocol support.
- URL state must be compact binary, base64-encoded — not human-readable.
  - Evidence: URL length target (< 2000 chars); 93 columns + 160 models.
- All row and column IDs must be stable and immutable forever.
  - Evidence: "Old URLs must remain valid forever" requirement.
- FontAwesome 7 Free is already bundled and used in the toolbar (fa-filter icon for filter toggle).
  - Evidence: `@fortawesome/fontawesome-free` in package.json; toolbar.ts uses `fas fa-filter`.
- Group headers already track hidden-column state via `group-header--partial` CSS class.
  - Evidence: `recalcGroupHeader()` in grid.ts toggles this class.
- Filter state is already tracked in a `Map<number, string>` keyed by column index.
  - Evidence: `const filters = new Map<number, string>()` in grid.ts.

## Key Risks
- Group filter indicator icon crowds the header when combined with chevron and hidden-columns indicator
  - Category: Product
  - Likelihood: Medium
  - Impact: Low
  - Mitigation: Use a small icon size; position it consistently (e.g. before chevron); test with collapsed + partial + filtered simultaneously.
  - Owner: bengalack

- Collapsed group header has colSpan=1 — very narrow; filter icon plus chevron plus group name may not fit
  - Category: Technical
  - Likelihood: Medium
  - Impact: Low
  - Mitigation: When collapsed, the group name is already truncated; the filter icon should be small and positioned to not require extra width. Test with the narrowest group names.
  - Owner: bengalack

- Filter icon not updating when filters are cleared via URL restore or reset-all action
  - Category: Technical
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: The icon toggle must be called from every code path that modifies filters: input handler, clear button, URL restore, and any future "clear all filters" action.
  - Owner: bengalack

## Dangerous Assumptions
- The `recalcGroupHeader()` function is called on every filter change
  - Why dangerous: If the filter icon update is placed in `recalcGroupHeader()` but that function is not called on filter change (it currently only handles column visibility), the icon won't update.
  - How to validate: Trace all filter-change code paths and verify they trigger group header recalculation.
  - If false, what breaks: Filter icon stays stale — shows when no filter is active, or doesn't appear when one is.

- The filter row is always visible when filters are active
  - Why dangerous: If the filter row can be toggled hidden (via the toolbar filter button) while filters are still active in the `filters` Map, the group indicator becomes the only signal. This is correct behavior but must be tested.
  - How to validate: Set a filter, collapse the filter row, verify the group icon persists.
  - If false, what breaks: User loses all indication that filters are active.

## Scope Creep Watchlist
- Clicking the filter icon to clear group filters — explicitly out of scope per user decision, but a natural follow-up request.
- Showing a count of active filters per group (e.g. badge number) — not requested, avoid.
- Extending the indicator to sort state (showing which group has the sorted column) — not requested.

## Over-Engineering Traps
- Creating a generic "group header badge" system for arbitrary indicators
  - Simplest safe alternative: A single `<i>` element toggled via a CSS class on the group header `<th>`.
- Animating the filter icon appearance/disappearance
  - Simplest safe alternative: Simple display toggle (hidden/visible), no transitions.

## Recommended Simplifications
- Reuse the existing `recalcGroupHeader()` pattern: add a CSS class (`group-header--filtered`) to the `<th>` and use CSS to show/hide a pre-existing `<i>` element inside it.
  - Tradeoff: No animation or fade effect.
  - Why acceptable: Consistent with how `group-header--partial` already works; no new patterns to learn.

---

# Risk & Assumption Review: Cell Value Truncation

## Metadata
- Date: 2026-04-01
- Reviewed Artifacts:
  - .claude/artifacts/planning/product-requirements.md (Cell value truncation requirement, v0.6)
- Open Questions:
  - .claude/artifacts/decisions/open-questions.md

## Confirmed Truths
- `Model` is the only `linkable=True` column; only it produces cells with `<a class="cell-link">`.
  - Evidence: `scraper/columns.py` — only `id=2` has `linkable=True`.
- The current mouseenter handler explicitly skips cells containing `a.cell-link`, so link cells have no overflow tooltip today.
  - Evidence: `grid.ts` — `if (td.querySelector('a.cell-link')) return;` exits early.
- Sorting operates on raw `ModelRecord.values[]` entries, not on rendered `td.textContent`.
  - Evidence: `sortModels()` in `grid.ts` reads `model.values[colIndex]` directly.
- Character-count-based truncation is unambiguous for the data in scope (all model names are ASCII or near-ASCII).
  - Evidence: msx.org model names; no known CJK or surrogate-pair values in Model/Manufacturer columns.

## Key Risks
- Clipboard copy captures the truncated display text, not the full value
  - Category: Technical
  - Likelihood: High
  - Impact: Medium
  - Mitigation: The copy handler reads `td.textContent` (or `a.textContent` for link cells). If truncation is applied via `textContent`, copied text will also be truncated. The full value must be stored as a `data-*` attribute on `td` and used by the copy path, or the copy handler must read from `model.values[]` directly.
  - Owner: bengalack

- The `Manufacturer` column has no `linkable` flag today — its cells are plain text; truncation is straightforward. If `linkable` is ever added to `Manufacturer`, the combined-tooltip logic must be revisited.
  - Category: Technical
  - Likelihood: Low
  - Impact: Low
  - Mitigation: The `truncate_limit` rendering path should already handle any linkable column uniformly — do not special-case `Model`.
  - Owner: bengalack

- `truncate_limit` is a display concern only; shipping it in `data.js` to the browser adds a trivial field to `ColumnDef`. No risk.
  - Category: Technical
  - Likelihood: Low
  - Impact: Low
  - Mitigation: None needed.
  - Owner: bengalack

## Dangerous Assumptions
- Character count truncation is a faithful proxy for visible width
  - Why dangerous: CSS may apply proportional fonts where `W` is wider than `i`; 9 chars of `WWWWWWWWW` overflows more than 9 chars of `iiiiiiiii`. A fixed truncate_limit in characters may still overflow or may truncate earlier than needed.
  - How to validate: Test the longest likely values (e.g. "Panasonic", "Spectravideo", "National") at the rendered column width.
  - If false, what breaks: Truncated cell still visually overflows, or short names are needlessly truncated. Since CSS `text-overflow: ellipsis` is already available as an alternative, this bears consideration.

- Native `title` tooltip is sufficient UX for full value + URL
  - Why dangerous: Browser native tooltips have a delay (~500 ms) and no styling control. On touch devices they don't appear at all.
  - How to validate: Confirm target users are desktop-only (consistent with "no mobile-first" non-goal).
  - If false, what breaks: Touch/mobile users cannot access the full model name or URL via tooltip.

- Truncation at limit=10 yields readable labels for all real Manufacturer/Model values
  - Why dangerous: "Spectravid…" (9 chars) for Spectravideo is arguably useful; "Al Alami…" (9 chars) for "Al Alamiah" is borderline. Some names may become ambiguous when truncated.
  - How to validate: Run through all known Manufacturer and Model values in the dataset to confirm no two values share the same 9-char prefix.
  - If false, what breaks: Two rows appear to have identical cell display values, confusing comparison.

## Scope Creep Watchlist
- CSS `text-overflow: ellipsis` as an alternative — this truncates by pixel width, not character count, and the `…` is rendered by the browser automatically. Raises the question of whether `truncate_limit` is needed at all if CSS handles it.
- Per-column tooltip styling (custom tooltip component instead of native `title`).
- Applying `truncate_limit` to other string columns beyond Model and Manufacturer.

## Over-Engineering Traps
- Storing the full value in a `data-full-value` attribute AND re-reading `model.values[]` in the copy handler
  - Simplest safe alternative: Store only `data-full-value` on the `td` at render time; all consumers (tooltip, copy) read from it. Avoids coupling copy handler to the column index lookup.
- Implementing a custom tooltip/popover component
  - Simplest safe alternative: Native `title` attribute — already used in the codebase and sufficient for desktop users.

## Recommended Simplifications
- Apply truncation purely in the render path (`buildDataRow`): write truncated text as `textContent`/`a.textContent`, set `data-full-value` on `td`, and update the mouseenter handler to set `td.title` from `data-full-value` for both plain and link cells.
  - Tradeoff: `data-full-value` adds a small per-cell DOM attribute for truncated columns.
  - Why acceptable: Keeps all truncation knowledge in one place; no changes to sort, filter, or URL codec paths.

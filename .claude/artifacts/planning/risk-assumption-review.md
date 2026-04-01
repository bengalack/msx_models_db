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

# Plan: Slot Map — Browser Tooltip Rendering

## Metadata
- Date: 2026-03-30
- Backlog item: Slot map — browser tooltip rendering
- Feature slug: slotmap-tooltip-rendering

## Context
- Intended outcome: Hovering over a slot map cell in the grid shows a human-readable tooltip explaining the abbreviation. The `~` sentinel and mirror `abbr*` cells are also visually distinct from normal content.

## Functional Snapshot
- Problem: Slot map cells display short abbreviations (MAIN, SUB, DSK, …) that are meaningful to hardware experts but opaque to general users. Without a tooltip, users must consult external references to understand cell values.
- Target user: MSX enthusiast / researcher hovering over slot map cells in the grid to understand a model's memory layout.
- Success criteria (observable):
  - Hovering a cell with a known abbreviation (e.g. "MAIN") shows a tooltip "MSX BIOS with BASIC ROM".
  - Hovering a `~` cell shows "Not expanded".
  - Hovering a mirror cell (e.g. "SUB*") shows "Sub ROM (mirror)".
  - Hovering a cell with an unknown raw tag string shows no tooltip.
  - `~` cells and mirror cells are visually distinct from cells with plain abbreviations.
- Primary user flow:
  1. User opens the grid page.
  2. User scrolls to a slotmap column.
  3. User hovers over a slot map cell.
  4. OS tooltip appears with the full description.
- Must never happen:
  - Tooltip logic must not throw or crash the grid.
  - Non-slotmap cells must not receive slotmap tooltip behavior.
- Key edge cases:
  - `~` → look up directly in LUT ("Not expanded")
  - `MAIN*` (mirror) → look up `MAIN` in LUT, append " (mirror)"
  - `CS1` → not in LUT (cartridge slots are derived, not LUT entries) → no tooltip
  - unknown raw tag (e.g. `SomeChip`) → not in LUT → no tooltip
  - `slotmap_lut` absent or empty → no tooltips rendered; no error
- Business rules:
  - Only columns whose key starts with `slotmap_` receive tooltip treatment.
  - LUT is keyed by abbreviation; `~` is a valid LUT key.
  - Mirror cells: strip trailing `*`, look up base abbr, append " (mirror)" to tooltip.
  - If base abbr is not in LUT, no tooltip is shown for the mirror cell.
  - Tooltip uses native HTML `title` attribute (no custom widget).
- Integrations:
  - `window.MSX_DATA.slotmap_lut` — `Record<string, string>` already embedded in `data.js` by the build pipeline. If absent (old data.js), degrade gracefully (no tooltips, no error).
- Non-functional requirements:
  - Privacy/Security: no user data involved.
  - Performance: LUT lookup is O(1); no measurable impact.
  - Reliability: must not interfere with existing grid interactions.
- Minimal viable increment (MVI): Native `title` tooltips + CSS visual markers for `~` and mirror cells. No custom tooltip widget.
- Deferred:
  - Custom animated tooltip widget (not needed; native `title` is sufficient for desktop).
  - Touch/mobile tooltip interaction.
  - `CS{N}` tooltip (cartridge slots are not in the LUT; add later by extending `slotmap-lut.json`).

## Executable Specification (Gherkin)

Feature: Slot map cell tooltips
  When a user hovers over a slot map cell, a tooltip from the LUT appears.
  The ~ sentinel and mirror cells are visually distinct.

  Background:
    Given the grid is loaded with window.MSX_DATA.slotmap_lut containing:
      | abbr  | tooltip                  |
      | MAIN  | MSX BIOS with BASIC ROM  |
      | SUB   | Sub ROM                  |
      | ~     | Not expanded             |

  Scenario: Known abbreviation shows tooltip
    Given a slotmap cell has the value "MAIN"
    When the user hovers over that cell
    Then the tooltip "MSX BIOS with BASIC ROM" is shown

  Scenario: Tilde sentinel shows tooltip
    Given a slotmap cell has the value "~"
    When the user hovers over that cell
    Then the tooltip "Not expanded" is shown

  Scenario: Mirror cell shows origin tooltip with suffix
    Given a slotmap cell has the value "SUB*"
    When the user hovers over that cell
    Then the tooltip "Sub ROM (mirror)" is shown

  Scenario: Unknown abbreviation shows no tooltip
    Given a slotmap cell has the value "SomeChip"
    And "SomeChip" is not a key in slotmap_lut
    When the user hovers over that cell
    Then no tooltip is shown

  Scenario: Non-slotmap cell is unaffected
    Given a data cell belongs to a column whose key is "manufacturer"
    When the user hovers over that cell
    Then no slotmap tooltip is applied

  Scenario: Missing LUT does not crash the grid
    Given window.MSX_DATA.slotmap_lut is absent or empty
    When the grid is rendered
    Then all slot map cells render normally with no tooltip and no JS error

  Scenario: Tilde and mirror cells are visually distinct
    Given a slotmap cell has the value "~"
    And another slotmap cell has the value "MAIN*"
    When the grid is rendered
    Then the "~" cell carries the CSS class "cell-slotmap-tilde"
    And the "MAIN*" cell carries the CSS class "cell-slotmap-mirror"
    And a cell with value "MAIN" carries neither class

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points:
  - `src/types.ts` — add `slotmap_lut?: Record<string, string>` to `MSXData`
  - `src/grid.ts` — pass `slotmap_lut` to `buildDataRow()`; set `title` + CSS classes for slotmap cells
  - `src/styles/grid.css` — add `.cell-slotmap-tilde` and `.cell-slotmap-mirror` styles
  - `tests/web/slotmap-tooltip.test.ts` — new unit test file for `resolveSlotmapTooltip` helper
- Compatibility notes:
  - `slotmap_lut` is an optional field on `MSXData`; absence must not break existing pages or tests.
  - `buildDataRow` signature is internal; no external callers.

## Observability (Minimum Viable)
- Applicability: N/A — pure client-side DOM feature; no network I/O; no errors expected.
- Failure modes:
  - Missing `slotmap_lut` → no tooltips; grid renders normally.

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required):
  - Pure unit tests for the `resolveSlotmapTooltip(value, lut)` helper: known abbr, `~`, mirror, unknown, mirror with unknown base, empty lut.
  - Vitest, in `tests/web/slotmap-tooltip.test.ts`.
- Tier 1 (if applicable): N/A — no DOM integration tests needed for a `title` attribute set.
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — `slotmap_lut` is already present in `docs/data.js` (shipped in the LUT feature). TypeScript type update is additive/optional.

## Rollout and Verify
- Applicability: N/A — static page; no server; single static deployment target.

## Cleanup Before Merge
- Remove: no temporary code planned.
- Squash intermediate commits into logical commits.
- Ensure all commits follow Conventional Commits.
- Rebase onto trunk and merge (fast-forward only).

## Definition of Done
- Gherkin specification is complete and current in the plan artifact.
- Tier 0 green.
- Cleanup gate satisfied.
- Backlog updated (item moved to "In product (shipped)").

## Chunks

- Chunk A: Tooltip helper + types + tests
  - User value: Establishes the core tooltip resolution logic, fully tested.
  - Scope: Add `slotmap_lut` to `MSXData`; extract `resolveSlotmapTooltip()`; unit tests.
  - Ship criteria: All `resolveSlotmapTooltip` unit tests pass.
  - Rollout notes: none.

- Chunk B: Grid rendering integration + CSS
  - User value: Tooltips and visual markers visible in the browser.
  - Scope: Wire `slotmap_lut` into `buildGrid` → `buildDataRow`; set `title`; add CSS classes.
  - Ship criteria: Grid renders with `title` attrs on slotmap cells; `~` and `*` cells have correct CSS classes; no regressions.
  - Rollout notes: none.

## Relevant Files (Expected)
- `src/types.ts` — add optional `slotmap_lut` to `MSXData`
- `src/grid.ts` — wire tooltip helper into `buildDataRow`
- `src/styles/grid.css` — add `.cell-slotmap-tilde` and `.cell-slotmap-mirror` styles
- `tests/web/slotmap-tooltip.test.ts` — new Vitest unit tests

## Notes
- `resolveSlotmapTooltip` is a pure function; extract it to a small helper module or inline helper in grid.ts — inline is fine given the size.
- Native `title` attribute is sufficient for the desktop target; the PRD does not require a custom widget.

## Assumptions
- `slotmap_lut` keys use exactly the same abbreviation strings that appear in cell values (already guaranteed by the build pipeline).
- CS{N} strings (e.g. "CS1", "CS2") are not present in the starter LUT; they will show no tooltip until the maintainer adds them to `slotmap-lut.json`.

## Validation Script (Draft)
1. Run `npm run build` and open `docs/index.html` in a browser.
2. Navigate to a slotmap column group.
3. Hover over a cell displaying "MAIN" — verify tooltip "MSX BIOS with BASIC ROM".
4. Hover over a cell displaying "~" — verify tooltip "Not expanded".
5. Hover over a mirror cell (e.g. "SUB*") — verify tooltip "Sub ROM (mirror)".
6. Hover over a "CS1" cell — verify no tooltip appears.
7. Verify "~" cells have visually muted style; mirror cells have visually distinct style.

## Tasks

- [x] T-001 Create and checkout local branch `feature/slotmap-tooltip-rendering`

- [ ] Implement: Chunk A — Tooltip helper + types + tests
  - [x] T-010 Add `slotmap_lut?: Record<string, string>` to `MSXData` interface in `src/types.ts`
  - [x] T-011 Extract `resolveSlotmapTooltip(value: string, lut: Record<string, string>): string | null` pure helper in `src/grid.ts` (returns tooltip string or null for no tooltip)
  - [x] T-012 Tests: add `tests/web/slotmap-tooltip.test.ts` covering: known abbr, `~`, mirror with known base, mirror with unknown base, unknown abbr, empty lut

- [ ] Implement: Chunk B — Grid rendering + CSS
  - [x] T-020 In `buildDataRow`, detect slotmap columns (`col.key.startsWith('slotmap_')`), call `resolveSlotmapTooltip`, and set `td.title`
  - [x] T-021 Add CSS classes: `cell-slotmap-tilde` on cells with value `~`; `cell-slotmap-mirror` on cells with value ending `*`
  - [x] T-022 Add `.cell-slotmap-tilde` and `.cell-slotmap-mirror` styles to `src/styles/grid.css`
  - [x] T-023 Update plan checkboxes and verify all Vitest tests pass

- [ ] Quality gate
  - [x] T-900 Run formatters (eslint --fix / prettier if configured)
  - [x] T-901 Run linters
  - [x] T-902 Run full test suite (Vitest + pytest)

- [ ] Merge to trunk
  - [x] T-950 Rebase onto trunk and merge (fast-forward only)
  - [x] T-951 Move backlog item to "In product (shipped)"

## Open Questions
- None.

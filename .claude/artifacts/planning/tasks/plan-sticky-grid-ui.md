# Plan: Implement Sticky Grid UI

## Gherkin Specification

Feature: Sticky grid headers and left gutter for MSX Models DB
  As a user viewing the MSX Models DB grid
  I want the page header, toolbar, group header, column header, filter row, and left gutter to remain visible as I scroll
  So that I always keep context and can easily interpret the data, even with many columns and rows

  Scenario: All sticky headers and left gutter remain visible during scroll
    Given the grid is rendered with many columns and rows
    When I scroll horizontally and vertically
    Then the page header, toolbar, group header, column header, filter row, and left gutter remain visible and aligned

  Scenario: Slot map columns are scrollable but headers/gutter remain sticky
    Given the grid includes 64 slot map columns
    When I scroll horizontally
    Then the slot map columns scroll under the sticky headers and left gutter, which remain visible

  Scenario: Collapsing/expanding column groups does not break sticky layout
    Given a column group is collapsed or expanded
    When I scroll the grid
    Then all sticky headers and the left gutter remain visible and correctly aligned

  Scenario: Hiding/unhiding rows does not break sticky layout
    Given one or more rows are hidden or unhidden
    When I scroll the grid
    Then all sticky headers and the left gutter remain visible and correctly aligned

  Scenario: No sticky element overlaps or misaligns
    Given the grid is scrolled or resized
    Then no sticky header or gutter overlaps, misaligns, or detaches from the grid body

  Scenario: Performance remains acceptable with many columns/rows
    Given the grid has >50 columns and >100 rows
    When I scroll rapidly
    Then sticky headers and gutter remain responsive and visually correct

  Scenario: Must never happen — sticky elements scroll out of view
    Given the grid is scrolled in any direction
    Then the sticky headers and left gutter never scroll out of view

## Chunks and Tasks

### Chunk 1: Sticky header and gutter scaffolding
- [ ] Implement sticky positioning for page header, toolbar, group header, column header, filter row
- [ ] Implement sticky left gutter (row numbers, hide/unhide, gap indicators)
- [ ] Ensure correct z-index stacking for all sticky elements
- [ ] Manual test: scroll grid in both directions, verify all sticky elements remain visible and aligned

### Chunk 2: Slot map columns and group header integration
- [ ] Render all 64 slot map columns in the grid
- [ ] Ensure slot map columns scroll horizontally under sticky headers/gutter
- [ ] Manual test: scroll horizontally, verify slot map columns and sticky elements behave as expected

### Chunk 3: Edge cases and robustness
- [ ] Test with group collapse/expand, verify sticky layout is preserved
- [ ] Test with row hide/unhide, verify sticky layout is preserved
- [ ] Test browser resize, verify sticky layout is preserved
- [ ] Test with many columns/rows for performance
- [ ] Fix any visual glitches, overlaps, or misalignments

### Chunk 4: Automation and cleanup
- [ ] Add/adjust automated tests for sticky layout (if feasible)
- [ ] Remove debug logs, temporary code, and TODOs
- [ ] Final manual test: all Gherkin scenarios pass

## Observability
N/A (pure frontend visual feature)

## Testing
- Manual test for all Gherkin scenarios
- Add automated tests if feasible (e.g., DOM structure, CSS class presence)

## Data
N/A

## Rollout
- Feature is user-facing and can be released as soon as all tasks are complete and automation is green.

---

This plan will be updated as each chunk is completed. Each task will be checked off in the same commit as the code change.
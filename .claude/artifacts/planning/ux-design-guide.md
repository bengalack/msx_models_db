# UX Design Guide: MSX Models DB

## Metadata
- Date: 2026-03-27
- Related:
  - PRD: .claude/artifacts/planning/product-requirements.md

## Visual References
- Reference 1: CRT phosphor terminal aesthetic — black background, glowing green text, scanline feel
- Reference 2: Classic green-screen monitors (VT100, IBM 3270) — dense monospace data, minimal chrome
- Textual direction: Dark mode default — near-black background, phosphor green text and accents, subtle glow on interactive elements. Light mode — warm off-white/cream with forest green accents. All colors via CSS custom properties so the entire theme is swappable from one block of CSS.

## Design Principles
- Data first — the grid occupies the full viewport; chrome is minimal and unobtrusive
- Retro surface, modern behaviour — the CRT aesthetic is visual only; interaction is fast and precise
- Themeable by design — every color is a CSS custom property; no hardcoded hex values in component CSS
- Compact but readable — monospace font, tight row height, clear grid lines; never sacrifice legibility for density
- Glow is accent, not noise — phosphor glow effects are used sparingly on selected/active elements only

## Interface Surfaces
- Surfaces: Web
- Primary surface: Desktop browser (full-width, single scrollable page)
- Input modalities: Keyboard+Mouse

## Accessibility
- Target: WCAG 2.1 AA
- Keyboard: Required (sort, filter, hide/show columns via keyboard; CTRL+C copy)
- Color contrast: Required (all text ≥ 4.5:1 against background in both themes)
- Note: Phosphor glow effects must not be the sole indicator of state — always pair with color/border

## Typography
- Font families:
  - Mono (primary — all text): `"Share Tech Mono", "Consolas", "Monaco", "Courier New", monospace`
  - Sans: not used (monospace is used throughout for retro consistency)
- Type scale:
  - Page title / H1: 18px / 700 / 1.2
  - Group header / H2: 12px / 600 / 1.3 / uppercase + letter-spacing: 0.08em
  - Column header: 11px / 600 / 1.3 / uppercase
  - Cell body: 12px / 400 / 1.4
  - Filter input: 12px / 400 / 1.3
  - Caption / label: 11px / 400 / 1.2
- Usage rules: Monospace everywhere reinforces the terminal aesthetic and ensures column alignment. Uppercase headers at small size aid scanning across many columns.

## Color System

All colors are defined as CSS custom properties on `[data-theme="dark"]` and `[data-theme="light"]` on the `<html>` element. Component CSS uses only `var(--...)` tokens — no hardcoded hex values.

### Dark mode (default) — phosphor green

```css
[data-theme="dark"] {
  --color-bg:            #0a0a0a;   /* near-black */
  --color-surface:       #111111;   /* grid background */
  --color-surface-alt:   #161616;   /* alternating row */
  --color-border:        #1c3a1c;   /* grid lines */
  --color-border-strong: #2a5a2a;   /* header borders */

  --color-text:          #c8ffc8;   /* body text — soft phosphor */
  --color-text-muted:    #6abf6a;   /* secondary text */
  --color-text-heading:  #39ff14;   /* group/column headers — bright phosphor */

  --color-accent:        #39ff14;   /* primary accent — phosphor green */
  --color-accent-dim:    rgba(57, 255, 20, 0.18); /* selection fill */
  --color-accent-glow:   0 0 6px rgba(57, 255, 20, 0.5); /* box-shadow glow */

  --color-gutter-bg:     #0d1a0d;   /* row number strip */
  --color-gutter-text:   #3a7a3a;
  --color-gutter-indicator: #ff8800; /* hidden row/col indicator — amber contrast */

  --color-header-bg:     #0d1a0d;
  --color-filter-bg:     #0f1f0f;
  --color-filter-border: #2a5a2a;

  --color-selection-border: #39ff14;
  --color-hover:         rgba(57, 255, 20, 0.07);

  --color-sort-active:   #39ff14;
  --color-danger:        #ff4444;
  --color-warning:       #ffaa00;
  --color-success:       #39ff14;
}
```

### Light mode — warm cream + forest green

```css
[data-theme="light"] {
  --color-bg:            #f0f0e4;   /* warm off-white */
  --color-surface:       #ffffff;
  --color-surface-alt:   #f7f7ed;
  --color-border:        #c4d4c4;
  --color-border-strong: #8aaa8a;

  --color-text:          #1a2e1a;   /* dark forest green */
  --color-text-muted:    #4a6a4a;
  --color-text-heading:  #155215;

  --color-accent:        #2d7a2d;
  --color-accent-dim:    rgba(45, 122, 45, 0.14);
  --color-accent-glow:   none;      /* no glow in light mode */

  --color-gutter-bg:     #e0ede0;
  --color-gutter-text:   #5a7a5a;
  --color-gutter-indicator: #cc5500; /* amber */

  --color-header-bg:     #e0ede0;
  --color-filter-bg:     #eaf2ea;
  --color-filter-border: #8aaa8a;

  --color-selection-border: #2d7a2d;
  --color-hover:         rgba(45, 122, 45, 0.07);

  --color-sort-active:   #2d7a2d;
  --color-danger:        #cc2200;
  --color-warning:       #996600;
  --color-success:       #1a6b1a;
}
```

## Layout Rules
- Layout model: Full-viewport, single-page, sticky headers
- Spacing scale: 2px, 4px, 8px, 12px, 16px, 24px, 32px
- Density: Compact
- Grid structure (top to bottom):
  1. **Page header bar** — title, dark/light toggle, data timestamp (height: 36px, sticky)
  2. **Toolbar strip** — column picker button, filter toggle button (height: 32px, sticky)
  3. **Column group header row** — group names spanning their columns, collapse/expand chevron (height: 28px, sticky)
  4. **Column header row** — individual column names, sort arrows (height: 28px, sticky)
  5. **Filter row** — one input per visible column (height: 28px, sticky, toggleable)
  6. **Data rows** — model data (height: 24px per row)
- Left gutter: 52px wide strip — × hide button (left), row number (right), row-selection highlight, gap indicator
- The grid body scrolls both horizontally and vertically; all 4 header rows and the left gutter remain sticky
- Z-index stacking order (within `.grid-wrap` scroll container, low → high):
  1. **tbody gutter** — `z-index: 2` (sticky left column in data rows)
  2. **Gap indicator line** (`gutter--gap::before`) — `z-index: 3`
  3. **Unhide button** (`gutter__unhide-btn`) — `z-index: 4`
  4. **Selected cells** (`cell--selected`) — `z-index: 5` (selection outline always above gap indicators)
  5. **Header cells** (group, column, filter) — `z-index: 10`
  6. **Header gutter corner** (`thead .gutter`) — `z-index: 11`

## Components

### Screens/views
- Single view: the entire page is the grid. No navigation, no modal views, no separate pages.

### Navigation model
- No navigation. Single-page. Toolbar for view controls only.

### Grid — column group headers
- Span across all child columns
- Left-aligned group name in uppercase monospace, small size
- Collapse/expand chevron (▶ / ▼) at right edge of group header cell (absolutely positioned, does not affect text flow)
- Collapsed state: group header cell shrinks to colSpan=1; text truncated with ellipsis if too narrow
- Overflow: group and column header text is clipped with `text-overflow: ellipsis`, matching data cell behavior
- Active/expanded: `var(--color-border-strong)` bottom border

### Grid — column headers
- Sort indicator: ↑ (asc) / ↓ (desc) appended to column name; no arrow when unsorted
- Active sort column: header text in `var(--color-text-heading)` color
- Overflow: header text is clipped with `text-overflow: ellipsis` when the column is narrow (e.g. inside a collapsed group)
- Hidden column indicator: in the group header row, a small `▶` marker appears between visible columns where one or more columns are hidden between them
- Right-click on column header → context menu: Sort Asc / Sort Desc / Hide Column / Show Hidden Columns in Group

### Grid — filter row
- One `<input type="text">` per visible column
- Active filter: input border in `var(--color-accent)`, clear (×) button appears inside input
- Toggled via toolbar button; hidden by default
- Filter syntax:
  - Plain text: substring match (case-insensitive). E.g. `japan` matches "Japan", "Japanese"
  - `|` (pipe): OR — matches if the cell contains ANY of the pipe-separated terms. E.g. `Japan|Spain` matches rows containing "Japan" or "Spain"
  - `!` (bang prefix): negation — excludes rows containing that term. E.g. `!Japan` matches rows that do NOT contain "Japan"
  - Combined: positive terms are OR’d, negative terms are AND’d. E.g. `Japan|Spain|!Tokyo` matches rows containing "Japan" or "Spain", but excludes any that also contain "Tokyo"

### Grid — data cells
- Default: `var(--color-surface)` background, `var(--color-text)` text
- Alternating rows: `var(--color-surface-alt)`
- Hover (no selection): `var(--color-hover)` background
- Selected: `var(--color-accent-dim)` fill + `1px solid var(--color-selection-border)` outline; in dark mode add `var(--color-accent-glow)`
- Empty/null value: displayed as `—` (em dash) in `var(--color-text-muted)`
- Overflow: cell text is clipped with ellipsis; full value shown in browser native tooltip (`title` attribute)

### Grid — left gutter
- Width: 52px
- Layout per cell: × button left-aligned (absolute, 4px from left edge), row number right-aligned (padding-right: 4px; left padding: 20px to clear the × button)
- × button (`gutter__hide-btn`): always visible; `color: var(--color-gutter-text); opacity: 0.35`; hover: `opacity: 1; color: var(--color-danger)`. `tabindex="-1"` so it doesn’t interfere with keyboard navigation.
- Row number: inherits `var(--color-gutter-text)`, 10px, right-aligned
- Row selected state (`gutter--row-selected`): inverted colors — `background: var(--color-gutter-text); color: var(--color-gutter-bg)`. Applied to the gutter cell only; data cells are not highlighted for row selection.
- Gap indicator: a minimal-height `<tr class="row-gap-indicator">` containing only a gutter `<td class="gutter gutter--gap">` (no full-width span). The gutter cell shows a ▲ button in `var(--color-gutter-indicator)` (amber) with dashed top/bottom border. No other cells in the indicator row — the indicator is visible only in the gutter column.

### Toolbar
- Left: "MSX Models DB" title (H1)
- Right: `[⊞ Columns]` button (opens column picker panel), `[≡ Filters]` toggle, `[? Help]` button, `[◑]` dark/light mode toggle
- Column picker panel: a floating panel listing all columns grouped by group, each with a checkbox; closes on outside click
- Help panel: a floating panel (300×200px) anchored below the toolbar with help/reference text; opens on `[? Help]` click; button shows active state (inverted colors) while open; closes on outside click or Escape
- Only one floating panel (Columns or Help) can be open at a time — opening one closes the other

### Dark/light mode toggle
- Icon-only button: `◐` (half-moon)
- Sets `data-theme="dark"` or `data-theme="light"` on `<html>`
- Persists to `localStorage`

### Feedback
- Loading: a single line of phosphor-green text `Loading data...` centred in the grid area; no spinner
- No data matched: grid body shows `No models match the current filters.` in `var(--color-text-muted)`, centred
- Error (data file missing): `Failed to load data.` in `var(--color-danger)`, centred

### Empty states
- No selection: no status bar needed
- Cells selected: a status bar (bottom of page, 24px) shows `N cell(s) selected — CTRL+C to copy`

### Confirmations/dialogs
- No modal dialogs. All actions are immediately reversible (re-show hidden rows/columns). No destructive UI actions.

## Interaction Patterns

### Grid — row selection
- Click gutter number: selects that row only (deselects all others). If the row was already the only selection, deselects it.
- Click and drag across gutter numbers: selects all rows touched while the mouse button is held.
- CTRL/CMD + click gutter number: toggles the row in/out of selection without clearing others.
- SHIFT + click gutter number: selects the contiguous range between the last-clicked row (anchor) and the clicked row.
- Escape: clears both row selection and cell selection.
- Visual (gutter): inverted colors on the gutter cell (background ↔ text swap).
- Visual (cells): all data cells of selected rows also receive the standard `cell--selected` highlight.
- Clicking any data cell directly clears row selection and starts a new independent cell selection.
- Not copied: row selection has no effect on Ctrl+C / TSV output.

### Row hiding via × button
- Click × with no rows selected: hides the row of that ×.
- Click × with one or more rows selected: hides all selected rows, then clears selection.
- No right-click context menu anywhere in the gutter.

### Cell selection
- Single click: select cell, clear previous selection
- CTRL/CMD + click: toggle cell in/out of selection
- SHIFT + click: extend selection rectangle from anchor to clicked cell
- Click + drag: select cells covered during drag (snap to cell boundaries on mouseenter, no pixel math)
- Selected cells: `var(--color-accent-dim)` fill + 1px solid border in `var(--color-selection-border)`; dark mode adds subtle glow

### Sort
- Click column header → sort ascending; second click → descending; third click → clear
- Visual: ↑/↓ appended to header text; header text color shifts to `var(--color-text-heading)`

### Filter
- Typing in filter input triggers immediate filtering (no enter required)
- Supports `|` for OR (e.g. `Japan|Spain`) and `!` prefix for negation (e.g. `!Japan`)
- Rows not matching any active filter disappear; gutter indicator appears as described above
- Active filter inputs highlighted with accent border

### Column group collapse
- Click group header → toggle collapse; all child columns disappear / reappear
- Group header shrinks to show only chevron + short name when collapsed
- Collapsed groups reflected in URL state

### Hidden rows/columns
- × button in gutter hides a row (or all selected rows if any are selected)
- Gap indicator (▲ in gutter only) appears between visible rows wherever rows are hidden; clicking it restores those rows
- Filter-excluded rows do not produce a gap indicator (they are simply absent from the filtered view)
- Column hide/show via column picker panel

### Clipboard copy
- CTRL+C / CMD+C when cells are selected → writes TSV to clipboard
- Multi-row, multi-column: rows separated by `\n`, columns by `\t`
- Status bar confirms: `Copied N cell(s)`

### Dark/light toggle
- Click `◐` → swap theme instantly, persist to localStorage
- No animation/transition on theme change (avoids flash artifacts with dense grids)

## Content Style
- Voice: Terse, technical, no marketing language. Labels match source data terminology (e.g. "VDP" not "graphics chip").
- Terminology: Use MSX community standard terms — VDP, PSG, MSX-MUSIC, VRAM, turbo R (not "Turbo R"). Column names should match terminology used on msx.org.
- Numbers: RAM/ROM sizes in KB or MB as appropriate; clock speeds in MHz; no unit padding (write `64 KB` not `064KB`).
- Null/missing values: always render as `—`, never blank or `null` or `N/A`.

## UI Definition of Done
- All colors reference CSS custom properties — zero hardcoded hex values in component styles
- Both `data-theme="dark"` and `data-theme="light"` render correctly with ≥ 4.5:1 contrast for all text
- Theme preference is saved to localStorage and restored on page load
- Grid is fully usable with keyboard alone (Tab to toolbar controls, arrow keys for cell navigation, Enter to sort)
- CTRL+C copies selected cells as TSV without any browser permission prompt
- All sticky header rows remain fixed during both horizontal and vertical scroll
- Cell text overflow clips with ellipsis; native tooltip shows full value
- Gutter indicator is visible and clickable in both themes
- The phosphor glow effect (dark mode) is applied only via `box-shadow` — never interferes with layout

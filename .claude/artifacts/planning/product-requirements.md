# PRD: MSX Models DB

## Metadata
- Version: 0.1
- Date: 2026-03-27
- Owner: bengalack

## Problem Statement
MSX computer model specifications are scattered across multiple websites with no unified, structured reference. Enthusiasts and researchers who want to compare models — by RAM, video chip, CPU speed, media, or any other dimension — must open multiple tabs, manually reconcile inconsistent data, and copy information by hand. This is slow, error-prone, and discouraging.

The goal is a single static web page that presents all MSX2, MSX2+, and MSX turbo R models (including unofficial FPGA-based models) in a structured, spreadsheet-like grid. Users can sort, filter, show/hide columns and rows, select cells, copy data to the clipboard, and share their exact view via URL. The data is maintained in a local JSON file, refreshed on demand by a scraper that pulls from msx.org and the openMSX GitHub repository.

## Goals
- Provide a single, authoritative reference for MSX2/MSX2+/turbo R model specifications.
- Enable fast comparison and grouping of models via sort, filter, and column/row visibility controls.
- Allow any view state to be shared or bookmarked via a live-updating URL.
- Give the maintainer a repeatable, low-effort process to refresh the data.

## Non-Goals
- MSX1 models (future iteration).
- Real-time data fetching from external sources at page load.
- User accounts, authentication, or server-side processing.
- Community/crowd-sourced data editing via the UI.
- Mobile-first design.

## Users
- MSX enthusiasts / collectors (Primary)
- MSX researchers and developers (Secondary)
- bengalack, project maintainer (Internal)

## Scope
This iteration covers the web page (grid UI) and the offline scraper process. The web page is a static HTML/CSS/JS file that reads a local JSON data file — no server required. The scraper is a separate runnable process (not part of the web page) that the maintainer runs on demand to update the JSON. Both the page and the scraper are part of this repository.

## Functional Requirements

- Grid display
  - Description: The page renders all in-scope MSX models as rows in a spreadsheet-like grid. Each column maps to a model attribute. The grid is the primary and only view.
  - Priority: Must
  - Acceptance Criteria:
    - All MSX2, MSX2+, and MSX turbo R models present in the JSON file appear as rows.
    - Each column defined in the JSON schema is rendered as a grid column.
    - The grid is readable and usable without horizontal scrolling for the Identity group at minimum.

- Column groups
  - Description: Columns are organized into named groups: Identity, Memory, Video, Audio, Media, CPU/Chipsets, Other, Emulation. Each group has a header that can be clicked to collapse or expand all columns in that group.
  - Priority: Must
  - Acceptance Criteria:
    - Each column belongs to exactly one group.
    - Clicking a group header collapses all its columns (they disappear from view).
    - Clicking again expands them.
    - Collapsed state is reflected in the URL.

- Column sorting
  - Description: Clicking a column header sorts the grid by that column. Clicking again reverses the sort order.
  - Priority: Must
  - Acceptance Criteria:
    - Single-click on a column header sorts ascending; second click sorts descending; third click clears sort.
    - Sort state is reflected in the URL.
    - Only one column is sorted at a time (unless multi-sort is explicitly added later).

- Column filtering
  - Description: Each column can be filtered, narrowing the rows displayed to those matching the filter value.
  - Priority: Must
  - Acceptance Criteria:
    - A filter input is accessible per column (e.g. in the column header or a filter row).
    - Entering a value hides rows that do not match.
    - Filter state is reflected in the URL.
    - Clearing the filter restores all rows.

- Column show/hide
  - Description: Individual columns can be shown or hidden independently of their group's collapse state.
  - Priority: Must
  - Acceptance Criteria:
    - There is a UI control (e.g. a column picker panel or right-click context menu) to toggle individual column visibility.
    - Hidden columns are excluded from the rendered grid.
    - Column visibility state is reflected in the URL.

- Row show/hide
  - Description: Individual rows can be hidden via an always-visible × button in the row's left gutter cell. A compact visual indicator appears in the gutter only (not spanning the grid) wherever one or more rows are hidden.
  - Priority: Must
  - Acceptance Criteria:
    - Each row's gutter cell contains a × button (left-aligned, low-contrast) and a row number (right-aligned).
    - Clicking the × button hides that row if no rows are currently selected. If one or more rows are selected, clicking any × button hides all selected rows.
    - Hidden rows are not rendered in the grid.
    - A compact amber ▲ indicator appears in the gutter column only (not full-width) between visible rows whenever hidden rows exist in that gap; clicking it unhides those rows.
    - There is no right-click context menu for row hiding.
    - Hidden row state is reflected in the URL.

- Row selection
  - Description: Clicking a row's gutter number selects the full row (independent of cell selection). Multiple rows can be selected. Row selection is used to batch-hide rows via the × button.
  - Priority: Must
  - Acceptance Criteria:
    - Click on a row number selects that row and deselects all others. Clicking the only selected row deselects it.
    - CTRL+click (CMD+click on macOS) toggles the clicked row in/out of the selection without clearing other selections.
    - SHIFT+click selects the range of visible rows between the last-clicked row and the clicked row.
    - Selected rows are visually indicated by inverted colors on the gutter cell only (background and text colors swap).
    - Row selection does not affect cell selection and is not included in clipboard copy output.
    - Pressing Escape clears row selection.

- Cell selection
  - Description: Users can select one or more data cells using mouse interactions. Selected cells are visually highlighted. Row selection (via gutter numbers) is a separate interaction.
  - Priority: Must
  - Acceptance Criteria:
    - Click selects a single cell and deselects any previous selection.
    - CTRL+click (CMD+click on macOS) adds or removes a cell from the current selection.
    - SHIFT+click selects the rectangular range from the last-clicked cell to the current cell.
    - Click+hold and drag selects the visual range covered by the drag.
    - Selected cells are visually distinct from unselected cells (e.g. background color change).
    - Selection state is reflected in the URL.

- Clipboard copy
  - Description: The standard OS copy shortcut copies the content of selected cells to the clipboard as tab-separated values (suitable for pasting into spreadsheets).
  - Priority: Must
  - Acceptance Criteria:
    - Pressing CTRL+C (or CMD+C on macOS) while cells are selected copies their text content.
    - Multi-cell selections are copied as tab-separated columns and newline-separated rows.
    - No browser extension or plugin is required.

- Live URL state
  - Description: The page URL updates in real time to encode the complete current view state as a compact binary payload (base64-encoded in the URL hash fragment). Opening the URL recreates the exact view. Old URLs must remain valid forever across all future data updates.
  - Priority: Must
  - Acceptance Criteria:
    - The URL hash updates on every state-changing interaction: cell selection, column/row visibility, column group collapse, sort order, filter values.
    - All state is encoded as a binary payload and base64-encoded into the URL hash (not query string).
    - Opening the URL in a new browser tab produces an identical grid view.
    - Unknown IDs in a decoded URL (from removed models or columns) are silently ignored — the URL never causes an error.
    - When the URL has no hash, the page loads a configurable default view (column visibility, sort, filters, collapsed groups) defined in a separate config. The default view config is not part of the URL state.
    - The default view configuration is a low-priority item to be defined later; initial implementation may fall back to "show all, no sort, no filters" until configured.
    - URL state encoding is versioned so future format changes remain backwards-compatible.

- Static deployment
  - Description: The web page works as a local `index.html` opened from disk, as a page hosted on a static file host (e.g. GitHub Pages), and embedded in Blogger/Blogspot. No server is involved at runtime in any deployment target.
  - Priority: Must
  - Acceptance Criteria:
    - Opening `index.html` directly in a browser (file:// protocol) renders the full grid with data.
    - The same files work when served over HTTP from a static host.
    - The page can be embedded in a Blogger/Blogspot post and render correctly.
    - Data is loaded via a `<script>` tag (e.g. `data.js` sets `window.MSX_DATA = {...}`) rather than `fetch()`, so it works on all three targets.
    - No server-side code, build step, or runtime parameter passing is required.

- Stable IDs
  - Description: Every model (row) and every column is assigned a short integer ID that is immutable forever. IDs are never reused, even if a model or column is removed. These IDs are the basis of all URL state encoding.
  - Priority: Must
  - Acceptance Criteria:
    - Every model in the JSON has a unique, permanent integer `id` field.
    - Every column definition has a unique, permanent integer `id` field.
    - The scraper maintains a persistent ID registry shared across all data-gathering runs.
    - On each run, the scraper first attempts to match incoming data against existing registry entries (by model identity, e.g. manufacturer + model name) before assigning any new ID.
    - A new ID is only created when the scraper cannot match the incoming data to any existing registry entry.
    - Re-running the scraper never reassigns or reuses an existing ID.
    - Removed models/columns are marked as retired in the registry, not deleted.

- JSON data file
  - Description: All model data is stored in a local JS data file (`data.js`) that the web page loads via a `<script>` tag. No other data source is used at runtime.
  - Priority: Must
  - Acceptance Criteria:
    - The data file schema (including stable IDs) is documented.
    - The web page loads and renders correctly using only the data file.
    - Adding a new model to the data file is sufficient to have it appear in the grid on next page load.

- Scraper process
  - Description: A runnable script (not part of the web page) fetches model data from msx.org wiki pages and openMSX GitHub XML files, merges them, and writes the output to the JSON data file.
  - Priority: Must
  - Acceptance Criteria:
    - The scraper can be invoked by the maintainer with a single command.
    - It scrapes MSX2, MSX2+, and MSX turbo R model pages from msx.org.
    - It parses machine XML files from the openMSX GitHub repository's share folder.
    - When both sources have data for the same model and the values conflict, the scraper summarizes all conflicts and prompts the maintainer to choose which value to keep before writing the output.
    - Parse failures are logged clearly so the maintainer can investigate.
    - Running the scraper again overwrites the previous data file (idempotent on data; preserves the ID registry).
    - The scraper reads and updates a persistent ID registry to ensure stable IDs across runs.

## Non-Functional Requirements

- No runtime dependencies on external servers
  - Target: Page loads and renders fully with no network requests at runtime (data file is local).
  - Priority: Must

- URL length
  - Target: URL remains under 2000 characters for any realistic view state (all columns shown, up to 50 cells selected).
  - Priority: Should

- Initial load time
  - Target: Grid is fully interactive within 3 seconds on a modern desktop browser over a local file or fast static host.
  - Priority: Should

- Browser compatibility
  - Target: Works in current versions of Chrome, Firefox, Edge, and Safari.
  - Priority: Should

- Scraper reliability
  - Target: Scraper logs a clear error and exits non-zero when a source cannot be parsed, rather than silently writing incomplete data.
  - Priority: Must

## Workflows

- Model lookup workflow
  - Trigger: User opens the page to look up or compare MSX model specs
  - Steps:
    1. User opens the URL (local or hosted)
    2. Grid loads with all models visible and default column layout
    3. User sorts, filters, shows/hides columns or rows to narrow focus
    4. User selects cells of interest and copies with CTRL+C / CMD+C
  - Success End State: User has the spec data they need
  - Failure States:
    - Data is missing or incorrect in the JSON
    - URL state fails to restore the view

- View sharing workflow
  - Trigger: User wants to share their current grid view with someone else
  - Steps:
    1. User configures the grid (sort, filter, selection, visible columns)
    2. User copies the URL from the browser address bar
    3. Recipient opens the URL
  - Success End State: Recipient sees the identical grid view
  - Failure States:
    - URL is too long to share via certain channels
    - URL state decoding fails on recipient's browser

- Data refresh workflow
  - Trigger: Maintainer wants to update model data
  - Steps:
    1. Maintainer runs the scraper command
    2. Scraper fetches data from msx.org and openMSX GitHub
    3. Merged JSON is written to the data file
    4. Maintainer reviews the output and commits the updated JSON
    5. Updated page is deployed (or used locally)
  - Success End State: JSON and page reflect the latest known data
  - Failure States:
    - Scraper fails due to source page structure change
    - Conflicting data between sources is not handled

## Success Criteria
- All MSX2, MSX2+, and MSX turbo R models from msx.org and openMSX XML are present in the grid.
- A user can sort, filter, and copy data without any page reload.
- Any grid state can be fully recreated from a URL alone.
- The scraper runs to completion with a single command and produces a valid JSON file.
- The page works identically when opened as `file://` and when served over HTTP.

## Assumptions
- msx.org wiki and openMSX GitHub XML files are publicly accessible and scrapeable.
- The number of in-scope models is small enough (likely < 200) that all rows can be rendered in the DOM without virtualization.
- The maintainer has Node.js or Python available locally to run the scraper.
- Column definitions (names and groups) are fixed at build/data time and do not change per-user at runtime.
- FPGA-based unofficial models will be included if they appear in the openMSX XML or have a dedicated msx.org wiki page.

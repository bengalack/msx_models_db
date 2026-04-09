# PRD: MSX Models DB

## Metadata
- Version: 0.6
- Date: 2026-04-01
er: bengalack

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
- MSX enthusia- Slot map extraction from msx.org wiki pages (deferred; XML-only for slot map data in this iteration).
- Slot map mirror detection from msx.org (deferred alongside msx.org slot map parsing).
- Default view configuration for slot map column groups (deferred to a later task).
sts / collectors (Primary)
- MSX researchers and developers (Secondary)
- bengalack, project maintainer (Internal)

## Scope
This iteration covers the web page (grid UI) and the offline scraper process. The web page is a static HTML/CSS/JS file that reads a local JSON data file — no server required. The scraper is a separate runnable process (not part of the web page) that the maintainer runs on demand to update the JSON. Both the page and the scraper are part of this repository.

## Functional Requirements

- Page title
  - Description: The page displays a title in the header showing authorship and data freshness.
  - Priority: Must
  - Acceptance Criteria:
    - The page title (both the header text and `document.title`) is "MSX Models DB by Bengalack · YYYY-MM-DD", where YYYY-MM-DD is the `generated` date from the data file.

- Grid display
  - Description: The page renders all in-scope MSX models as rows in a spreadsheet-like grid. Each column maps to a model attribute. The grid is the primary and only view.
  - Priority: Must
  - Acceptance Criteria:
    - All MSX2, MSX2+, and MSX turbo R models present in the JSON file appear as rows.
    - Each column defined in the JSON schema is rendered as a grid column.
    - The grid is readable and usable without horizontal scrolling for the Identity group at minimum.
    - The Identity group columns (Manufacturer, Model) and their group header are frozen/sticky during horizontal scroll.

- Column groups
  - Description: Columns are organized into named groups: Identity, Release, Memory, Video, Audio, Media, CPU/Chipsets, Other, Emulation. Each group has a header that can be clicked to collapse or expand all columns in that group.
  - Priority: Must
  - Acceptance Criteria:
    - Each column belongs to exactly one group.
    - Clicking a group header collapses all its columns (they disappear from view).
    - Clicking again expands them.
    - Collapsed state is reflected in the URL.

- Collapsed group header chevron visibility
  - Description: The collapse/expand chevron (▶) in a collapsed group header must remain visible on mouse-over. When collapsed, the header uses an inverted color scheme (text becomes background, background becomes text); the chevron must inherit that inverted foreground color so it is always legible, including on hover.
  - Priority: Must
  - Acceptance Criteria:
    - The chevron is visible at all times when the group header is collapsed — both at rest and on hover.
    - The chevron color matches the group header's current foreground text color in all states (normal, collapsed, collapsed+hover).

- Group filter indicator
  - Description: Each group header displays a FontAwesome filter icon when any column within that group has an active filter. The icon is a purely visual indicator (no click action). It is visible whether the group is expanded or collapsed, ensuring the user always knows which groups have active filters.
  - Priority: Must
  - Acceptance Criteria:
    - When one or more columns in a group have a non-empty filter value, the group header shows a FontAwesome filter icon.
    - When no columns in the group have an active filter, the icon is not displayed.
    - The icon is visible both when the group is expanded and when it is collapsed.
    - The icon does not interfere with the existing hidden-columns indicator or the collapse/expand chevron.
    - The icon is purely informational — clicking it does not trigger any action.
    - Clearing all filters in a group causes the icon to disappear immediately.

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
  - Description: Individual rows can be hidden. A visual indicator appears in the left gutter of the grid whenever one or more rows are hidden.
  - Priority: Must
  - Acceptance Criteria:
    - There is a UI control to hide a row (e.g. right-click context menu on row header).
    - Hidden rows are not rendered in the grid.
    - The left gutter shows a clear visual cue (e.g. a marker or gap indicator) between visible rows when one or more rows are hidden between them.
    - Clicking the gutter indicator reveals/unhides the hidden row(s).
    - Hidden row state is reflected in the URL.

- Cell selection
  - Description: Users can select one or more cells using mouse interactions. Selected cells are visually highlighted.
  - Priority: Must
  - Acceptance Criteria:
    - Click selects a single cell and deselects any previous selection.
    - CTRL+click (CMD+click on macOS) adds or removes a cell from the current selection.
    - SHIFT+click selects the rectangular range from the last-clicked cell to the current cell.
    - Click+hold and drag selects the visual range covered by the drag.
    - Selected cells are visually distinct from unselected cells (e.g. background color change).
    - Clicking outside the grid table on non-interactive space (not buttons, toolbar, headers, or gutter) clears all cell and row selection.
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

- Column configuration
  - Description: All column definitions (groups, columns, metadata, data sources, and derived-column rules) are maintained in a single source of truth. Adding, removing, hiding, or retiring a column requires editing only that one file. All downstream artifacts (data.js, ID registry) are generated from it automatically.
  - Priority: Must
  - Acceptance Criteria:
    - There is exactly one configuration file that defines all groups and columns with their full metadata (ID, key, label, short label, tooltip, group, type).
    - Adding a new column requires adding one entry to this file (plus scraper extraction logic if the column is scraped from an external source).
    - Removing a column during development (before the first public release) requires only deleting the entry from the configuration. No other files need manual changes.
    - Retiring a column after the first public release is done by setting a flag on the entry. The column's ID is preserved forever for URL compatibility, but the column is excluded from the generated data.js output.
    - A column can be marked as hidden: it is scraped and available as input to derived columns, but not shipped to the browser.
    - Derived columns are supported. A derived column specifies a Python function that receives the full merged row (including hidden columns) and returns the computed value. Derived columns are computed during the merge/build step and stored in data.js — not computed at runtime in the browser.
    - Defined derived column rules:
      - `nmos_cmos`: "CMOS" if the `engine` field matches `*T976*` (i.e. contains the substring "T976", e.g. T9769, T9769B, T9769C); "NMOS" otherwise.
      - `fpga_support`: "Yes" if the `engine` field matches `*Altera*` (i.e. contains the substring "Altera", e.g. Altera Cyclone IV); `null` (empty) otherwise.
    - The web page requires no column configuration of its own; it reads all column and group definitions from data.js at load time.

- Local supplemental data source
  - Description: A maintainer-curated JSON file (`data/local-raw.json`) serves as a third data source alongside openMSX XML and msx.org. It supplies data for fields that cannot be scraped automatically (e.g. SRAM, HIMEM Addr, Wait Cycles, NMOS/CMOS, RTC, Engine). Values in the local file take precedence over both openMSX and msx.org for any field they provide.
  - Priority: Must
  - Acceptance Criteria:
    - `data/local-raw.json` is a JSON array of model objects with the same schema as `msxorg-raw.json`.
    - Each entry requires at minimum `manufacturer` and `model` keys to match against the merged dataset.
    - During build, local values overwrite the openMSX+msx.org merged value for any field they supply.
    - Models present only in `local-raw.json` (not in openMSX or msx.org) are included in the output.
    - If `data/local-raw.json` is absent, the build completes normally (local source is optional).

- Cell value truncation
  - Description: Column definitions may specify an optional `truncate_limit` (positive integer). When a cell's string value exceeds this limit, the visible text is trimmed: the first `(truncate_limit − 1)` characters are shown, followed by `…`. A tooltip reveals the full value. When the cell also links to a URL, the tooltip shows `"<full value> — <url>"` on a single line. Sorting always uses the full original value from the data record, unaffected by truncation.
  - Priority: Must
  - Acceptance Criteria:
    - `ColumnDef` accepts an optional integer `truncate_limit` field (absent or `0` = no truncation).
    - The `Model` column has `truncate_limit = 10`.
    - The `Manufacturer` column has `truncate_limit = 10`.
    - A cell whose value length exceeds `truncate_limit` displays the first `(truncate_limit − 1)` characters followed by `…`.
    - A cell whose value length is at or below `truncate_limit` is displayed unchanged.
    - Hovering a truncated cell shows a native tooltip (`title`) containing the full, untruncated value.
    - When a truncated cell also carries a URL link, the tooltip is `"<full value> — <url>"` on a single line.
    - Sorting by a column with `truncate_limit` uses the full original value from the data record, not the truncated display string.

- Scraper process
  - Description: A runnable script (not part of the web page) fetches model data from msx.org wiki pages and openMSX GitHub XML files, merges them, computes derived columns, and writes the output to the JSON data file.
  - Priority: Must
  - Acceptance Criteria:
    - The scraper can be invoked by the maintainer with a single command.
    - It scrapes MSX2, MSX2+, and MSX turbo R model pages from msx.org.
    - It parses machine XML files from the openMSX GitHub repository's share folder.
    - When both sources have data for the same model and the values conflict, the scraper summarizes all conflicts and prompts the maintainer to choose which value to keep be    - When both sources have data for the same model and the values conflict, openMSX is used by default (it is considered the more authoritative source for hardware specifications). All conflicts are recorded in a file for maintainer review; the maintainer can override individual field choices and re-run the build with a resolutions file.
 ID registry).
    - The scraper reads and updates a persistent ID registry to ensure stable IDs across runs.
    - The scraper supports a build mode that skips fetching from external sources and instead uses previously cached raw data files on disk. This is the default mode; fetching is opt-in (e.g. via a `--fetch` flag).
    - External sources (msx.org, openMSX GitHub) change infrequently; the maintainer fetches fresh data only when needed.
    - When fetching a URL that is expected to exist and the server responds with HTTP 502 or 503, the scraper waits 2 seconds and retries the request. A warning is logged for each retry attempt. The maximum number of retries is 5; if all retries fail the error is propagated normally.

## Non-Functional Requirements

- No runtime dependencies on external servers
  - Target: Page loads and renders fully with no network requests at runtime (data file is local).
  - - Slot map columns
  - Description: Each model row exposes 64 fixed slot map columns across 4 column groups ("Slotmap, slot 0–3"), showing what occupies each page of each sub-slot. All models carry all 64 columns. Cells outside a model's physical slot configuration show `~`.
  - Priority: Must
  - Acceptance Criteria:
    - Four column groups are present: "Slotmap, slot 0", "Slotmap, slot 1", "Slotmap, slot 2", "Slotmap, slot 3".
    - Each group has exactly 16 columns named by the convention `SS / Pp` (sub-slot and page, with non-breaking spaces; e.g. `0 / P0`, `1 / P3`), covering 4 sub-slots × 4 pages. The main slot is shown in the group header.
    - Page numbers 0–3 correspond to Z80 address ranges 0x0000–0x3FFF, 0x4000–0x7FFF, 0x8000–0xBFFF, 0xC000–0xFFFF respectively.
    - All 64 columns are present for every model (uniform schema — no per-model column variation).
    - Cells outside a model's physically supported slot configuration display `~`.
    - Cells that contain valid content display a short abbreviation (e.g. `MAIN`, `CS1`, `DSK`).
    - Hovering a cell with an abbreviation shows a tooltip with the full human-readable description (e.g. "MSX BIOS with BASIC ROM").
    - Mirror cells display the origin abbreviation with `*` appended (e.g. `SUB*`, `DSK*`).
    - The `~` sentinel and mirror `*` notation are visually distinct from normal cell content.

- Slot map LUT
  - Description: A maintainer-controlled lookup table JSON file maps XML device types and `id` patterns to short abbreviations and tooltip strings. It is the single source of truth for slot map vocabulary. At build time it is used with regex matching; at runtime in the browser it is used for fast key-based tooltip lookup.
  - Priority: Must
  - Acceptance Criteria:
    - The LUT is a separate JSON file in the repository (not embedded in code).
    - Each LUT entry contains: XML element type (or `*` for id-only match), a case-insensitive regex pattern matched against the `id` attribute, a short abbreviation, and a tooltip string.
    - The browser receives the LUT as a key→tooltip map (keyed by abbreviation) embedded in `data.js`, so tooltip strings are stored once and not repeated per cell.
    - At scrape/build time, each device is classified by testing LUT rules in order; the first match wins.
    - If no LUT rule matches a device, the scraper emits a warning to stdout, writes the raw device string as the cell value (unabbreviated), and continues — it does not abort.
    - The maintainer can extend the LUT to handle newly encountered device strings without changing scraper code.
    - The starter LUT covers at minimum: `MAIN`, `SUB`, `KNJ`, `JE`, `FW`, `DSK`, `MUS`, `RS2`, `MM`, `PM`, `RAM`, `CS1`–`CS4` (explicit entries), `EXP`, `⌧`, `•`.
    - Cartridge slot abbreviations (`CS1`–`CS4`) are explicit LUT entries with their own tooltip text (e.g. "Cartridge slot 1"). They are not parameterised — each has its own entry so the browser can resolve their tooltip via the standard `{abbr: tooltip}` map.

- Slot map XML extraction
  - Description: The scraper extracts slot map data from openMSX machine XML files by walking the `<primary>` and `<secondary>` element hierarchy and classifying each device against the LUT.
  - Priority: Must
  - Acceptance Criteria:
    - Non-expanded primary slots (devices as direct children of `<primary>`, no `<secondary>` elements) are classified and written to sub-slot 0 columns; sub-slots 1–3 receive `~`.
    - Expanded primary slots (containing `<secondary slot="N">` children) are walked per sub-slot; missing sub-slot elements receive `~` for all 4 pages.
    - Cartridge/expansion slots (`<primary external="true" slot="N"/>`) produce `CS{N}` in all 4 pages of sub-slot 0, where `{N}` is a sequential 1-based counter incremented for each cartridge slot found (not the slot index); sub-slots 1–3 receive `⌧` (unless `<secondary external="true">` elements are present, which produce `EXP`).
    - Multiple devices in the same sub-slot with non-overlapping `<mem>` ranges are each assigned to their respective page(s); the cell value is the abbreviation of the device covering that page's address range.
    - If multiple devices overlap the same page, the scraper emits a warning and uses the first device encountered.
    - Mirror detection applies three methods (in order of precedence):
      1. Explicit `<Mirror>` element: `<mem>` defines affected pages; `<ps>`/`<ss>` identify the origin slot/device; those pages receive the origin abbreviation + `*`.
      2. ROM file smaller than `<mem>` range: ROM file size is looked up via SHA1 in `all_sha1s.txt` then measured on disk; pages within `<mem>` range beyond the ROM's byte coverage are mirrors; first page = original, rest = `<abbr>*`.
      3. `<rom_visibility>` narrower than `<mem>` range: pages within `<mem>` but outside `<rom_visibility>` are mirrors; `rom_visibility` page = original, others = `<abbr>*`.
    - If a SHA1 from the XML cannot be resolved to a file on disk (for method 2), the scraper skips mirror detection for that ROM and emits a warning.

Priority: Must

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
    1. Maintainer runs the scraper build command (uses cached raw data by default)
    2. If fresh data is needed, maintainer adds a fetch flag to also scrape msx.org and openMSX GitHub
    3. Scraper merges sources, computes derived columns, assigns stable IDs, and writes data.js
    4. Maintainer reviews the output and commits the updated data files
    5. Updated page is deployed (or used locally)
  - Success End State: JSON and page reflect the latest known data
  - Failure States:
    - Scraper fails due to source page structure change
    - Conflicting data between sources is not handled

- Development rebuild workflow
  - Trigger: Maintainer has changed column configuration (added, removed, hidden, or retired a column, or updated a derivation rule) and wants to see the result
  - Steps:
    1. Maintainer edits the column configuration file
    2. Maintainer runs the scraper build command (no fetch — uses cached raw data)
    3. Scraper regenerates data.js with updated columns and values
    4. Maintainer opens/reloads the page to verify
  - Success End State: The grid reflects the column changes immediately without re-fetching external data
  - Failure States:
    - Column key does not match any scraped field and is not a derived column (value will be null for all models)

## Success Criteria
- All MSX2, MSX2+, and MSX turbo R models from msx.org and openMSX XML are present in the grid.
- A user can sort, filter, and copy data without any page reload.
- Any grid state can be fully recreated from a URL alone.
- The scraper runs to completion with a single command and produces a valid JSON file.
- The page works identically when opened as `file://` and when served over HTTP.

## Assumptions
- msx.org wiki and openMSX GitHub XML files are publicly accessible and scrapeable.
- `data/local-raw.json` can override fields from both openMSX and msx.org for any model. Local values are assumed to be manually verified and authoritative.
- The number of in-scope models is small enough (likely < 200) that all rows can be rendered in the DOM without virtualization.
- The maintainer has Node.js or Python available locally to run the scraper.
- Column definitions (names, groups, derived rules) are fixed at build/data time and do not change per-user at runtime. They are maintained in a single Python configuration file and generated into data.js by the scraper.
- FPGA-based unofficial models will be included if they appear in the openMSX XML or have a dedicated msx.org wiki page. Specifically: **1chipMSX** and **Omega MSX** are in scope. MiSTer MSX core is out of scope (does not represent a distinct MSX model).
- The `systemroms/machines/` directory and `all_sha1s.txt` index are available locally when the scraper runs (required for ROM-size-based mirror detection).
- The starter LUT vocabulary covers all device types present in in-scope openMSX XML files; unknown strings will be rare and handled by maintainer LUT extension.

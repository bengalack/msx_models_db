# PRD: MSX Models DB

## Metadata
- Version: 0.16
- Date: 2026-04-17
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

- Page title
  - Description: The page displays a title in the header showing authorship and data freshness.
  - Priority: Must
  - Acceptance Criteria:
    - The page title (both the header text and `document.title`) is "MSX Models DB by Bengalack · N models · YYYY-MM-DD", where N is the total number of models in the data file (regardless of any active filters) and YYYY-MM-DD is the `generated` date from the data file.

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

- Selection column and row header highlight
  - Description: When any cell in a column is selected, that column's header cell displays inverted colors (text color becomes background color, background color becomes text color). The same inversion applies to the row number cell of any row that contains a selected cell.
  - Priority: Must
  - Acceptance Criteria:
    - While one or more cells in a column are selected, the column header for that column shows inverted colors.
    - While one or more cells in a row are selected, the row number cell for that row shows inverted colors.
    - When the selection is cleared, all column headers and row number cells revert to their normal colors immediately.
    - The inversion applies to all selected columns/rows simultaneously (multi-selection is supported).

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
      - `cartridge_slots`: count of distinct sub-slots in the final merged slotmap whose page-0 abbreviation matches `CS{N}` or `CS{N}!` (non-standard placement). Falls back to the hidden `scraped_cart_slots` field (set by the msx.org and openMSX scrapers) for models that have msx.org page text with a slot count but no HTML slot map table. Returns `null` if neither source has data.
      - `expansion_slots`: count of distinct sub-slots whose page-0 abbreviation matches `ES{N}` or `ES{N}!`. Returns `null` if no expansion slots are found. No fallback (no existing scraped source for expansion slot counts).
    - The web page requires no column configuration of its own; it reads all column and group definitions from data.js at load time.

- Local supplemental data source
  - Description: A maintainer-curated JSON file (`data/local-raw.json`) serves as a third data source alongside openMSX XML and msx.org. It supplies data for fields that cannot be scraped automatically (e.g. SRAM, HIMEM Addr, Wait Cycles, NMOS/CMOS, Engine). Values in the local file take precedence over both openMSX and msx.org for any field they provide.
  - Priority: Must
  - Acceptance Criteria:
    - `data/local-raw.json` is a JSON array of model objects with the same schema as `msxorg-raw.json`.
    - Each entry requires at minimum `manufacturer` and `model` keys to match against the merged dataset.
    - During build, local values overwrite the openMSX+msx.org merged value for any field they supply.
    - Models present only in `local-raw.json` (not in openMSX or msx.org) are included in the output.
    - If `data/local-raw.json` is absent, the build completes normally (local source is optional).

- Link-shares LUT
  - Description: A maintainer-curated JSON file (`data/link-shares.json`) allows models that have no msx.org page of their own to inherit the `links` entry from a donor model. This covers model variants (e.g. a regional or hardware-revision variant) that share the same msx.org wiki page as their base model.
  - Priority: Must
  - Acceptance Criteria:
    - `data/link-shares.json` is a flat JSON object whose keys and values are natural keys in the form `"manufacturer|model"` (lowercase, trimmed), matching the merge natural-key format.
    - Each entry maps a recipient model (key) to a donor model (value). The recipient will inherit the donor's `links` value in the output.
    - If the recipient already has its own `links` entry, the share entry is ignored (no overwrite).
    - If the donor model is not present in the dataset, or the donor itself has no `links` entry, the share entry is silently skipped and a warning is logged.
    - A model cannot share links with itself (self-reference is a load-time error).
    - If `data/link-shares.json` is absent, the build completes normally (link-shares is optional).

- Cell value truncation
  - Description: Column definitions may specify an optional `truncate_limit` (positive integer). When a cell's string value exceeds this limit, the visible text is trimmed: the first `(truncate_limit − 1)` characters are shown, followed by `…`. A tooltip reveals the full value. When the cell also links to a URL, the tooltip shows `"<full value> — <url>"` on a single line. Sorting always uses the full original value from the data record, unaffected by truncation.
  - Priority: Must
  - Acceptance Criteria:
    - `ColumnDef` accepts an optional integer `truncate_limit` field (absent or `0` = no truncation).
    - The `Model` column has a configurable default `truncate_limit = 16` (adjustable without regression).
    - The `Manufacturer` column has a configurable default `truncate_limit = 12` (adjustable without regression).
    - A cell whose value length exceeds `truncate_limit` displays the first `(truncate_limit − 1)` characters followed by `…`.
    - A cell whose value length is at or below `truncate_limit` is displayed unchanged.
    - Hovering a truncated cell shows a native tooltip (`title`) containing the full, untruncated value.
    - When a truncated cell also carries a URL link, the tooltip is `"<full value> — <url>"` on a single line.
    - Sorting by a column with `truncate_limit` uses the full original value from the data record, not the truncated display string.

- Column cell shading
  - Description: Column definitions may include a `shaded` boolean flag. When true, data cells in that column render with a subtle tinted background and bold text, providing a visual separator between alternating column groups.
  - Priority: Should
  - Acceptance Criteria:
    - `ColumnDef` accepts an optional `shaded?: boolean` field (absent or `false` = no shading).
    - Data cells (`<td>`) in a shaded column receive the `col-shaded` CSS class; header cells are not affected.
    - Two CSS custom properties per theme (`--color-surface-shaded` and `--color-surface-shaded-alt`) control the background for odd and even rows respectively, preserving row alternation.
    - Slot map columns for sub-slots 1 and 3 are shaded by default (every other sub-slot group) to aid visual separation across the 64-column block.
    - A column's `shaded` value is omitted from `data.js` when `false` (same convention as `linkable`).

- Scraper process
  - Description: A runnable script (not part of the web page) fetches model data from msx.org wiki pages and openMSX GitHub XML files, merges them, computes derived columns, and writes the output to the JSON data file.
  - Priority: Must
  - Acceptance Criteria:
    - The scraper can be invoked by the maintainer with a single command.
    - It scrapes MSX2, MSX2+, and MSX turbo R model pages from msx.org.
    - A model that appears in multiple msx.org category pages is assigned the highest generation. The ranking from lowest to highest is: MSX1 < MSX2 < MSX2+ < turbo R.
    - When a model's VDP field lists multiple chips (e.g. "V9938 / V9958"), the highest-ranked chip is used. The ranking from lowest to highest is: TMS99xx < V9938 < V9958.
    - It parses machine XML files from the openMSX GitHub repository's share folder.
    - When both sources have data for the same model and the values conflict, openMSX is used by default (it is considered the more authoritative source for hardware specifications). All conflicts are recorded in a file for maintainer review; the maintainer can override individual field choices and re-run the build with a resolutions file.
    - The scraper reads and updates a persistent ID registry to ensure stable IDs across runs.
    - The scraper supports a build mode that skips fetching from external sources and instead uses previously cached raw data files on disk. This is the default mode; fetching is opt-in (e.g. via a `--fetch` flag).
    - External sources (msx.org, openMSX GitHub) change infrequently; the maintainer fetches fresh data only when needed.
    - The msx.org scraper supports a local-mirror mode: `--msxorg-mirror DIR` reads category and model pages from a local directory of browser-saved HTML files (Save-As, HTML Only) instead of fetching live. `--local-msxorg-only` forces local-only mode. The default mirror path can be stored in `data/scraper-config.json` under the key `msxorg_mirror`; the CLI flag always takes precedence. File names follow browser Save-As output: `https://www.msx.org/wiki/<Title>` → `<Title>.html`. If a model file is absent from the mirror, the scraper warns and skips that model; the rest of the build continues. If the mirror directory does not exist, the scraper aborts the msx.org portion with a clear error. The same HTML parsers are used as for live pages — no divergent code path.
    - The openMSX scraper supports a local-mirror mode: `--openmsx-mirror DIR` reads machine XML files from a local directory (e.g. a local clone of the openMSX repository) instead of fetching from GitHub. `--local-openmsx-only` forces local-only mode. The default mirror path can be stored in `data/scraper-config.json` under the key `openmsx_mirror`; the CLI flag always takes precedence.
    - When fetching a URL that is expected to exist and the server responds with HTTP 502 or 503, the scraper waits 2 seconds and retries the request. A warning is logged for each retry attempt. The maximum number of retries is 5; if all retries fail the error is propagated normally.
    - For each machine XML, the scraper detects the presence of an `<RTC>` element anywhere under the `<devices>` section and populates the `rtc` field with `"Yes"` if found or `"No"` if the XML was parsed but no `<RTC>` element is present. Models with no openMSX XML file receive an empty/null `rtc` value. msx.org does not supply RTC data; only openMSX XML is used for this field.
    - For each machine XML, the scraper reads `<devices><Matsushita><hasturbo>` and populates the `z80_turbo` field with `"Yes"` if the element text is `"true"`, or `"No"` in all other cases (including when `<Matsushita>` is absent or `<hasturbo>` is absent or not `"true"`). Models with no openMSX XML file receive an empty/null `z80_turbo` value. The `z80_turbo` column is in the CPU/Chipsets group. msx.org does not supply this data; only openMSX XML is used for this field.
    - For memory extraction, the scraper treats `<PanasonicRAM>` (a proprietary implementation of the standard MSX memory mapper interface) as implying `mapper = "Yes"`. The rule applied is: `<MemoryMapper>` present → `mapper = "Yes"`; `<PanasonicRAM>` present → `mapper = "Yes"` (takes precedence over a plain `<RAM>` in the same XML); `<RAM>` alone → `mapper = "No"`. When multiple RAM-typed elements are present, their sizes are summed for the `ram` field; `mapper` is "Yes" if any `<MemoryMapper>` or `<PanasonicRAM>` element is found, otherwise "No".
    - The `cpu_speed_mhz` column (CPU Speed (MHz)) is removed. Its ID (23) is retired and must not be reused.

- Alias LUT
  - Description: A maintainer-curated JSON file (`data/aliases.json`) normalizes known name variants to their canonical forms before merge, enabling cross-source records that differ only in name spelling to match correctly. Two rule types are supported: single-column rules (normalize one field independently) and composite rules (normalize multiple fields only when all specified fields match simultaneously).
  - Priority: Must
  - Acceptance Criteria:
    - `data/aliases.json` supports two rule types at the top level:
      - **Single-column rules** (existing): a field name key maps to `{ canonical: [alias, ...] }` objects. Any record whose named field matches an alias is rewritten to the canonical value.
      - **Composite rules**: a `"composite"` key holds an array of `{ "match": {col: val, ...}, "canonical": {col: val, ...} }` objects. A rule fires only when **all** `match` fields match simultaneously; all `canonical` fields are then written into the record. Rules are evaluated in list order; the first matching rule wins.
    - Before computing the merge natural key, every record from all sources is passed through the alias LUT: single-column rules first, then composite rules.
    - Matching is case-insensitive for both rule types.
    - An alias string mapped to two different canonical names in the same field is rejected at load time with a `ValueError`.
    - A composite rule with a missing or non-dict `match`/`canonical` key, an empty `match` dict, or a non-string field value is rejected at load time with a `ValueError`.
    - If `data/aliases.json` is absent, no aliasing occurs and the build proceeds normally.

- Build timing
  - Description: The scraper logs elapsed time so the maintainer can see how long each phase took.
  - Priority: Should
  - Acceptance Criteria:
    - At the end of every build, total elapsed time is logged.
    - When `--fetch` is used, each data source (openMSX, msx.org) additionally logs its individual fetch duration.
    - Times are reported to one decimal place in seconds (e.g. `42.3s`).

- Scraper exclude list
  - Description: A maintainer-curated JSON file (`data/exclude.json`) prevents unwanted models from appearing in the output. Models matching an exclusion rule are dropped after parsing, before being added to the merged dataset.
  - Priority: Should
  - Acceptance Criteria:
    - `data/exclude.json` is a JSON array of rule objects. Each rule uses exactly one mode: `{"manufacturer": "...", "model": "..."}` or `{"filename": "..."}` (not both).
    - Manufacturer/model matching supports `"*"` as a wildcard (matches any value including empty) and `""` to match an empty field. Matching is case-sensitive.
    - Filename rules apply only to the openMSX scraper (exact match against XML filename); they are silently ignored by the msx.org scraper.
    - A model excluded by any matching rule does not appear in `docs/data.js` after a build.
    - If `data/exclude.json` is absent or empty, the build output is identical to one without the file (no-op).
    - A malformed `exclude.json` (invalid JSON, unknown keys in an entry) raises a `ValueError` at startup before any network requests are made.
    - After each build run, any rule that matched zero models produces a WARN log line.
    - The per-scraper build summary includes an `excluded` count alongside the existing `skipped`/`errors` counts.

- Slot map columns
  - Description: Each model row exposes 64 fixed slot map columns across 4 column groups ("Slotmap, slot 0–3"), showing what occupies each page of each sub-slot. All models carry all 64 columns. Cells outside a model's physical slot configuration show `⌧`.
  - Priority: Must
  - Acceptance Criteria:
    - Four column groups are present: "Slotmap, slot 0", "Slotmap, slot 1", "Slotmap, slot 2", "Slotmap, slot 3".
    - Each group has exactly 16 columns named by the convention `SS / Pp` (sub-slot and page, with non-breaking spaces; e.g. `0 / P0`, `1 / P3`), covering 4 sub-slots × 4 pages. The main slot is shown in the group header.
    - Page numbers 0–3 correspond to Z80 address ranges 0x0000–0x3FFF, 0x4000–0x7FFF, 0x8000–0xBFFF, 0xC000–0xFFFF respectively.
    - All 64 columns are present for every model (uniform schema — no per-model column variation).
    - Cells outside a model's physically supported slot configuration display `⌧`.
    - Cells that contain valid content display a short abbreviation (e.g. `MAIN`, `CS1`, `DSK`).
    - Hovering a cell with an abbreviation shows a tooltip with the full human-readable description (e.g. "MSX BIOS with BASIC ROM").
    - Mirror cells display the origin abbreviation with `*` appended (e.g. `SUB*`, `DSK*`).
    - The `⌧` sentinel and mirror `*` notation are visually distinct from normal cell content.

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
    - The starter LUT covers at minimum: `MAIN`, `SUB`, `KNJ`, `JE`, `FW`, `DSK`, `MUS`, `RS2`, `MM`, `PM`, `RAM`, `CS1`–`CS6`, `ES1`–`ES6` (explicit entries), `EXP`.
    - Cartridge slot abbreviations (`CS1`–`CS6`) and expansion slot abbreviations (`ES1`–`ES6`) are explicit LUT entries with their own tooltip text. Non-standard subslot variants (`CS1!`–`CS6!`, `ES1!`–`ES6!`) are also explicit entries. They are not parameterised — each has its own entry so the browser can resolve their tooltip via the standard `{abbr: tooltip}` map.

- Slot map XML extraction
  - Description: The scraper extracts slot map data from openMSX machine XML files by walking the `<primary>` and `<secondary>` element hierarchy and classifying each device against the LUT.
  - Priority: Must
  - Acceptance Criteria:
    - Non-expanded primary slots (devices as direct children of `<primary>`, no `<secondary>` elements) are classified and written to sub-slot 0 columns; sub-slots 1–3 receive `⌧`.
    - Expanded primary slots (containing `<secondary slot="N">` children) are walked per sub-slot; missing sub-slot elements receive `⌧` for all 4 pages.
    - External primary slots (`<primary external="true" slot="N"/>`) and external secondary slots (`<secondary external="true" slot="N"/>`) produce `CS{N}[!]` in the openMSX extraction path, because the XML does not distinguish cartridge slots from expansion slots. The merge step (see "Slot map CS/ES resolution") upgrades `CS` to `ES` where msx.org data is available.
    - Cartridge/expansion slots at the primary level produce `CS{N}` in all 4 pages of sub-slot 0; sub-slots 1–3 receive `⌧` for unoccupied sub-slots.
    - External slots placed inside an expanded primary slot (`<secondary external="true" slot="N">`) produce `CS{N}!` on all 4 pages of that sub-slot. The `!` suffix signals non-standard placement.
    - Multiple devices in the same sub-slot with non-overlapping `<mem>` ranges are each assigned to their respective page(s); the cell value is the abbreviation of the device covering that page's address range.
    - If multiple devices overlap the same page, the scraper emits a warning and uses the first device encountered.
    - Mirror detection applies three methods (in order of precedence):
      1. Explicit `<Mirror>` element: `<mem>` defines affected pages; the origin abbreviation + `*` is written to those pages.
      2. ROM file smaller than `<mem>` range: ROM file size is looked up via SHA1 in `all_sha1s.txt` then measured on disk; pages beyond the ROM's byte coverage are mirrors (`<abbr>*`).
      3. `<rom_visibility>` narrower than `<mem>` range: pages within `<mem>` but outside `<rom_visibility>` are mirrors (`<abbr>*`).
    - If a SHA1 from the XML cannot be resolved to a file on disk (for method 2), the scraper skips mirror detection for that ROM and emits a warning.

- Slot map HTML extraction
  - Description: The scraper extracts slot map data from msx.org wiki pages by parsing the HTML Slot Map table section and classifying cell text into the same abbreviations as the XML extraction path.
  - Priority: Must
  - Acceptance Criteria:
    - The parser finds the first `<h2><span id="Slot_Map" …>` heading on the page; if multiple Slot Map headings exist (e.g. 1chipMSX with default and upgraded configurations), only the first is used.
    - A cell is treated as a **cartridge slot** (CS) if its text contains the word `cartridge` (case-insensitive, e.g. "Cartridge Slot 1", "Mini Cartridge Slot").
    - A cell is treated as an **expansion slot** (ES) if its text contains the word `slot` but not `cartridge`. This covers "Module Slot", "Slot CN…" (internal connectors), and positional names such as "Lowest back slot", "Middle back slot", "Top back slot".
    - Cartridge slots (CS) in a non-expanded main slot produce `CS{N}` on all 4 pages of sub-slot 0. Expansion slots (ES) produce `ES{N}`. Slots in an expanded main slot (multiple sub-slot columns) receive the `!` suffix: `CS{N}!` or `ES{N}!`, following the same convention as the XML extraction path.
    - CS and ES use independent sequential counters, each starting at 1, incremented left-to-right across the table.
    - Cell text is matched against the `id_pattern` fields in `data/slotmap-lut.json` in order (first match wins). LUT entries with a null `id_pattern` (element-name-only entries) are covered by a supplemental list that matches their typical msx.org free-text descriptions.
    - All other slot map conventions (64-key output, `⌧`/`•` sentinels, sequential numbering) are identical to those of the XML extraction path.

- Slot map CS/ES resolution
  - Description: openMSX XML cannot distinguish a cartridge slot from an expansion slot; both are encoded as `<primary external="true">`. The msx.org HTML scraper can tell them apart from the cell text. The merge step uses this to upgrade provisional `CS{N}` values from openMSX to `ES{N}` where msx.org data is available, then renumbers all CS and ES slots with fresh, independent counters.
  - Priority: Must
  - Acceptance Criteria:
    - For any slotmap cell where openMSX emits `CS{N}` and msx.org emits `ES{M}`, the merged result uses `ES` (msx.org wins for the CS/ES type distinction only).
    - For any slotmap cell where both sources emit `CS`, or where only one source has data, the existing merge precedence rules apply.
    - After type resolution, all slotmap keys in the merged model are renumbered: the model's slots are walked in order (main slot 0→3, sub-slot 0→3), and independent counters assign `CS1`, `CS2`, … and `ES1`, `ES2`, … fresh from 1. The `!` suffix is preserved during renumbering.
    - Renumbering runs for every merged model that contains at least one CS or ES value (including models present only in openMSX or only in msx.org, to normalise stale provisional numbers).

## Non-Functional Requirements

- No runtime dependencies on external servers
  - Target: Page loads and renders fully with no network requests at runtime (data file is local).
  - Priority: Must

- Static deployment compatibility
  - Target: Page renders correctly via file://, HTTP static host, and embedded in Blogger/Blogspot — no build step or server required.
  - Priority: Must

- URL backwards-compatibility
  - Target: Every URL ever shared remains valid forever; unknown IDs are silently ignored, never cause errors.
  - Priority: Must

- Performance
  - Target: Initial render of the full grid completes in under 2 seconds on a modern desktop browser with a local file:// load.
  - Priority: Should

## Workflows

- Browsing and comparing models
  - Trigger: User opens the page (locally or via hosted URL).
  - Steps:
    1. Page loads `data.js` and renders the full grid.
    2. User sorts by a column to rank models.
    3. User enters filter values to narrow the row set.
    4. User collapses irrelevant column groups to reduce visual noise.
    5. User hides individual rows or columns as needed.
    6. User clicks or drags to select cells of interest.
    7. User presses CTRL+C to copy selected cell values to the clipboard.
  - Success End State: User has the comparative data they need and can paste it into a spreadsheet or document.
  - Failure States:
    - Data file is missing or malformed — page renders no rows.
    - A filter produces zero results — user sees an empty grid with no indication of why.

- Sharing a view
  - Trigger: User wants to share their current grid view with someone else.
  - Steps:
    1. User configures the view (sort, filters, collapsed groups, hidden columns/rows, cell selection).
    2. User copies the current URL (hash updates live — no extra action needed).
    3. Recipient opens the URL in a browser.
    4. Recipient's page loads and reproduces the exact same view.
  - Success End State: Recipient sees an identical grid view.
  - Failure States:
    - URL is too long for the sharing medium (e.g. SMS). Mitigation: compact binary encoding minimises URL length.
    - Recipient's browser is too old to support required JS features — page may not render.

- Refreshing the data
  - Trigger: Maintainer wants to update the model database.
  - Steps:
    1. Maintainer optionally updates `data/local-raw.json` with new or corrected values.
    2. Maintainer runs the scraper in build mode (`python scraper/build.py`) to regenerate from cached raw data, or with `--fetch` to also pull fresh data from msx.org and openMSX GitHub.
    3. Scraper merges all sources, applies alias normalisation, computes derived columns, and writes `docs/data.js`.
    4. Maintainer reviews the conflict log (if any) and optionally edits a resolutions file, then re-runs.
    5. Maintainer commits and deploys the updated `docs/data.js`.
  - Success End State: `docs/data.js` reflects current known data; the web page shows updated models on next load.
  - Failure States:
    - msx.org page structure has changed — scraper emits parse warnings and may produce incomplete data.
    - openMSX XML schema has evolved — scraper may misclassify devices; maintainer reviews warnings.
    - Conflicting data between sources — conflict log is written; maintainer resolves manually.

## Success Criteria

- A user can open the page and immediately see all MSX2, MSX2+, and MSX turbo R models in a sortable, filterable grid.
- Sort, filter, column/row visibility, and group collapse all work without page reload.
- Any view state can be shared via a URL that exactly reproduces the view in a new tab.
- The maintainer can refresh the data with a single command and no manual JSON editing (beyond `local-raw.json` for fields that cannot be scraped).
- The page works correctly as a local `index.html`, as a GitHub Pages site, and embedded in Blogger/Blogspot.
- All previously shared URLs remain valid after data updates.

## Assumptions

- msx.org wiki article pages are scrapable (robots.txt permits general crawlers on article paths).
- The msx.org Slot Map HTML table structure is sufficiently consistent across model pages for a single parser to handle all variants.
- openMSX GitHub XML schema remains stable enough that the existing parser handles new machine files without code changes.
- Users are on modern desktop browsers (Chrome, Firefox, Edge, Safari current − 1). Mobile is not a supported target.
- Data updates are infrequent; the maintainer triggers them on demand rather than on a schedule.
- 1chipMSX and Omega MSX have dedicated msx.org wiki pages and are treated as first-class models.
- The MiSTer MSX core is not a distinct MSX model and is excluded from the dataset.
- `data/local-raw.json` is the only mechanism for supplying fields that cannot be scraped; no other manual override path is needed.

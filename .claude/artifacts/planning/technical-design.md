# Technical Design: MSX Models DB

## Metadata
- Date: 2026-04-01
- Related:
  - PRD: .claude/artifacts/planning/product-requirements.md
  - Risk review: .claude/artifacts/planning/risk-assumption-review.md
  - Decision log: .claude/artifacts/decisions/decision-log.md
  - UX guide: .claude/artifacts/planning/ux-design-guide.md
  - Open questions: .claude/artifacts/decisions/open-questions.md

## System Shape

The system has two independent sub-systems that share a single artifact: `docs/data.js`.

The **web page** is a static TypeScript app built with Vite. It reads `data.js` at load time via a `<script>` tag, renders a grid, and manages all state client-side. The build output (`docs/`) is committed to the repository and served directly by GitHub Pages, opened as `file://`, or embedded in Blogger.

The **scraper** is an offline Python CLI. The maintainer runs it on demand to fetch model data from msx.org and openMSX GitHub, merge the results (with interactive conflict resolution), and write a fresh `docs/data.js`. It also maintains `data/id-registry.json` — a committed file that maps model/column identities to their stable integer IDs across all scraper runs.

No server is involved at any point. The two sub-systems only communicate through files on disk.

The slot map feature adds 64 columns per model, extracted exclusively from openMSX machine XML files. A maintainer-controlled **Slot Map LUT** (`data/slotmap-lut.json`) maps XML device types and `id` patterns to short abbreviations and tooltip strings. The LUT is consumed by the scraper at build time (regex matching) and embedded in `data.js` as a compact key→tooltip map for runtime tooltip lookup in the browser. Mirror cells are detected in the XML via three methods (explicit `<Mirror>` element, ROM file size vs mapped range, `<rom_visibility>` vs `<mem>` range) and encoded as `<abbr>*` in the output.

## Domain Boundaries

- Web page (UI)
  - Responsibilities: Render grid, manage view state, encode/decode URL hash, handle user interactions
  - Owns Data: In-memory view state (sort, filters, selection, hidden rows/cols, collapsed groups); reads MSXData from window at load
  - External Interfaces: Reads `window.MSX_DATA` (set by data.js); writes URL hash via `history.replaceState`

- Scraper (data pipeline)
  - Responsibilities: Fetch, parse, merge all three sources, compute derived columns, conflict-resolve, and write model data; maintain model ID registry; extract and classify slot map data from openMSX XML; detect slot map mirrors
  - Owns Data: `scraper/columns.py` (single source of truth for column/group definitions); `data/id-registry.json` (source of truth for model IDs); `data/slotmap-lut.json` (slot map vocabulary — maintained by maintainer); `data/local-raw.json` (manually curated supplemental data, highest authority); writes `docs/data.js`
  - Merge strategy: openMSX + msx.org merged first (openMSX wins on conflict); local overrides applied on top (local wins for any field it provides)
  - External Interfaces: HTTP GET to msx.org (HTML scraping); HTTP GET to raw.githubusercontent.com or GitHub API (XML files); stdin/stdout for conflict prompts; read-only access to `systemroms/machines/` (ROM file size lookups for mirror detection)

## Components

- Grid App (web page)
  - Type: Web App (static SPA)
  - Responsibilities: Grid display, column groups, sort/filter, row/column show-hide, cell selection, clipboard copy, URL state sync, theme toggle, **sticky headers and sticky left gutter**
  - Sticky UI: Implements four sticky header rows (page header, toolbar, group header, column header, filter row) and a sticky left gutter (row numbers, hide/unhide controls, gap indicators) as per UX guide. All sticky elements remain visible during both horizontal and vertical scroll, ensuring context is preserved for large grids and wide slot map columns.
  - Sticky Columns: The left gutter (row numbers, hide/unhide) is implemented as a sticky column, always visible regardless of horizontal scroll. The Identity group columns (Manufacturer, Model) are also frozen/sticky during horizontal scroll, pinned immediately to the right of the gutter. The Identity group header is likewise frozen. Gap indicator rows include frozen cells in the frozen panel so the dashed line remains visible. Sticky slot map columns may be considered in future versions if user need arises.
  - Slot Map Columns: Renders all 64 slot map columns (4 groups × 16 columns) for every model, with group headers and tooltips as defined in the requirements. Cells outside a model's physical slot configuration display `~`. Mirror cells display `<abbr>*` and are visually distinct. All slot map columns are scrollable horizontally, but their group headers and column headers remain sticky.
  - Group Filter Indicator: Each group header `<th>` contains a FontAwesome `fas fa-filter` icon element (hidden by default). When any column in the group has a non-empty filter value, the header gets class `group-header--filtered` which reveals the icon. The `recalcGroupHeader()` function handles this alongside its existing `group-header--partial` logic. The indicator is visible in both expanded and collapsed states.
  - Depends On: `window.MSX_DATA` (set by data.js before app script runs)
  - Data Stores: In-memory only (no localStorage except theme preference)

- URL Codec
  - Type: Library (module within Grid App)
  - Responsibilities: Serialize/deserialize full view state to/from a compact binary payload; base64-encode for URL hash
  - Depends On: Grid state types
  - Data Stores: URL hash fragment (`window.location.hash`)

- Column Configuration
  - Type: Python module (single source of truth)
  - Responsibilities: Define all column groups, columns (with metadata, display order, types), derived-column rules, hidden/retired flags. All downstream artifacts are generated from this file.
  - Depends On: -
  - Data Stores: `scraper/columns.py` (source code)

- Scraper CLI
  - Type: Job (offline Python script)
  - Responsibilities: Scrape msx.org, parse openMSX XML, load local supplemental data, merge all three sources, compute derived columns, prompt on conflicts, assign/reuse stable model IDs, write data.js
  - Depends On: `scraper/columns.py` (column config), id-registry.json (model IDs), msx.org HTTP or local mirror (`PageSource`), GitHub API/raw HTTP or local mirror (`XMLSource`)
  - Data Stores: `data/id-registry.json` (read+write), `docs/data.js` (write), `data/scraper-config.json` (read, optional), `data/local-raw.json` (read-only, optional), `data/aliases.json` (read-only, optional), `data/link-shares.json` (read-only, optional)

- msx.org Page Source
  - Type: Library (module `scraper/mirror.py`)
  - Responsibilities: Abstract the origin of msx.org HTML pages behind a `PageSource` protocol so the rest of the scraper is source-agnostic. Three implementations:
    - `LivePageSource` — fetches from the live msx.org website; returns `None` + logs on any HTTP error.
    - `MirrorPageSource` — reads browser-saved HTML files from a local directory. Filename convention: wiki URL slug → URL-decode → underscores→spaces → colons→underscores → append ` - MSX Wiki.html`. Returns `None` + WARN when a file is missing; ERROR when the directory is missing.
    - `FallbackPageSource` — wraps live + mirror; tries live first, falls back to mirror on failure.
  - CLI flags (on `build` and `fetch-msxorg`):
    - `--msxorg-mirror DIR` — enables FallbackPageSource (live-with-fallback)
    - `--msxorg-mirror DIR --local-msxorg-only` — enables MirrorPageSource (skip live entirely)
    - No flag — LivePageSource (default)
  - Config: `data/scraper-config.json` key `msxorg_mirror` provides a persistent default mirror path; CLI flag overrides it.
  - Depends On: `requests` (live), filesystem (mirror)
  - Data Stores: local mirror directory (read-only)

- openMSX XML Source
  - Type: Library (module `scraper/openmsx_source.py`)
  - Responsibilities: Abstract the origin of openMSX machine XML files behind an `XMLSource` protocol so the rest of the scraper is source-agnostic. Three implementations:
    - `LiveXMLSource` — lists files via GitHub API and fetches each from raw.githubusercontent.com; caches download URLs from the listing response.
    - `MirrorXMLSource` — reads `.xml` files from a local directory (e.g. the openMSX `share/machines` folder). Lists files via `glob("*.xml")` (sorted, skip-prefixes applied). Returns `None` + WARN when a file is missing; ERROR when the directory is missing. No delay between reads.
    - `FallbackXMLSource` — wraps live + mirror; tries GitHub first, falls back to mirror on any listing or fetch failure.
  - CLI flags (on `build` and `fetch-openmsx`):
    - `--openmsx-mirror DIR` — enables FallbackXMLSource (live-with-fallback)
    - `--openmsx-mirror DIR --local-openmsx-only` — enables MirrorXMLSource (skip GitHub entirely)
    - No flag — LiveXMLSource (default)
  - Config: `data/scraper-config.json` key `openmsx_mirror` provides a persistent default mirror path; CLI flag overrides it.
  - Depends On: `requests` (live), filesystem (mirror)
  - Data Stores: local mirror directory (read-only)

- ID Registry
  - Type: File artifact (JSON)
  - Responsibilities: Map model natural keys to permanent integer IDs; record retired model IDs. Column IDs are defined in `scraper/columns.py` and are not part of the registry.
  - Depends On: -
  - Data Stores: `data/id-registry.json`

- Link-Shares LUT
  - Type: File artifact (JSON), maintainer-controlled
  - Responsibilities: Allow models with no msx.org page of their own to inherit the `links` entry from a donor model. Keys and values are natural keys (`"manufacturer|model"`, lowercase). Applied in the build step after per-model `links` are computed and before the models list is sorted.
  - Depends On: -
  - Data Stores: `data/link-shares.json`

- Slot Map LUT
  - Type: File artifact (JSON), maintainer-controlled
  - Responsibilities: Define the vocabulary for slot map cell classification. Each entry maps an XML element type + case-insensitive `id` regex pattern to a short abbreviation and tooltip string. Rules are tested in order; first match wins. Embedded in `data.js` at build time as a compact `{ abbr: tooltip }` map for browser-side tooltip rendering.
  - Depends On: -
  - Data Stores: `data/slotmap-lut.json`

- Slot Map Extractor
  - Type: Library (module within Scraper CLI)
  - Responsibilities: Walk `<primary>`/`<secondary>` XML hierarchy per machine; classify each device via LUT; compute page assignments from `<mem base size>`; detect mirrors via three methods; emit 64 slot map column values per model; warn on unknown device strings (never abort)
  - Depends On: `data/slotmap-lut.json`, `systemroms/machines/all_sha1s.txt` + ROM files (optional; for mirror method 2)
  - Data Stores: -

## Key Flows

- Page load and state restore
  - Trigger: User opens URL (file://, HTTP, or Blogger embed)
  - Steps:
    1. Browser executes `<script src="data.js">` — sets `window.MSX_DATA`
    2. Browser executes `<script src="bundle.js">` — app initialises
    3. App reads `window.MSX_DATA` (columns, groups, models)
    4. App reads `window.location.hash`; if non-empty, URL Codec decodes it into view state
    5. If hash is empty, app loads default view config from `MSX_DATA.defaultView` (or falls back to show-all)
    6. Grid renders with decoded state
  - Data touched: window.MSX_DATA, window.location.hash
  - Failure handling: Unknown IDs in decoded hash are silently dropped. If data.js is missing (file:// without data.js), app renders an error message.

- User interaction → URL update
  - Trigger: Any state-changing interaction (sort, filter, select, hide/show, collapse)
  - Steps:
    1. Event handler updates in-memory view state object
    2. Grid re-renders affected DOM regions (targeted updates, not full re-render)
    3. URL Codec serializes full view state → binary payload → base64
    4. `history.replaceState(null, '', '#' + encoded)` updates hash without page reload
  - Data touched: in-memory state, URL hash
  - Failure handling: Codec errors are caught and logged; URL update is skipped (state still applies visually)

- Clipboard copy
  - Trigger: CTRL+C / CMD+C keydown when selection is non-empty
  - Steps:
    1. Collect selected cells (sorted by row then column display order)
    2. Build TSV string: rows joined by `\n`, columns by `\t`
    3. Write to clipboard via `navigator.clipboard.writeText()`
    4. Show status bar message: `Copied N cell(s)`
  - Data touched: in-memory selection state
  - Failure handling: If clipboard API unavailable (some file:// environments), fall back to `document.execCommand('copy')` on a hidden textarea

- Filter state → group header indicator
  - Trigger: Any code path that modifies the `filters` Map (filter input handler, filter clear button, toggleFilters hide-all, URL state restore)
  - Steps:
    1. After modifying `filters`, determine affected group ID(s) from the column's `groupId`
    2. In `recalcGroupHeader(groupId)`: check whether any column in the group has a non-empty entry in `filters`
    3. Toggle `group-header--filtered` class on the group `<th>` accordingly
    4. CSS rule `.group-header--filtered .filter-indicator { display: inline }` reveals the icon; removal hides it
  - Data touched: `filters` Map (read-only), group header DOM element (class toggle)
  - Failure handling: If the group header `<th>` is not found (group has 0 visible columns), skip silently — same as existing `recalcGroupHeader` behavior

- Scraper build (primary workflow)
  - Trigger: Maintainer runs `python -m scraper build` (or `build --fetch` for fresh data)
  - Steps:
    1. Load column configuration from `scraper/columns.py` (groups, columns, derive functions); validate (no duplicate IDs, no ID 0, group refs valid, etc.)
    2. Load cached raw data from `data/openmsx-raw.json` and `data/msxorg-raw.json`; rename `"standard"` → `"generation"` in cached dicts for backward compatibility
    3. Load local supplemental data from `data/local-raw.json` (optional; absent file is not an error)
    4. If `--fetch`: fetch fresh data from msx.org and openMSX GitHub first, overwriting cached files
    5. Merge msx.org and openMSX data per model (openMSX wins on conflict); then apply local overrides on top (local wins for any field it provides)
    5a. After all per-model `links` are computed (keyed model URLs from `msxorg_title`), apply `data/link-shares.json`: for each entry whose recipient has no `links`, copy the donor's `links` (if present). Absent file is silently skipped.
    6. Compute derived columns: for each model row, run every `Column.derive` callable; store results under the column's key
    7. Load `data/id-registry.json`; match models by natural key (manufacturer + model name); assign new IDs for unmatched entries
    8. Build output: generate `docs/data.js` with groups (from config), active columns (excluding hidden/retired), and model values[] positionally aligned to active columns
    9. Atomic write `docs/data.js` and `data/id-registry.json`
    10. Print summary: N models written, M conflicts resolved, K parse failures
  - Data touched: id-registry.json (read+write), docs/data.js (write), cached raw JSON (read, or write if --fetch)
  - Failure handling: HTTP errors → retry once, then log and skip model. Parse failures → log field name and raw value, continue. If >20% of models fail to parse, abort before writing output. Missing cached files without --fetch → error with clear message.

- Slot map extraction (per machine XML)
  - Trigger: Scraper processes an openMSX machine XML file during the build flow
  - Steps:
    1. Parse XML with `lxml` (`recover=True`); locate `<devices>` element
    2. First pass — walk all `<primary slot="N">` elements:
       - If `external="true"`: classify as `CS{N}` for sub-slot 0 pages 0–3; mark sub-slots 1–3 as `~`
       - If no `<secondary>` children: classify direct child devices against LUT; assign to pages via `<mem base size>`; mark sub-slots 1–3 as `~`
       - If `<secondary>` children present: for each sub-slot 0–3, classify child devices against LUT and assign pages; any missing sub-slot element → `~` for all 4 pages
    3. For each device assignment: determine which pages (0–3) its `<mem>` range covers (page N = range intersects [N×0x4000, (N+1)×0x4000)); assign abbreviation to those pages
    4. If no LUT rule matches a device: emit `[WARN] Unmatched device: <element> id="<id>" in <filename>` to stdout; write raw device string as cell value
    5. Second pass — resolve mirrors:
       - Method 1 (`<Mirror>` elements): look up referenced slot by `<ps>`/`<ss>`; find abbreviation already assigned to that slot in pass 1; write `<abbr>*` to the pages covered by `<Mirror>`'s `<mem>` range
       - Method 2 (ROM file size): for each ROM device, look up all `<sha1>` values in `all_sha1s.txt`; try each until a file is found on disk; measure file size; compare to byte count covered by `<mem>`; pages beyond file size → `<abbr>*`; warn if no SHA1 resolves
       - Method 3 (`<rom_visibility>`): pages within `<mem>` range but outside `<rom_visibility>` range → `<abbr>*`; `rom_visibility` page = original
    6. Write all 64 slot map values to the model record (keyed by column key, e.g. `slotmap_0_0_0` … `slotmap_3_3_3`)
  - Data touched: XML file, `data/slotmap-lut.json`, `systemroms/machines/all_sha1s.txt` + ROM files (optional)
  - Failure handling: Unknown device → warn + raw string. SHA1 not found → warn + skip mirror detection for that ROM. Overlapping `<mem>` ranges → warn + first device wins. Scraper never aborts on slot map issues.

## Data Model

- MSXData (runtime, in data.js)
  - Purpose: Full dataset consumed by the web page at load time
  - Key fields: `version` (schema version int), `generated` (ISO date), `columns[]`, `groups[]`, `models[]`, `defaultView` (optional)
  - Relationships: Each model has a `values[]` array aligned to `columns[]` by position
  - Retention: Regenerated on each scraper run; committed to repo

- ColumnDef
  - Purpose: Defines one grid column
  - Key fields: `id` (stable int), `key` (machine key), `label` (display), `groupId` (int), `type` ('string'|'number'|'boolean')
  - Relationships: Belongs to one GroupDef
  - Retention: Columns are fixed; IDs are permanent once assigned

- GroupDef
  - Purpose: Defines one collapsible column group
  - Key fields: `id` (stable int 0–7), `key`, `label`, `order`
  - Relationships: Contains one or more ColumnDefs
  - Retention: Groups are fixed; defined in scraper config

- ModelRecord
  - Purpose: One row in the grid — one MSX model
  - Key fields: `id` (stable int), `values[]` (string|number|null, indexed by column position)
  - Relationships: values[] is parallel to MSXData.columns[]
  - Retention: Regenerated by scraper; stable ID is permanent

- IDRegistry (scraper tool, not shipped to browser)
  - Purpose: Maps model natural keys to stable integer IDs; records retired model IDs. Column IDs are defined in `scraper/columns.py` and not tracked here.
  - Key fields: `version` (2), `models` (object: natural key → id), `retired_models` (int[]), `next_model_id`
  - Relationships: Source of truth for model ID assignment only
  - Retention: Committed to repo; never reset; append-only for retirements

- SlotMapLUT (build-time + runtime)
  - Purpose: Vocabulary for slot map cell classification. Used as ordered rule list at build time; shipped to browser as flat `{ abbr: tooltip }` map for tooltip rendering.
  - Key fields (per rule): `element` (XML element type or `"*"`), `id_pattern` (case-insensitive regex string), `abbr` (short string), `tooltip` (display string)
  - Relationships: Consumed by Slot Map Extractor at build time; embedded in MSXData as `slotmap_lut: { [abbr]: tooltip }` for browser use
  - Retention: Committed to repo; grows as new device strings are encountered; never loses entries

- SlotMapColumns (in data.js, part of ColumnDef)
  - Purpose: The 64 slot map columns — 4 groups × 16 columns. Each is a standard ColumnDef with a stable ID and a key of the form `slotmap_{ms}_{ss}_{p}` (main slot, sub-slot, page).
  - Key fields: same as ColumnDef (`id`, `key`, `label`, `groupId`, `type: 'string'`)
  - Relationships: 4 GroupDefs added ("Slotmap, slot 0–3"); 16 ColumnDefs per group
  - Retention: IDs permanent once assigned; groups and columns defined in `scraper/columns.py`

- ViewState (in-memory only, serialized to URL)
  - Purpose: Encodes the complete current view
  - Key fields: `sortColumnId`, `sortDirection`, `filters` (Map<colId, string>), `hiddenRows` (Set<modelId>), `hiddenColumns` (Set<colId>), `collapsedGroups` (Set<groupId>), `selectedCells` (Set<`${modelId}:${colId}`>)
  - Relationships: References IDs from MSXData
  - Retention: In-memory; encoded in URL hash; never persisted elsewhere

## URL Codec — Binary Format

```
Byte 0:     version (currently 0x01)
Byte 1:     flags (reserved, 0x00)
Bytes 2–3:  sort_column_id (uint16, 0x0000 = no sort; column ID 0 is reserved and must never be assigned)
Byte 4:     sort_direction (0x00=asc, 0x01=desc)
Bytes 5–8:  collapsed_groups bitmask (uint32, bit N = group ID N collapsed)
Bytes 9–10: hidden_columns bitset byte length (uint16)
Bytes …:    hidden_columns bitset (bit N = column ID N hidden)
Bytes …:    hidden_rows bitset byte length (uint16)
Bytes …:    hidden_rows bitset (bit N = model ID N hidden)
Bytes …:    filter_count (uint16)
  Per filter:
    column_id (uint16)
    string_byte_length (uint16)
    utf8 bytes
Bytes …:    selection_row_count (uint16)
  Per selected row:
    model_id             (uint16)
    col_bitset_byte_len  (uint16)
    col_bitset bytes     (variable; bit N = column ID N is selected)
```

Entire buffer → `btoa(String.fromCharCode(...bytes))` → URL-safe base64 (replace `+`→`-`, `/`→`_`, strip `=` padding) → `#` + result.

Estimated size for 50 selected cells across 10 rows, all filters empty, no hidden rows: ~90 bytes → ~120 base64 chars.

Future format changes increment the version byte; the decoder checks version and falls back to empty state for unknown versions.

## Integrity Strategy
- Invariants:
  - IDs in id-registry.json are never deleted or reused
  - `next_model_id` and `next_column_id` only ever increase
  - `docs/data.js` is only written after the full scraper run succeeds and the maintainer has resolved all conflicts
  - URL decoder never throws; unknown IDs are silently ignored
- Idempotency: Scraper run is idempotent on data (same sources → same output); registry is append-only
- Concurrency: Single-maintainer tool; no concurrent access design needed

## Audit and Compliance
- Audit needs: None for runtime. Scraper logs parse failures and conflict resolutions to stdout; maintainer reviews before committing.
- PII handling: No PII in this system. Model data is public hardware specification information.

## Integrations

- msx.org wiki
  - Direction: Outbound (scraper reads)
  - Interface: HTTP GET (HTML scraping)
  - Notes: Custom User-Agent `msxmodelsdb-scraper/1.0`; respect robots.txt Disallow paths; add 500ms delay between requests to avoid hammering

- openMSX GitHub repository
  - Direction: Outbound (scraper reads)
  - Interface: HTTP GET to raw.githubusercontent.com XML files
  - Notes: Fetch file listing via GitHub API (`/repos/openMSX/openMSX/contents/share/machines`); then fetch individual XML files. Can be replaced by a local mirror directory (`--openmsx-mirror DIR`) containing the same `.xml` files — no network access in that mode.

## Technology Stack

### Backend (Scraper)
- Language/Runtime: Python 3.11+
- HTML parsing: `beautifulsoup4` + `lxml` backend
- XML parsing: `lxml` with `recover=True` (lenient parser — openMSX XML files are often malformed/non-strict and must be parsed permissively)
- HTTP: `requests` (with retry via `urllib3`)
- Interactive prompts: built-in `input()` with coloured output via `colorama`
- JSON: stdlib `json`
- No web framework (CLI tool only)

### Frontend (Web Page)
- Approach: Static SPA (no SSR, no MPA)
- Language: TypeScript 5.x
- Build tool: Vite 5.x
- UI toolkit: None (vanilla TS + DOM APIs)
- Styling: Plain CSS with CSS custom properties (no preprocessor)
- Output: `docs/bundle.js` + `docs/index.html` (Vite build); `docs/data.js` (scraper)

### Data
- Primary database: None (files only)
- Runtime data: `docs/data.js` (JS file setting `window.MSX_DATA`)
- ID registry: `data/id-registry.json` (JSON file, dev-only)
- Schema documentation: `data/schema.md`
- Migrations: n/a (schema version field in MSXData enables future evolution)

### Infrastructure Posture
- Hosting: GitHub Pages (from `docs/` directory on main branch) + local `file://`
- Environments: Local only (no dev/staging/prod distinction — static files)
- Deployment style: Commit `docs/` to main branch → GitHub Pages auto-deploys

### Observability
- Logging: Browser `console.warn` for URL decode errors only; no production logging
- Metrics: None
- Tracing: None
- Scraper: stdout only — structured log lines with severity prefix (`[INFO]`, `[WARN]`, `[ERROR]`)

### Testing Posture
- Unit (web): Vitest; cover URL codec (encode/decode round-trips, version handling, unknown ID tolerance), grid state transitions
- Unit (scraper): pytest; cover ID registry (match/assign/retire), merge logic, conflict detection
- Integration: None (no server to integrate against)
- E2E: None in CI; manual smoke test by opening `docs/index.html` locally
- CI runs: lint + typecheck + unit tests on push to main

## Repository & Delivery Conventions

### Repository Structure

```
msx_models_db/
├── docs/                   # Committed build output — served by GitHub Pages
│   ├── index.html          # Built by Vite
│   ├── bundle.js           # Built by Vite
│   └── data.js             # Written by scraper (window.MSX_DATA = {...})
├── src/                    # TypeScript source
│   ├── main.ts             # Entry point
│   ├── grid/
│   │   ├── state.ts        # ViewState type + reducers
│   │   ├── render.ts       # DOM rendering
│   │   ├── selection.ts    # Cell selection (click, CTRL, SHIFT, drag)
│   │   ├── columns.ts      # Column/group show-hide, collapse
│   │   └── clipboard.ts    # CTRL+C handler
│   ├── url/
│   │   ├── codec.ts        # Binary encode/decode of ViewState
│   │   └── sync.ts         # history.replaceState integration
│   └── theme.ts            # Dark/light toggle, localStorage persistence
├── scraper/                # Python scraper package
│   ├── __main__.py         # Entry point (python -m scraper)
│   ├── sources/
│   │   ├── msx_org.py      # msx.org HTML scraper
│   │   └── openmsx_xml.py  # openMSX XML parser (general fields)
│   ├── slotmap.py          # Slot map extractor + LUT loader + mirror detection
│   ├── merge.py            # Merge + interactive conflict resolution
│   ├── registry.py         # ID registry load/save/match/assign
│   └── output.py           # Write data.js
├── data/
│   ├── id-registry.json    # Stable ID registry (committed, never deleted)
│   ├── slotmap-lut.json    # Slot map vocabulary (maintained by maintainer)
│   └── schema.md           # MSXData schema documentation
├── systemroms/
│   └── machines/
│       ├── all_sha1s.txt   # SHA1→relative-path index (for mirror ROM size lookup)
│       └── …               # ROM files (not committed; present in maintainer's local env)
├── tests/
│   ├── web/                # Vitest tests
│   │   ├── codec.test.ts
│   │   └── state.test.ts
│   └── scraper/            # pytest tests
│       ├── test_registry.py
│       ├── test_merge.py
│       └── test_slotmap.py  # LUT matching, page assignment, mirror detection
├── index.html              # Vite dev entry point
├── vite.config.ts
├── tsconfig.json
├── package.json
├── requirements.txt        # Python deps (beautifulsoup4, lxml, requests, colorama)
└── .claude/
```

### Command Surface
- `npm run dev` — start Vite dev server (hot reload, serves from src/)
- `npm run build` — bundle TypeScript → docs/index.html + docs/bundle.js
- `npm test` — run Vitest unit tests
- `npm run lint` — ESLint on src/
- `npm run typecheck` — tsc --noEmit
- `python -m scraper` — run scraper; writes docs/data.js and data/id-registry.json
- `pytest tests/scraper/` — run scraper unit tests

### CI Outline (GitHub Actions)
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Test (web): `npm test -- --run`
- Test (scraper): `pip install -r requirements.txt && pytest tests/scraper/`
- Build: `npm run build`
- (No auto-deploy; maintainer commits docs/ manually after scraper run)

### Environment Model

- Configuration sources: None at runtime. Scraper reads `data/scraper-config.json` (optional JSON object) for persistent local paths:
  - `msxorg_mirror` — path to local msx.org mirror directory (browser-saved HTML files)
  - `openmsx_mirror` — path to local openMSX mirror directory (XML files, e.g. `share/machines`)
  CLI flags `--msxorg-mirror`, `--local-msxorg-only`, `--openmsx-mirror`, `--local-openmsx-only` override config values.
- Optional scraper env vars:
  - `SCRAPER_DELAY_MS`: delay between HTTP requests (default: 500)
  - `GITHUB_TOKEN`: GitHub API token to avoid rate limits when fetching XML file listings

## Evolution Strategy
- Versioning approach: `MSXData.version` integer increments when the schema changes. The URL codec has its own version byte. Both are checked at load time; unknown versions degrade gracefully.
- Migration approach: Schema changes are additive where possible (new columns get new IDs; old columns never removed). If a breaking schema change is unavoidable, bump the MSXData version and update the web page to handle both versions during a transition window.

## Known Tradeoffs

- Vanilla TS + hand-rolled grid (no table library)
  - Why chosen: The cell-level selection model (non-contiguous multi-cell, drag), custom column group headers, and **multi-row sticky headers/left gutter** do not map well onto standard table library abstractions; hand-rolling avoids fighting the library and enables precise sticky behavior as required.
  - Cost: More implementation work; selection, drag, and sticky logic must be carefully tested, especially for edge cases (e.g., wide slot map columns, many hidden columns, simultaneous vertical/horizontal scroll).

- Build step required (Vite)
  - Why chosen: TypeScript, npm packages (codec utilities), and clean module organisation require a build step; output is still plain static files
  - Cost: Node.js required in the dev environment; one extra step before committing built output

- `docs/data.js` and `docs/bundle.js` committed to main branch
  - Why chosen: GitHub Pages serves from `docs/`; avoids a separate gh-pages branch or Actions deploy pipeline
  - Cost: Git history includes binary-ish build artifacts; diffs are noisy after scraper runs

- Python for scraper (separate runtime from web page)
  - Why chosen: beautifulsoup4 + lxml are best-in-class for HTML/XML scraping; maintainer preference
  - Cost: Two runtimes (Node.js for web, Python for scraper); contributors need both installed

- No row virtualisation
  - Why chosen: Assumed < 300 rows; simple DOM table is faster to implement and easier to style, and enables reliable sticky header/gutter behavior without virtualization complexity.
  - Cost: If row count grows significantly beyond 300, performance may degrade; add virtualization at that point, ensuring sticky header/gutter logic is preserved.

- Slot map LUT as a separate maintainer-edited JSON file (not code)
  - Why chosen: New device strings will appear as more machines are parsed; maintainer must be able to extend vocabulary without touching scraper code
  - Cost: An extra file to maintain; scraper must validate LUT on load (duplicate abbrs, malformed patterns)

- Two-pass XML walk for mirror resolution (`<Mirror>` element method)
  - Why chosen: `<Mirror>` references a slot by number (`<ps>`/`<ss>`), which may appear later in document order; a second pass guarantees all slot content is classified before cross-references are resolved
  - Cost: Slightly more complex extraction logic; first pass must store intermediate slot→abbr map before second pass

- `systemroms/` not committed to the repository
  - Why chosen: ROM files are copyrighted; only the SHA1 index (`all_sha1s.txt`) is committed; mirror detection gracefully degrades when ROM files are absent
  - Cost: Mirror detection method 2 (ROM file size) is unavailable in CI and on machines without the ROM collection; mirrors in those cases are silently missed rather than flagged

- Slot map column keys use positional naming (`slotmap_{ms}_{ss}_{p}`)
  - Why chosen: Systematic and derivable from slot coordinates; no ambiguity; easy to generate programmatically in `scraper/columns.py`
  - Cost: Keys are not human-readable at a glance; rely on `label` field for display

---

## Feature Design: Cell Value Truncation

### Overview

Columns may declare an optional `truncate_limit` (positive integer). When a string cell value exceeds this limit, the rendered text is clipped to `(truncate_limit − 1)` characters followed by `…`. The full value is preserved in a `data-full-value` DOM attribute and exposed via a native `title` tooltip. Sorting and clipboard copy are unaffected because both already read from `ModelRecord.values[]` directly — not from `td.textContent`.

### Schema Change — `ColumnDef`

Add one optional field to `ColumnDef` (TypeScript) and the `Column` dataclass (Python):

```ts
// src/types.ts
export interface ColumnDef {
  // ... existing fields ...
  truncateLimit?: number;   // positive int; absent or 0 = no truncation
}
```

```python
# scraper/columns.py
@dataclass
class Column:
    # ... existing fields ...
    truncate_limit: int = 0   # 0 = no truncation
```

The scraper serialises `truncate_limit` (renamed `truncateLimit` in camelCase) into `data.js` only when non-zero, keeping the output compact.

Initial values:
- `manufacturer` (id=1): `truncate_limit = 10`
- `model` (id=2): `truncate_limit = 10`

### Render Path — `buildDataRow` (grid.ts)

After computing `text = cellText(rawValue, col)`, apply truncation before writing to the DOM:

```
if col.truncateLimit > 0 and text.length > col.truncateLimit:
    td.dataset.fullValue = text
    displayText = text.slice(0, truncateLimit - 1) + '…'
else:
    displayText = text
```

For **plain cells**: `td.textContent = displayText`

For **link cells** (where `col.linkable` and a URL is present):
- `a.textContent = displayText`
- `a.title = fullValue + ' — ' + url`  (replaces the current `a.title = url`)

### Tooltip Path — `mouseenter` handler (grid.ts)

The current handler skips cells with `a.cell-link` and falls through to per-cell overflow or `data-tooltip` logic. The update:

1. **Link cells with truncation** — no longer skipped early; if `td.dataset.fullValue` is set, the combined `a.title` was already written at render time. The handler still exits early — the `<a>` manages its own `title`.
2. **Plain cells with truncation** — `td.dataset.fullValue` is set; handler sets `td.title = td.dataset.fullValue` (takes priority over the existing overflow check, because the full value is always the right tooltip regardless of whether the cell visually overflows).
3. **Cells without truncation** — existing behavior unchanged.

Priority order inside mouseenter for non-link cells:
```
if td.dataset.fullValue  → td.title = td.dataset.fullValue
else if scrollWidth > offsetWidth → td.title = td.textContent
else if td.dataset.tooltip → td.title = td.dataset.tooltip
else → removeAttribute('title')
```

### Clipboard Copy — no change needed

`copySelection()` reads `model.values[c]` directly, bypassing all DOM text. No modification required.

### Sort — no change needed

`sortModels()` reads `model.values[colIndex]` directly. No modification required.

### Data flows affected

| Path | Change |
|---|---|
| `scraper/columns.py` | Add `truncate_limit` field; set 10 on `manufacturer` and `model` |
| `scraper/build.py` (or equivalent serialiser) | Serialise `truncateLimit` into `ColumnDef` in `data.js` when non-zero |
| `src/types.ts` | Add `truncateLimit?: number` to `ColumnDef` |
| `src/grid.ts` — `buildDataRow` | Apply truncation; set `data-full-value`; update `a.title` for link cells |
| `src/grid.ts` — `mouseenter` handler | Prefer `data-full-value` over overflow check for plain cells |
| Clipboard copy | No change |
| Sort | No change |
| URL codec | No change |
| Filter | No change |

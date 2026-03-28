# Technical Design: MSX Models DB

## Metadata
- Date: 2026-03-27
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

## Domain Boundaries

- Web page (UI)
  - Responsibilities: Render grid, manage view state, encode/decode URL hash, handle user interactions
  - Owns Data: In-memory view state (sort, filters, selection, hidden rows/cols, collapsed groups); reads MSXData from window at load
  - External Interfaces: Reads `window.MSX_DATA` (set by data.js); writes URL hash via `history.replaceState`

- Scraper (data pipeline)
  - Responsibilities: Fetch, parse, merge, conflict-resolve, and write model data; maintain ID registry
  - Owns Data: `data/id-registry.json` (source of truth for stable IDs); writes `docs/data.js`
  - External Interfaces: HTTP GET to msx.org (HTML scraping); HTTP GET to raw.githubusercontent.com or GitHub API (XML files); stdin/stdout for conflict prompts

## Components

- Grid App (web page)
  - Type: Web App (static SPA)
  - Responsibilities: Grid display, column groups, sort/filter, row/column show-hide, cell selection, clipboard copy, URL state sync, theme toggle
  - Depends On: `window.MSX_DATA` (set by data.js before app script runs)
  - Data Stores: In-memory only (no localStorage except theme preference)

- URL Codec
  - Type: Library (module within Grid App)
  - Responsibilities: Serialize/deserialize full view state to/from a compact binary payload; base64-encode for URL hash
  - Depends On: Grid state types
  - Data Stores: URL hash fragment (`window.location.hash`)

- Scraper CLI
  - Type: Job (offline Python script)
  - Responsibilities: Scrape msx.org, parse openMSX XML, merge sources, prompt on conflicts, assign/reuse stable IDs, write data.js
  - Depends On: id-registry.json, msx.org HTTP, GitHub raw HTTP
  - Data Stores: `data/id-registry.json` (read+write), `docs/data.js` (write)

- ID Registry
  - Type: File artifact (JSON)
  - Responsibilities: Map model/column natural keys to permanent integer IDs; record retired IDs
  - Depends On: -
  - Data Stores: `data/id-registry.json`

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

- Scraper run
  - Trigger: Maintainer runs `python -m scraper`
  - Steps:
    1. Load `data/id-registry.json`
    2. Fetch list of MSX2/MSX2+/turboR model pages from msx.org category pages
    3. Scrape each model page; extract fields; log parse failures without aborting
    4. Fetch openMSX machine XML files from GitHub
    5. Parse each XML; extract fields
    6. Match scraped models to registry by natural key (manufacturer + model name); assign new IDs only for unmatched entries
    7. Merge msx.org and openMSX data per model; for conflicting fields, print summary and prompt maintainer to choose
    8. Write updated `data/id-registry.json`
    9. Write `docs/data.js` with full MSXData payload
    10. Print summary: N models written, M conflicts resolved, K parse failures
  - Data touched: id-registry.json (read+write), docs/data.js (write)
  - Failure handling: HTTP errors → retry once, then log and skip model. Parse failures → log field name and raw value, continue. If >20% of models fail to parse, abort before writing output.

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
  - Purpose: Maps natural keys to stable integer IDs; records retired IDs
  - Key fields: `version`, `models` (object: natural key → id), `retired_models` (int[]), `next_model_id`, `columns` (object: key → id), `next_column_id`
  - Relationships: Source of truth for all ID assignment
  - Retention: Committed to repo; never reset; append-only for retirements

- ViewState (in-memory only, serialized to URL)
  - Purpose: Encodes the complete current view
  - Key fields: `sortColumnId`, `sortDirection`, `filters` (Map<colId, string>), `hiddenRows` (Set<modelId>), `hiddenColumns` (Set<colId>), `collapsedGroups` (Set<groupId>), `selectedCells` (Set<`${modelId}:${colId}`>)
  - Relationships: References IDs from MSXData
  - Retention: In-memory; encoded in URL hash; never persisted elsewhere

## URL Codec — Binary Format

```
Byte 0:     version (currently 0x01)
Byte 1:     flags (reserved, 0x00)
Bytes 2–3:  sort_column_id (uint16, 0x0000 = no sort)
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
Bytes …:    selection_count (uint16)
  Per selected cell:
    model_id (uint16)
    column_id (uint16)
```

Entire buffer → `btoa(String.fromCharCode(...bytes))` → URL-safe base64 → `#` + result.

Estimated size for 50 selected cells, all filters empty, no hidden rows: ~130 bytes → ~174 base64 chars.

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
  - Notes: Fetch file listing via GitHub API (`/repos/openMSX/openMSX/contents/share/machines`); then fetch individual XML files

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
│   │   └── openmsx_xml.py  # openMSX XML parser
│   ├── merge.py            # Merge + interactive conflict resolution
│   ├── registry.py         # ID registry load/save/match/assign
│   └── output.py           # Write data.js
├── data/
│   ├── id-registry.json    # Stable ID registry (committed, never deleted)
│   └── schema.md           # MSXData schema documentation
├── tests/
│   ├── web/                # Vitest tests
│   │   ├── codec.test.ts
│   │   └── state.test.ts
│   └── scraper/            # pytest tests
│       ├── test_registry.py
│       └── test_merge.py
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
- Configuration sources: None at runtime. Scraper has no required env vars.
- Optional scraper env vars:
  - `SCRAPER_DELAY_MS`: delay between HTTP requests (default: 500)
  - `GITHUB_TOKEN`: GitHub API token to avoid rate limits when fetching XML file listings

## Evolution Strategy
- Versioning approach: `MSXData.version` integer increments when the schema changes. The URL codec has its own version byte. Both are checked at load time; unknown versions degrade gracefully.
- Migration approach: Schema changes are additive where possible (new columns get new IDs; old columns never removed). If a breaking schema change is unavoidable, bump the MSXData version and update the web page to handle both versions during a transition window.

## Known Tradeoffs

- Vanilla TS + hand-rolled grid (no table library)
  - Why chosen: The cell-level selection model (non-contiguous multi-cell, drag) and custom column group headers don't map well onto standard table library abstractions; hand-rolling avoids fighting the library
  - Cost: More implementation work; selection and drag logic must be carefully tested

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
  - Why chosen: Assumed < 300 rows; simple DOM table is faster to implement and easier to style
  - Cost: If row count grows significantly beyond 300, performance may degrade; add virtualisation at that point

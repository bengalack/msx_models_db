# Risk & Assumption Review: MSX Models DB

## Metadata
- Date: 2026-03-30
- Reviewed Artifacts:
  - .claude/artifacts/planning/problem-description.md
  - .claude/artifacts/planning/problem-description-slotmap.md
  - .claude/artifacts/planning/product-requirements.md
- Open Questions:
  - .claude/artifacts/decisions/open-questions.md

## Confirmed Truths
- The page must be entirely client-side; no server assistance is available at runtime.
  - Evidence: Three deployment targets (file://, static host, Blogger/Blogspot) all lack server-side parameter passing.
- Data must be loaded via a `<script>` tag (e.g. `data.js` sets `window.MSX_DATA = {...}`), not `fetch()`.
  - Evidence: `fetch()` is blocked on `file://` in Chrome; Blogger cannot serve local files; script tags work universally.
- URL state must be compact binary, base64-encoded — not human-readable.
  - Evidence: Cell selections of any realistic size must fit within ~2000 chars; user confirmed binary encoding.
- All row and column IDs must be stable and immutable forever.
  - Evidence: Old URLs must remain valid across all future database updates; IDs identify cells in encoded URL state.
- Gutter indicators (hidden rows / columns) appear in the header strip area only; no distinction between filter-hidden and manually-hidden in the grid body.
  - Evidence: User confirmed — both cases show the same indicator in row-1 / col-1 header region.

## Key Risks

- Scraper incorrectly creates new IDs for existing models
  - Category: Data
  - Likelihood: Low (registry + matching is explicitly designed for)
  - Impact: High — old URLs break permanently if IDs diverge
  - Mitigation: Scraper matches incoming data to existing registry entries (by manufacturer + model name) before assigning any new ID. New IDs are only created for genuinely new entries. Registry is committed alongside the data file and reviewed by the maintainer before deployment.
  - Owner: bengalack (maintainer)

- msx.org wiki page structure changes break the scraper
  - Category: Data
  - Likelihood: Medium
  - Impact: Medium — scraper stops updating; data goes stale
  - Mitigation: Scraper logs parse failures clearly and exits non-zero; maintainer investigates before committing output.
  - Owner: bengalack

- openMSX XML files are malformed / non-strict XML
  - Category: Data
  - Likelihood: High (confirmed — files are known to be non-strict)
  - Impact: Low — handled by design
  - Mitigation: Use lxml with `recover=True` (lenient parsing mode); log any elements that could not be recovered; validate extracted field values after parsing rather than relying on well-formed structure.
  - Owner: Implementation

- openMSX XML schema evolves or field names change
  - Category: Data
  - Likelihood: Low
  - Impact: Low — only affects fields sourced from openMSX
  - Mitigation: Validate parsed fields at scrape time; log unexpected or missing fields clearly.
  - Owner: bengalack

- Data conflicts between msx.org and openMSX XML for the same model
  - Category: Data
  - Likelihood: Medium
  - Impact: Low — one field may be wrong
  - Mitigation: Scraper summarizes all conflicts and prompts the maintainer interactively to choose which value to keep before writing output. No automatic priority rule; maintainer has final say.
  - Owner: bengalack

- Blogger/Blogspot embed: external data file not CORS-accessible
  - Category: Technical
  - Likelihood: Low (if hosted on GitHub Pages)
  - Impact: High — grid fails to load data when embedded in Blogger
  - Mitigation: Host `data.js` on GitHub Pages (which serves correct CORS headers); document this as required hosting for the data file when using Blogger embed.
  - Owner: bengalack

- URL state payload exceeds browser/platform limits
  - Category: Technical
  - Likelihood: Low (with binary + base64 encoding)
  - Impact: Medium — shared URL is truncated or rejected
  - Mitigation: Binary-encode all state; use base64 in URL hash fragment (not query string — hash is not sent to server and has no hard length limit in modern browsers). Test with maximum realistic selection.
  - Owner: Implementation

- Unknown IDs in a decoded URL cause errors
  - Category: Technical
  - Likelihood: Medium (models/columns added or removed over time)
  - Impact: Low if handled gracefully
  - Mitigation: URL decoder must silently ignore any ID not found in the current data; never throw on unknown IDs.
  - Owner: Implementation

- Unknown LUT device strings silently widen slot map cells in the browser
  - Category: Data
  - Likelihood: Medium — new device strings likely as more models are parsed
  - Impact: Low — visible but contained; maintainer will spot it in the grid
  - Mitigation: Scraper warns to stdout on every unmatched device string (with model name and XML element); maintainer extends LUT and rebuilds. Raw string is written as-is so data is not lost.
  - Owner: bengalack

- SHA1-based ROM file lookup fails for mirror detection
  - Category: Data
  - Likelihood: Medium — `systemroms/` is not guaranteed to have every ROM
  - Impact: Low — mirror pages are shown as originals rather than `*`; data is not wrong, just less precise
  - Mitigation: If SHA1 is not found in `all_sha1s.txt` or the resolved file is absent on disk, scraper skips mirror detection for that ROM and emits a warning. Never aborts.
  - Owner: Implementation

- Multiple devices mapped to the same page in one sub-slot
  - Category: Data
  - Likelihood: Low — unusual in practice but XML allows it
  - Impact: Low — cell would be ambiguous
  - Mitigation: Scraper warns and uses the first device encountered (document order in XML). If this produces wrong output, maintainer can extend conflict system to handle it.
  - Owner: Implementation

- 64 extra columns degrade grid performance
  - Category: Technical
  - Likelihood: Low — row count is small (<200); column count increases but cells are simple text
  - Impact: Low — observable slowdown unlikely on modern desktop browsers
  - Mitigation: Slot map groups default to collapsible; user can hide all 64 at once. Monitor actual load time; add virtualization only if measured.
  - Owner: Implementation

- `<Mirror>` element references a slot not yet parsed (ordering dependency)
  - Category: Technical
  - Likelihood: Low — `<ps>`/`<ss>` reference a primary/secondary slot number, not a parse-order position
  - Impact: Low — mirror cell would be misclassified if the referenced slot content isn't resolved yet
  - Mitigation: Parse all slot content first (two-pass); resolve `<Mirror>` cross-references in a second pass after all devices are classified.
  - Owner: Implementation

## Dangerous Assumptions

- msx.org allows programmatic scraping
  - Why dangerous: If robots.txt disallows scraping or ToS prohibits it, the scraper cannot be used.
  - How to validate: Check https://www.msx.org/robots.txt and review ToS before implementing the scraper.
  - If false, what breaks: The scraper cannot source data from msx.org; data must be manually curated.

- openMSX XML files cover the majority of MSX2/MSX2+/turbo R models
  - Why dangerous: If coverage is sparse, the scraper produces an incomplete database with significant manual gap-filling required.
  - How to validate: Count MSX2/MSX2+/turboR entries in the openMSX share/machines folder before building the scraper.
  - If false, what breaks: The scraper effort is larger than expected; msx.org scraping becomes the primary source.

- All in-scope models fit in the DOM without row virtualization (< ~300 rows)
  - Why dangerous: If the total row count is significantly higher (e.g. after adding FPGA models), rendering all rows at once may cause lag.
  - How to validate: Count total unique MSX2/MSX2+/turboR entries across both sources.
  - If false, what breaks: A row virtualization layer is needed, adding implementation complexity.

- The maintainer's runtime environment supports the scraper language (Node.js or Python)
  - Why dangerous: If neither is available, the scraper cannot be run.
  - How to validate: Confirm preferred runtime with maintainer before choosing scraper language.
  - If false, what breaks: Scraper must be rewritten in a different runtime.

- `systemroms/machines/` directory and `all_sha1s.txt` are present when the scraper runs
  - Why dangerous: Mirror detection method 2 (ROM size) depends entirely on this directory. If absent, all size-based mirrors are missed silently.
  - How to validate: Scraper checks for the directory and index file at startup; warns clearly if missing rather than silently skipping.
  - If false, what breaks: Mirror detection degrades to explicit `<Mirror>` element and `<rom_visibility>` only — mirrors in most models go undetected.

- The starter LUT covers all device types in in-scope XML files
  - Why dangerous: Any unmatched device writes its raw XML string as cell content — maintainer may not notice until the grid renders with wide cells.
  - How to validate: Do a dry-run parse of all 109 in-scope XML files and log every device string against the LUT before shipping the scraper.
  - If false, what breaks: Some cells show raw strings (ugly but not broken); LUT needs extension before the grid looks correct.

## Scope Creep Watchlist

- msx.org slot map parsing is deferred but will likely be requested once XML-only data reveals gaps (models with no openMSX XML entry).
- FPGA model list is undefined — could expand to dozens of community models with sparse or no structured data source.
- The "Emulation" column group could invite requests to launch openMSX directly from the page (out of scope — data reference only).
- Blogger/Blogspot embed support could grow into a full embeddable widget with custom sizing, theming, or iframe API.
- "Old URLs always work" implies a compatibility contract — any future schema change must be designed around this constraint, not just the current iteration.
- Multi-sort (currently out of scope) is a natural follow-up request once single-column sort is live.

## Over-Engineering Traps

- Building a custom binary serialization format for URL state from scratch
  - Simplest safe alternative: Represent state as a structured JSON object, compress with a lightweight algorithm (e.g. LZ-string), then base64-encode. Well-tested, no custom parser to maintain.

- Implementing drag-to-select with pixel-level precision
  - Simplest safe alternative: Snap drag selection to cell boundaries on mouseenter events; no pixel math needed.

- Distinguishing filtered vs manually hidden rows in the data model
  - Simplest safe alternative: Both states write to the same "hidden rows" set in URL state; the gutter indicator is shown for any row absent from the rendered grid.

- Scraper trying to reconcile every possible data conflict automatically
  - Simplest safe alternative: Flag conflicts in the JSON with a `_conflict` field and let the maintainer resolve manually on first run.

- Building a custom LUT matching engine with complex parameterisation for CS{N}
  - Simplest safe alternative: One special-case rule in the scraper: if `<primary external="true">`, read slot number from the attribute and emit `CS{N}`. All other LUT entries are straight element-type + regex-on-id. No template engine needed.

- Implementing all three mirror detection methods simultaneously
  - Simplest safe alternative: Ship method 3 (`<rom_visibility>`) first — it is fully self-contained in the XML with no file I/O. Add method 2 (SHA1/file size) second. Add method 1 (`<Mirror>` element, two-pass) last — it is the rarest pattern.

## Recommended Simplifications

- Build the UI first against a hand-curated JSON file; add the scraper second.
  - Tradeoff: Data is incomplete until the scraper is built.
  - Why acceptable: Decouples UI development from scraper complexity; the JSON schema can be validated against real UI before the scraper is locked in.

- Use the URL hash fragment (not query string) for all state encoding.
  - Tradeoff: Hash is not sent to the server (irrelevant here since there is no server) and is not indexed by search engines.
  - Why acceptable: No server exists; search indexing of state URLs is undesirable anyway. Hash has no practical length limit in modern browsers.

- Assign stable IDs as short integers (e.g. sequential, starting at 1) rather than slugs or hashes.
  - Tradeoff: IDs are not human-readable in the URL.
  - Why acceptable: User explicitly confirmed IDs do not need to be human-readable; integers are maximally compact for binary encoding.

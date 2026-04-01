# Risk & Assumption Review: MSX Models DB

## Metadata
- Date: 2026-03-31
- Reviewed Artifacts:
  - .claude/artifacts/planning/problem-description.md
  - .claude/artifacts/planning/problem-description-slotmap.md
  - .claude/artifacts/planning/product-requirements.md
- Open Questions:
  - .claude/artifacts/decisions/open-questions.md

## Confirmed Truths
- The page must be entirely client-side; no server assistance is available at runtime.
- Data must be loaded via a `<script>` tag (e.g. data.js sets `window.MSX_DATA = {...}`), not `fetch()`.
- URL state must be compact binary, base64-encoded — not human-readable.
- All row and column IDs must be stable and immutable forever.
- Gutter indicators (hidden rows / columns) appear in the header strip area only; no distinction between filter-hidden and manually-hidden in the grid body.

## Key Risks
- Scraper incorrectly creates new IDs for existing models
- msx.org wiki page structure changes break the scraper
- openMSX XML files are malformed / non-strict XML
- openMSX XML schema evolves or field names change
- Data conflicts between msx.org and openMSX XML for the same model
- Blogger/Blogspot embed: external data file not CORS-accessible
- URL state payload exceeds browser/platform limits
- Unknown IDs in a decoded URL cause errors
- Unknown LUT device strings silently widen slot map cells in the browser
- SHA1-based ROM file lookup fails for mirror detection
- Multiple devices mapped to the same page in one sub-slot
- 64 extra columns degrade grid performance
- `<Mirror>` element references a slot not yet parsed (ordering dependency)

## Dangerous Assumptions
- msx.org allows programmatic scraping
- openMSX XML files cover the majority of MSX2/MSX2+/turbo R models
- All in-scope models fit in the DOM without row virtualization (< ~300 rows)
- The maintainer's runtime environment supports the scraper language (Node.js or Python)
- `systemroms/machines/` directory and `all_sha1s.txt` are present when the scraper runs
- The starter LUT covers all device types in in-scope XML files

## Scope Creep Watchlist
- msx.org slot map parsing is deferred but will likely be requested once XML-only data reveals gaps (models with no openMSX XML entry).
- FPGA model list is undefined — could expand to dozens of community models with sparse or no structured data source.
- The "Emulation" column group could invite requests to launch openMSX directly from the page (out of scope — data reference only).
- Blogger/Blogspot embed support could grow into a full embeddable widget with custom sizing, theming, or iframe API.
- "Old URLs always work" implies a compatibility contract — any future schema change must be designed around this constraint, not just the current iteration.
- Multi-sort (currently out of scope) is a natural follow-up request once single-column sort is live.

## Over-Engineering Traps
- Building a custom binary serialization format for URL state from scratch
- Implementing drag-to-select with pixel-level precision
- Distinguishing filtered vs manually hidden rows in the data model
- Scraper trying to reconcile every possible data conflict automatically
- Building a custom LUT matching engine with complex parameterisation for CS{N}
- Implementing all three mirror detection methods simultaneously

## Recommended Simplifications
- Build the UI first against a hand-curated JSON file; add the scraper second.

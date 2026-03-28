# Problem Description: MSX Models DB

## Metadata
- Date: 2026-03-27
- Owner: bengalack
- Project Meta: .claude/artifacts/project/project-meta.md

## Summary
- MSX model specifications are scattered across the internet with no unified reference.
- Goal: a single static web page presenting all relevant MSX models in a sortable, filterable grid.
- First iteration covers MSX2, MSX2+, and MSX turbo R models only (including unofficial FPGA-based models).
- Grid supports rich cell selection (click, CTRL+click, SHIFT+click, drag) with visual highlight and native copy.
- Column groups (Identity, Memory, Video, Audio, Media, CPU/Chipsets, Other, Emulation) can collapse/expand.
- URL encodes current grid state (selections, sort, filters) to enable sharing and bookmarking.
- Data is stored in a local JSON file consumed directly by the HTML page.
- A separate scraper process populates/refreshes the JSON from msx.org wiki and openMSX GitHub XML files.
- Page must work both as a local `index.html` and as a hosted static site (e.g. GitHub Pages).

## Problem
Today, finding detailed and comparable specs for MSX computer models requires visiting multiple websites (msx.org wiki, openMSX documentation, community pages). There is no consolidated, structured view that lets a user quickly compare models across key dimensions like RAM, video chip, CPU speed, or media. Grouping models by standard (MSX2 vs. turbo R) or filtering by manufacturer requires manual effort. This is slow and error-prone.

## Desired Outcomes
- A user can open one page and immediately see all MSX2/MSX2+/turbo R models in a grid.
- Columns can be sorted and filtered without reloading the page.
- Column groups can be collapsed to focus on relevant dimensions.
- Cells can be selected and copied to clipboard using standard OS shortcuts.
- The URL updates live as the user interacts (selects cells, hides columns, sorts, filters, collapses groups) and always fully recreates the exact view when opened.
- The maintainer can re-run a scraper at any time to refresh the underlying data file.

## Stakeholders
- MSX enthusiasts / collectors
  - Type: Customer
  - Goals: Quickly find and compare specs across MSX models
  - Responsibilities: End users of the web page
- bengalack (maintainer)
  - Type: Internal
  - Goals: Keep data accurate; run scraper as needed
  - Responsibilities: Maintain JSON data file; run scraping process; deploy the page

## Current Workflows
- Manual research workflow
  - Trigger: User wants to look up or compare MSX model specs
  - Steps:
    1. Search for model on msx.org, Wikipedia, or other sites
    2. Open multiple tabs to compare models
    3. Manually note or copy specs into a spreadsheet or document
  - Success End State: User has the spec info they need
  - Failure States:
    - Info is missing, inconsistent, or contradictory across sources
    - User gives up due to effort required

- Data maintenance workflow
  - Trigger: Maintainer wants to update the database
  - Steps:
    1. Run scraper process against msx.org wiki
    2. Run scraper process against openMSX GitHub XML files
    3. Merged output written to local JSON file
    4. JSON file committed / deployed alongside the web page
  - Success End State: JSON file reflects current known data; web page shows updated info
  - Failure States:
    - Source page structure changes and scraper breaks
    - Conflicting data between msx.org and openMSX XML

## In Scope
- Static web page with a grid/spreadsheet view of MSX models
- MSX2, MSX2+, MSX turbo R models (official and unofficial FPGA-based)
- Sortable, filterable, and individually show/hide-able columns
- Collapsible/expandable column groups (hides all columns in the group)
- Individually show/hide-able rows, with a visual indicator in the left gutter when one or more rows are hidden (making hidden rows discoverable)
- Cell selection: single click, CTRL+click, SHIFT+click, click+drag
- Visual highlight of selected cells
- Standard clipboard copy from selection (OS-native shortcut)
- URL is kept in sync with the current view at all times (live — updates on every interaction: cell selection, column visibility, sort order, active filters, collapsed groups), so the URL always fully recreates the current view when opened
- Local JSON data file as the single data source for the page
- Scraper process to populate JSON from msx.org wiki and openMSX GitHub XML files
- Works as local `index.html` and as a hosted static site

## Out of Scope
- MSX1 models (deferred to a future iteration)
- User accounts, authentication, or server-side logic
- Community contributions or crowd-sourced edits via the UI
- Real-time data fetching from external sources at page load
- Mobile-first or native app

## Constraints
- Static only — no backend server; all logic runs in the browser or in the offline scraper
  - Source: Operational
  - Notes: Must work as a plain `index.html` opened from disk
- Data sourced only from msx.org and openMSX GitHub XML
  - Source: Operational
  - Notes: No licensed data; scraper must respect source terms
- Maintainer-driven data updates (no automation pipeline)
  - Source: Org
  - Notes: Scraper is run manually on demand

## Risks
- msx.org wiki page structure changes break the scraper
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: Design scraper to be easily updated; log parse failures clearly
- openMSX XML schema evolves over time
  - Likelihood: Low
  - Impact: Low
  - Mitigation: Pin to a known schema version; test on update
- Data conflicts between msx.org and openMSX XML for the same model
  - Likelihood: Medium
  - Impact: Low
  - Mitigation: Define a priority/merge rule (e.g. openMSX XML wins for hardware fields); flag conflicts in JSON
- URL-state encoding becomes unwieldy for large selections
  - Likelihood: Low
  - Impact: Low
  - Mitigation: Use compact encoding (e.g. base64 or short ids); test with max realistic selection

## Unknowns
- Exact list of FPGA-based unofficial MSX models to include
  - Why it matters: Scope of data collection and scraper targets
  - Suggested question: Which FPGA models should be included — MiSTer MSX core, Omega MSX, 1chipMSX, others?
- Whether openMSX XML covers all MSX2/2+/turboR models or has gaps
  - Why it matters: Determines how much supplemental scraping from msx.org is needed
  - Suggested question: Run a count of MSX2+ and turboR entries in the openMSX XML to assess coverage
- Preferred column definitions within each group (to be refined by maintainer)
  - Why it matters: Determines the schema of the JSON file
  - Suggested question: Review proposed columns below and confirm or adjust

## Simplification Opportunities
- Start with a hardcoded JSON file (manually curated) before building the scraper
  - Why it helps: Lets the UI be built and validated independently from the scraper
- Use an existing headless table library (e.g. TanStack Table) rather than building grid logic from scratch
  - Why it helps: Sorting, filtering, and column management are non-trivial; proven libraries reduce risk

## Proposed Column Groups (to be refined)

| Group | Proposed Columns |
|---|---|
| Identity | Manufacturer, Model Name, Year, Region/Market, MSX Standard, Form Factor |
| Memory | Main RAM, VRAM, ROM (BIOS size) |
| Video | Video Chip (VDP), Max Resolution, Max Colors, Max Sprites |
| Audio | Sound Chip(s), Audio Channels |
| Media | Floppy Drive(s), Cartridge Slots, Tape Interface, Other Storage |
| CPU/Chipsets | CPU, Clock Speed, Sub-CPU |
| Other | Keyboard Layout, Built-in Software, Connectivity/Ports |
| Emulation | openMSX Machine ID, FPGA/MiSTer Support |

## References
- .claude/artifacts/project/project-meta.md
- .claude/artifacts/decisions/open-questions.md
- https://www.msx.org/wiki/Main_Page
- https://github.com/openMSX/openMSX/tree/master/share

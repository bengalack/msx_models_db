# Problem Description: Scraper Exclude List

## Metadata
- Date: 2026-03-29
- Owner: bengalack
- Project Meta: .claude/artifacts/project/project-meta.md

## Summary
- The scrapers currently fetch every model they discover — there is no way to skip unwanted models.
- A maintainer-editable `data/exclude.json` lists entries to skip **before any HTTP request** is made.
- Each entry matches by **manufacturer + model** (both scrapers) or by **XML filename** (openMSX only).
- Empty string `""` in a field means the field itself must be empty to match.
- `"*"` is a wildcard meaning "any value in this field".
- A missing `exclude.json` is treated as an empty list (no exclusions).
- Every skipped model is logged so the maintainer can audit exclusions.

## Problem
The scrapers fetch every model they discover from the openMSX GitHub repository and the msx.org category pages. There is no mechanism to exclude known-unwanted models (e.g. prototype hardware, non-standard variants, duplicates). After each scrape run the maintainer must manually remove them from the merged output. This is tedious, error-prone, and easy to forget.

## Desired Outcomes
- The maintainer edits `data/exclude.json` once; subsequent scraper runs never fetch that model again.
- No unwanted models reach `data/merged.json` or `docs/data.js`.
- Every skipped model is logged (INFO level) so the maintainer can see what was excluded on each run.
- A missing or empty `exclude.json` causes no errors and no exclusions.
- Malformed `exclude.json` raises a clear, early error before any network traffic.

## Stakeholders
- bengalack (maintainer)
  - Type: Internal
  - Goals: Keep the dataset clean without manual post-processing after each scrape.
  - Responsibilities: Maintains `data/exclude.json`; runs the scraper.

## Current Workflows
- Scraper run (current — no exclusion)
  - Trigger: Maintainer runs `python -m scraper build --fetch`
  - Steps:
    1. openMSX scraper fetches XML file listing from GitHub API
    2. openMSX scraper fetches **every** XML file and parses it
    3. msx.org scraper enumerates model pages from category listings
    4. msx.org scraper fetches **every** model page
    5. Merge step combines both sources
    6. Build pipeline writes `docs/data.js`
    7. Maintainer manually removes unwanted models from output
  - Success End State: `docs/data.js` contains only wanted models (after manual cleanup)
  - Failure States:
    - Maintainer forgets to remove a model → unwanted model appears on the web page
    - Manual cleanup must be repeated on every scrape run

- Scraper run (desired — with exclusion)
  - Trigger: Maintainer runs `python -m scraper build --fetch`
  - Steps:
    1. Scraper loads and validates `data/exclude.json` at startup
    2. openMSX scraper fetches XML file listing; skips files matching exclude rules
    3. msx.org scraper enumerates model pages; skips models matching exclude rules
    4. Merge and build proceed as normal
  - Success End State: `docs/data.js` never contains excluded models; no manual cleanup needed
  - Failure States:
    - `exclude.json` is malformed → scraper exits with a clear error before making any requests

## In Scope
- `data/exclude.json` — maintainer-edited file, committed to the repo
- Exclude check in `scraper/openmsx.py` — applied after file listing, before fetching each XML
- Exclude check in `scraper/msxorg.py` — applied after category enumeration, before fetching each model page
- Match modes per entry (one entry uses one mode):
  - `manufacturer` + `model`: exact string match on both fields; `""` matches an empty field; `"*"` matches any value
  - `filename`: openMSX only; exact match on XML filename (e.g. `"Sony_HB-75P.xml"`)
- INFO-level log line for each skipped model
- Fail-fast validation of `exclude.json` at scraper startup (before any network calls)
- Missing `exclude.json` → treated as empty list, no error
- Unit tests for the matching logic

## Out of Scope
- Excluding models after they have been fetched (merge-time filtering)
- Regex or glob patterns beyond `"*"` wildcard
- Wildcards on fields other than manufacturer and model (e.g. wildcard on year or region)
- UI or web-facing exclusion management
- Automatic population of the exclude list

## Constraints
- `data/exclude.json` must be valid JSON, pretty-printed, human-readable, and diff-friendly.
  - Source: Operational — maintainer edits by hand and reviews diffs in git.
- Exclude check must occur **before** any HTTP request for the excluded model.
  - Source: Operational — purpose is to avoid unnecessary network traffic.

## Risks
- Overly broad wildcard entry accidentally excludes wanted models.
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: Log every skip at INFO level so maintainer notices unexpected exclusions on each run.
- `exclude.json` malformed after a manual edit causes scraper to crash mid-run.
  - Likelihood: Low
  - Impact: Medium
  - Mitigation: Validate at startup before making any network calls; print the offending entry and line.

## Unknowns
- None blocking.

## Simplification Opportunities
- Load and validate the exclude list once at scraper startup (not per-model lookup).
  - Why it helps: Catches typos in `exclude.json` before any network traffic; O(1) startup cost.

## References
- .claude/artifacts/project/project-meta.md
- .claude/artifacts/decisions/open-questions.md
- scraper/openmsx.py
- scraper/msxorg.py
- data/exclude.json (to be created)

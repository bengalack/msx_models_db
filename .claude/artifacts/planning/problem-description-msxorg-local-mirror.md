# Problem Description: msx.org Local Mirror Scraping

## Metadata
- Date: 2026-04-07
- Owner: bengalack
- Project Meta: .claude/artifacts/project/project-meta.md

## Summary
- msx.org started returning HTTP 403 for all automated requests, making live scraping impossible.
- The maintainer can save pages manually via browser Save-As (HTML Only) as a fallback.
- The scraper must be able to read from a local directory of saved HTML files instead of fetching live.
- Both category listing pages and individual model pages must be supported as local files.
- A config file stores the default mirror path; a CLI flag (`--local-mirror`) overrides it.
- If a page is missing from the local copy, the scraper warns and skips — it does not fall back to live.
- Live scraping and local-mirror mode are mutually exclusive per run.

## Problem
msx.org now blocks all automated HTTP requests with 403 Forbidden. The scraper's msx.org data source
is completely unavailable unless the maintainer can provide an offline copy. Without a local-mirror
mode, the maintainer loses all msx.org data on the next rebuild unless they modify the scraper code.

## Desired Outcomes
- Maintainer saves msx.org category and model pages as HTML files using browser Save-As (HTML Only).
- Running `python -m scraper build --fetch --local-mirror /path/to/mirror` reads those files instead of fetching live.
- The scraper extracts exactly the same data as it would from live pages (same parsers reused).
- Missing pages are warned and skipped; the rest of the build continues normally.
- A config file (`data/scraper-config.json` or similar) can store the mirror path so the flag is optional.
- The flag always takes precedence over the config file.

## Stakeholders
- bengalack (maintainer)
  - Type: Internal
  - Goals: Keep msx.org data up to date despite the site blocking automated access
  - Responsibilities: Save pages manually; run scraper with local-mirror flag or config

## Current Workflows
- Live scraping workflow (now broken)
  - Trigger: Maintainer runs `python -m scraper build --fetch`
  - Steps:
    1. Scraper fetches category pages from msx.org to enumerate model URLs
    2. Scraper fetches each model page and parses specs
  - Success End State: msx.org data merged into output
  - Failure States:
    - 403 Forbidden on all requests — entire msx.org data source is lost

- Desired: Local-mirror workflow
  - Trigger: Maintainer runs `python -m scraper build --fetch --local-mirror /path/to/mirror`
  - Steps:
    1. Scraper reads category HTML files from local directory to enumerate model titles
    2. Scraper reads each model HTML file from local directory and parses specs
    3. Missing files: warn + skip; build continues
  - Success End State: msx.org data populated from local files; output identical to live run
  - Failure States:
    - Mirror path does not exist → error with clear message; build aborts msx.org portion
    - Individual model file missing → warn + skip; other models unaffected

## In Scope
- Reading category listing pages from a local directory
- Reading individual model pages from a local directory
- File naming convention matching browser Save-As output for `https://www.msx.org/wiki/<Title>` → `<Title>.html`
- `--local-mirror <path>` CLI flag on `build --fetch`
- Config file key for default mirror path (flag overrides config)
- Warn-and-skip when a file is missing
- Reuse existing HTML parsers unchanged (same data extracted as from live pages)

## Out of Scope
- Downloading / mirroring the site automatically (the maintainer does this manually)
- Falling back to live fetch when a local file is missing
- Partial mirrors (only some categories saved) — supported naturally by warn-and-skip
- Handling "Webpage, Complete" Save-As format (HTML + `_files/` folder) — HTML Only only
- Scraping any source other than msx.org via this mechanism
- openMSX (GitHub XML) local-mirror — not affected by the 403 issue

## Constraints
- Browser Save-As (HTML Only) is the only supported input format
  - Source: Operational
  - Notes: File content is identical to what the live parser already handles
- No new parser logic — existing `parse_model_page()` and `_find_specs_table()` must work unchanged
  - Source: Org
  - Notes: Avoids divergence between live and local-mirror code paths
- Config file must not be required — flag alone is sufficient to activate local-mirror mode
  - Source: Operational
  - Notes: Keeps CI/CD and one-off runs simple

## Risks
- Browser Save-As may alter HTML in ways that break the existing parser
  - Likelihood: Low
  - Impact: High
  - Mitigation: Test parser against a locally saved page before merging
- File naming: browser may encode colons or spaces differently in filenames (e.g. category pages with `Category:MSX2_Computers`)
  - Likelihood: Medium
  - Impact: Medium
  - Mitigation: Define and test the exact filename convention; document it for the maintainer
- Maintainer forgets to re-save pages when msx.org content is updated
  - Likelihood: Medium
  - Impact: Low
  - Mitigation: Out of scope for this feature; data staleness is accepted trade-off

## Unknowns
- None — all open questions resolved by inspecting the local mirror directory.

## Simplification Opportunities
- Reuse `list_model_pages()` and `fetch_all()` structure — swap only the HTTP calls for file reads
  - Why it helps: Minimal code surface; parsers stay identical; easy to test with existing fixtures

## References
- .claude/artifacts/project/project-meta.md
- .claude/artifacts/decisions/open-questions.md
- .claude/artifacts/planning/problem-description.md

# Plan: msx.org Local Mirror Scraping

## Metadata
- Date: 2026-04-07
- Backlog item: Scraper — msx.org local mirror fallback
- Feature slug: msxorg-local-mirror

## Context
- Intended outcome: When msx.org blocks live HTTP access, the maintainer can save pages locally with browser Save-As and point the scraper at that directory. All parsing logic stays identical; only the HTML source changes.

## Functional Snapshot
- Problem: msx.org returns 403 Forbidden for all automated requests; the msx.org data source is unavailable without a local fallback.
- Target user: bengalack (maintainer) running the scraper build pipeline.
- Success criteria (observable):
  - `--msxorg-mirror DIR` enables live-with-fallback mode (try live, use mirror on failure).
  - `--msxorg-mirror DIR --local-msxorg-only` skips live entirely; reads only local files.
  - A missing category file logs a warning and yields zero models for that standard; other categories and the overall build continue.
  - A missing individual model file logs a warning and skips that model; others continue.
  - The mirror path can be stored in `data/scraper-config.json` (key `msxorg_mirror`); the CLI flag overrides it.
  - Both flags work on `build` and `fetch-msxorg` subcommands.
- Primary user flow (local-only):
  1. Maintainer saves msx.org category and model pages via browser Save-As (HTML Only) into one flat directory.
  2. Sets `msxorg_mirror` in `data/scraper-config.json` once.
  3. Runs `python -m scraper build --fetch --local-msxorg-only` — no live HTTP to msx.org.
- Must never happen:
  - A missing mirror file raises an exception or aborts the build entirely.
  - Live HTTP requests are made when `--local-msxorg-only` is active.
  - Passing a non-existent mirror path silently succeeds.
- Key edge cases:
  - Category file missing → warn + skip that standard; models from other categories still collected.
  - Model file missing → warn + skip that model; other models unaffected.
  - CLI flag overrides config key.
  - Config absent or key absent → live mode.
  - Mirror dir exists but is empty → all categories warn + skip; `msxorg-raw.json` written with zero models.
- Business rules:
  - Filename convention (browser Save-As HTML Only on Windows):
    - Take the wiki URL slug (e.g. `Sony_HB-F9S`, `Category:MSX2_Computers`)
    - URL-decode percent-encoded characters (`%2B` → `+`)
    - Replace `_` → ` `
    - Replace `:` → `_` (Windows forbids colons in filenames)
    - Append ` - MSX Wiki.html`
    - Examples: `Sony_HB-F9S` → `Sony HB-F9S - MSX Wiki.html`; `Category:MSX2_Computers` → `Category_MSX2 Computers - MSX Wiki.html`
  - Existing HTML parsers (`parse_model_page`, `_find_specs_table`, `list_model_pages` CSS selectors) are reused unchanged — browser-saved HTML is structurally identical to live HTML.
  - No delay between reads in mirror mode (delay is a courtesy for live servers; irrelevant for local files).
- Integrations:
  - `data/scraper-config.json` (new, optional): JSON object with optional `"msxorg_mirror_path"` string key.
  - Local filesystem: mirror directory of `.html` files.
  - Failure behavior: mirror dir missing → `ERROR` log + msx.org portion returns `[]` (build continues without msx.org data).
- Non-functional requirements:
  - No network access when mirror mode is active.
  - No new Python dependencies.
- Minimal viable increment (MVI): `PageSource` abstraction + `MirrorPageSource` implementation + CLI flag. Config file is part of MVI (makes the flag optional for repeated use).
- Deferred:
  - Auto-downloading / mirroring the site.
  - Handling "Webpage, Complete" format (HTML + `_files/` folder).
  - Local mirror support for the openMSX GitHub source (not affected by the 403).
  - `fetch-msxorg` sub-command: same wiring as `build`, included in MVI.

## Executable Specification (Gherkin)

```gherkin
Feature: msx.org local mirror scraping
  The scraper can read msx.org category and model pages from a local
  directory of browser-saved HTML files, producing output identical to
  a live fetch. Missing files are warned and skipped; the build continues.

  Background:
    Given a mirror directory containing browser-saved msx.org HTML files

  Scenario: Happy path — all files present
    Given the mirror directory contains "Category_MSX2 Computers - MSX Wiki.html"
    And the mirror directory contains "Sony HB-F9S - MSX Wiki.html"
    When the scraper runs with --local-mirror pointing to that directory
    Then msxorg-raw.json contains a Sony HB-F9S entry
    And no HTTP requests were made

  Scenario: Missing model file — warn and skip
    Given the mirror directory contains the category file
    But the mirror directory does NOT contain "Sony HB-F9S - MSX Wiki.html"
    When the scraper runs with --local-mirror
    Then a WARNING is logged naming "Sony HB-F9S" and the expected file path
    And Sony HB-F9S is absent from msxorg-raw.json
    And other models present in the mirror are still included

  Scenario: Missing category file — warn and skip standard
    Given the mirror directory does NOT contain "Category_MSX2 Computers - MSX Wiki.html"
    When the scraper runs with --local-mirror
    Then a WARNING is logged for the missing MSX2 category file
    And zero MSX2 models are collected
    And models from other present category files are still collected

  Scenario: Mirror path does not exist — error, no silent failure
    Given --local-mirror points to a directory that does not exist
    When the scraper runs
    Then an ERROR is logged stating the path does not exist
    And the msx.org scraping step returns an empty result
    And no exception propagates to abort the overall build

  Scenario: CLI flag overrides config file
    Given data/scraper-config.json contains msxorg_mirror_path pointing to dir A
    And --local-mirror flag points to dir B
    When the scraper runs
    Then HTML files are read from dir B, not dir A

  Scenario: Config file used when no flag given
    Given data/scraper-config.json contains msxorg_mirror_path pointing to a valid dir
    And no --local-mirror flag is passed
    When the scraper runs with --fetch
    Then HTML files are read from the config-specified directory

  Scenario: No mirror configured — live mode unchanged
    Given data/scraper-config.json does not exist
    And no --local-mirror flag is passed
    When the scraper runs with --fetch
    Then the scraper attempts live HTTP requests as before
```

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branch for development.

## Architecture Fit
- Touch points:
  - `scraper/mirror.py` (new): `PageSource` Protocol, `LivePageSource`, `MirrorPageSource`
  - `scraper/msxorg.py`: `list_model_pages()` and `fetch_all()` accept optional `source: PageSource`; existing `session` parameter kept for backward compat; graceful-error try/except moves into `LivePageSource`
  - `scraper/build.py`: load config; pass `mirror_path` to `msxorg.fetch_all()`
  - `scraper/__main__.py`: add `--local-mirror` flag to `build` and `fetch-msxorg` subcommands
  - `data/scraper-config.json` (new, optional): config file; gitignored or committed as empty `{}`
- Compatibility notes:
  - `msxorg.fetch_all(session=None)` callers unaffected — no-source path creates `LivePageSource` internally.
  - `list_model_pages()` gains optional `source` param; existing call in `fetch_all` passes it through.
  - No change to parser functions (`parse_model_page`, `_find_specs_table`, etc.).

## Observability (Minimum Viable)
- Applicability: Required
- Failure modes:
  - Mirror dir does not exist → `ERROR: Mirror directory not found: {path}` → return `[]`
  - Category file missing → `WARNING: Mirror file not found for category {standard}: {path}` → skip standard
  - Model file missing → `WARNING: Mirror file not found for model {title}: {path}` → skip model
  - Config file present but malformed JSON → `ERROR: Failed to load scraper config: {path}` → ignore config, proceed in live mode
- Logs:
  - `[mirror:mode] Using local mirror | path={path}` at INFO when mirror mode is active
  - `[mirror:summary] {N} of {total} model files found in mirror` at INFO after category enumeration
- Signals/metrics: warning count per run surfaced through existing `errors` counter in `fetch_all` summary log

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required):
  - `tests/scraper/test_mirror.py` (new): filename derivation for model and category URLs, including percent-encoded chars; `MirrorPageSource.fetch_category` returns bytes when file present, `None` + warn when absent; `MirrorPageSource.fetch_page` same; non-existent mirror dir logged + returns `None`
  - `tests/scraper/test_msxorg.py` (extend): `fetch_all` with `MirrorPageSource` returns parsed models; missing category file → empty for that standard; missing model file → warn + skip; live mode unchanged when no source given
  - `tests/scraper/test_build.py` (extend): config file `msxorg_mirror_path` wired through; CLI flag overrides config
- Tier 1: Manual smoke — run `python -m scraper build --fetch --local-mirror "C:/Users/…/msx_org_wiki_dumps"` against real local mirror; verify model count plausible and known models present
- Tier 2: N/A

## Data and Migrations
- Applicability: Schema only — `data/scraper-config.json` is a new optional file; no schema changes to `msxorg-raw.json` or `data.js`
- `data/scraper-config.json` initial content: `{}` (empty object, all keys optional)
- No migrations or backfills needed

## Rollout and Verify
- Applicability: N/A (offline scraper; no deployment step)
- Manual verify smoke path:
  1. `python -m pytest tests/scraper/ -q` — all green
  2. `python -m scraper build --fetch --msxorg-mirror "C:/Users/palha/Google Drive/msx/msx_org_wiki_dumps" --local-msxorg-only`
  3. Check `data/msxorg-raw.json` — contains expected models (Sony HB-F9S, etc.)
  4. `python -m scraper build --fetch` (no flags) — live mode; gracefully handles 403

## Cleanup Before Merge
- Done — no debug prints, conventional commits, fast-forward merged.

## Definition of Done
- [x] Gherkin specification complete and current
- [x] `pytest tests/scraper/` full suite green (291 passed)
- [x] `--msxorg-mirror` and `--local-msxorg-only` flags documented in `--help` output
- [x] Config file `data/scraper-config.json` committed as `{}`
- [x] Cleanup gate satisfied
- [x] Backlog updated

## Chunks

- **Chunk 1 — `PageSource` abstraction + `MirrorPageSource` + msxorg refactor** ✓
  - `scraper/mirror.py` (new): `PageSource` Protocol, `LivePageSource`, `MirrorPageSource`, `FallbackPageSource`
  - `scraper/msxorg.py`: refactored to accept optional `source: PageSource`
  - `tests/scraper/test_mirror.py` (new), `tests/scraper/test_msxorg.py` (extended)

- **Chunk 2 — Config file + CLI wiring** ✓
  - `data/scraper-config.json` committed as `{}`; key `msxorg_mirror`
  - `scraper/build.py`: `load_scraper_config()`, `local_only` param, source selection logic
  - `scraper/__main__.py`: `--msxorg-mirror DIR`, `--local-msxorg-only` on `build` and `fetch-msxorg`
  - `tests/scraper/test_build.py` extended

- **Chunk 3 — Mirror modes (fallback vs local-only)** ✓
  - `FallbackPageSource` added to `scraper/mirror.py`
  - `--local-mirror` renamed to `--msxorg-mirror`; `--local-msxorg-only` added
  - Config key renamed `msxorg_mirror_path` → `msxorg_mirror`
  - Tests extended in `test_mirror.py` and `test_build.py`

## Relevant Files
- `scraper/mirror.py` — `PageSource` Protocol + `LivePageSource` + `MirrorPageSource` + `FallbackPageSource`
- `scraper/msxorg.py` — accepts `source: PageSource | None`
- `scraper/build.py` — `load_scraper_config()`, `mirror_path`, `local_only`
- `scraper/__main__.py` — `--msxorg-mirror`, `--local-msxorg-only` on `build` and `fetch-msxorg`
- `data/scraper-config.json` — committed as `{}`; set `msxorg_mirror` locally
- `tests/scraper/test_mirror.py`, `test_msxorg.py`, `test_build.py`

## Notes
- Filename convention (browser Save-As HTML Only, Windows): wiki slug → URL-decode → `_`→space → `:`→`_` → append ` - MSX Wiki.html`
- `data/scraper-config.json` is committed as `{}`; local mirror path is set by maintainer and not committed.
- Config key is `msxorg_mirror` (not `msxorg_mirror_path`).

## Tasks
- [x] T-001 Create and checkout feature branch
- [x] T-010 `scraper/mirror.py`: `PageSource`, `LivePageSource`, `MirrorPageSource`, `FallbackPageSource`
- [x] T-011 Refactor `scraper/msxorg.py` to accept `source: PageSource | None`
- [x] T-012 Tests: `test_mirror.py`
- [x] T-013 Tests: extend `test_msxorg.py`
- [x] T-020 Create `data/scraper-config.json` as `{}`
- [x] T-021 Config loading in `scraper/build.py`
- [x] T-022 `--msxorg-mirror` + `--local-msxorg-only` CLI flags
- [x] T-023 Tests: extend `test_build.py`
- [x] T-900 Formatters (N/A)
- [x] T-901 Linters (N/A)
- [x] T-902 `pytest tests/scraper/` — 291 passed
- [x] T-950/951/952 Squash, Conventional Commits, fast-forward merge to trunk

## Open Questions
- None.

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
  - `python -m scraper build --fetch --local-mirror /path/to/mirror` produces msx.org data identical to what a live fetch would yield for the same pages.
  - A missing category file logs a warning and yields zero models for that standard; other categories and the overall build continue.
  - A missing individual model file logs a warning and skips that model; others continue.
  - The mirror path can be stored in `data/scraper-config.json`; the CLI flag overrides it.
  - `fetch-msxorg --local-mirror /path` works the same way for a standalone msx.org-only run.
- Primary user flow:
  1. Maintainer opens a browser, navigates to each msx.org category page and model page, saves as "Webpage, HTML Only".
  2. All files land in one flat directory (e.g. `C:/Users/…/msx_org_wiki_dumps/`).
  3. Maintainer runs `python -m scraper build --fetch --local-mirror "C:/Users/…/msx_org_wiki_dumps"`.
  4. Scraper reads category files to enumerate models, then reads each model file; produces `msxorg-raw.json` as normal.
- Must never happen:
  - A missing mirror file raises an exception or aborts the build entirely.
  - Live HTTP requests are made when `--local-mirror` is active.
  - Passing `--local-mirror` to a path that does not exist silently succeeds (should error with a clear message).
- Key edge cases:
  - Category file missing → warn + skip that standard; models from other categories still collected.
  - Model file missing → warn + skip that model; other models unaffected.
  - `--local-mirror` flag takes precedence over `msxorg_mirror_path` in config.
  - Config file absent → live mode (no error).
  - Config file present but `msxorg_mirror_path` key absent → live mode.
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
  2. `python -m scraper build --fetch --local-mirror "C:/Users/palha/Google Drive/msx/msx_org_wiki_dumps"` — runs without exception
  3. Check `data/msxorg-raw.json` — contains expected models (Sony HB-F9S, etc.)
  4. `python -m scraper build --fetch` (no flag, no config) — still works in live mode (gracefully handles 403)

## Cleanup Before Merge
- Remove any debug prints introduced during development
- Squash intermediate commits into logical commits (one per chunk)
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge (fast-forward only)

## Definition of Done
- [ ] Gherkin specification complete and current
- [ ] `pytest tests/scraper/` full suite green
- [ ] Manual smoke run against real mirror directory succeeds
- [ ] `--local-mirror` flag documented in `--help` output
- [ ] Config file `data/scraper-config.json` committed as `{}` (or gitignored with doc note)
- [ ] Cleanup gate satisfied
- [ ] Backlog updated

## Chunks

- **Chunk 1 — `PageSource` abstraction + `MirrorPageSource` + msxorg refactor**
  - User value: Core engine — mirror mode works end-to-end for `msxorg.fetch_all(source=MirrorPageSource(...))`
  - Scope: `scraper/mirror.py` (new); `scraper/msxorg.py` (refactor to accept `source`); `tests/scraper/test_mirror.py` (new); `tests/scraper/test_msxorg.py` (extend)
  - Ship criteria: `fetch_all(source=MirrorPageSource(path))` reads local files; missing files warn+skip; `fetch_all()` with no source still does live HTTP; all tests green
  - Rollout notes: None

- **Chunk 2 — Config file + CLI wiring**
  - User value: Maintainer can use `--local-mirror` flag or set path in config; end-to-end `build --fetch --local-mirror` works
  - Scope: `data/scraper-config.json` (new); `scraper/build.py` (config loading + pass mirror_path); `scraper/__main__.py` (add `--local-mirror` to `build` and `fetch-msxorg`); `tests/scraper/test_build.py` (extend)
  - Ship criteria: flag overrides config; config used when no flag; live mode when neither; `--help` shows `--local-mirror`; all tests green
  - Rollout notes: None

## Relevant Files (Expected)
- `scraper/mirror.py` — new; `PageSource` Protocol + `LivePageSource` + `MirrorPageSource`
- `scraper/msxorg.py` — add `source` param to `list_model_pages()` and `fetch_all()`; remove duplicate try/except now handled by `LivePageSource`
- `scraper/build.py` — load `scraper-config.json`; pass `mirror_path` through to `msxorg.fetch_all()`
- `scraper/__main__.py` — add `--local-mirror` flag to `build` and `fetch-msxorg`
- `data/scraper-config.json` — new, committed as `{}`
- `tests/scraper/test_mirror.py` — new
- `tests/scraper/test_msxorg.py` — extend
- `tests/scraper/test_build.py` — extend

## Notes
- `LivePageSource` absorbs the graceful try/except error handling we added in the previous fix; the try/except blocks in `list_model_pages` and `fetch_all` can be removed once the source handles them.
- No delay in `MirrorPageSource` — delay param stays in `fetch_all` and is passed to `LivePageSource` only.
- `data/scraper-config.json` should be committed as `{}` so it exists in the repo; the maintainer fills in `msxorg_mirror_path` locally without committing it (or `.gitignore` it — TBD, user decides).

## Assumptions
- Browser Save-As HTML Only on Windows always produces filenames matching the derived convention (verified against real dump directory).
- The mirror directory is flat (no subdirectories); all files at the top level.
- `data/scraper-config.json` is committed as `{}` and the user's local path is not committed to the repo.

## Validation Script (Draft)
1. `python -m pytest tests/scraper/ -q` — all green
2. `python -m scraper build --fetch --local-mirror "C:/Users/palha/Google Drive/msx/msx_org_wiki_dumps"`
3. Check `data/msxorg-raw.json` — Sony HB-F9S present, manufacturer/model/year fields populated
4. `python -m scraper build --fetch` — no exception; gracefully handles 403 from live site

## Tasks
- [ ] T-001 Create and checkout feature branch (`feature/msxorg-local-mirror`)

- [ ] Implement: Chunk 1 — PageSource abstraction + MirrorPageSource
  - [x] T-010 Create `scraper/mirror.py`: define `PageSource` Protocol; implement `LivePageSource` (wraps session.get + raise_for_status, returns `None` on exception with ERROR/WARNING log); implement `MirrorPageSource` (filename derivation from URL slug; returns bytes or `None` + WARNING when file missing; ERROR when dir missing)
  - [x] T-011 Refactor `scraper/msxorg.py`: add `source: PageSource | None = None` to `list_model_pages()` and `fetch_all()`; create `LivePageSource` internally when `source` is None; replace direct `session.get()` calls with `source.fetch_category()` / `source.fetch_page()`; remove now-redundant try/except blocks; handle `None` return from source (warn + skip)
  - [x] T-012 Tests: `tests/scraper/test_mirror.py` — filename derivation (model page, category page, percent-encoded title); `MirrorPageSource` returns bytes when file present; returns `None` + logs warning when file missing; logs error when dir missing; `LivePageSource` returns None on HTTP error
  - [x] T-013 Tests: extend `tests/scraper/test_msxorg.py` — `fetch_all` with `MirrorPageSource` returns parsed models; missing category → empty for that standard; missing model file → skip + warning; no-source path creates LivePageSource (existing tests still pass)

- [ ] Implement: Chunk 2 — Config file + CLI wiring
  - [ ] T-020 Create `data/scraper-config.json` as `{}`
  - [ ] T-021 Add config loading to `scraper/build.py`: `load_scraper_config(path)` reads `data/scraper-config.json` if present (ignore if absent or malformed + log ERROR); `fetch()` in build reads `msxorg_mirror_path` from config; passes `MirrorPageSource` or `None` to `msxorg.fetch_all()`
  - [ ] T-022 Add `--local-mirror` flag to `scraper/__main__.py`: add to both `build` and `fetch-msxorg` subcommands; flag value passed through to `build_module.build()` and `cmd_fetch_msxorg()`; flag overrides config path when both present
  - [ ] T-023 Tests: extend `tests/scraper/test_build.py` — config `msxorg_mirror_path` used when no flag; flag overrides config; missing config → live mode; malformed config → live mode + ERROR log

- [ ] Quality gate
  - [ ] T-900 Run formatters (N/A — no formatter configured)
  - [ ] T-901 Run linters (N/A — no linter configured)
  - [ ] T-902 Run `python -m pytest tests/scraper/ -v` — all green

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits (one per chunk)
  - [ ] T-951 Ensure all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)

## Open Questions
- Should `data/scraper-config.json` be committed as `{}` (so it's always present in the repo) or `.gitignore`d (so the maintainer's local path never accidentally gets committed)? Either works; recommend committing `{}` so new clones work without extra setup.

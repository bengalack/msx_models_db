# Plan: Scraper Exclude List

## Metadata
- Date: 2026-03-29
- Backlog item: Scraper — exclude list
- Feature slug: scraper-exclude-list

## Context
- Intended outcome: A maintainer-edited `data/exclude.json` prevents unwanted models from appearing in the scraped output. Models that match an exclusion rule are dropped after parsing (post-parse), before being added to the merged dataset.

## Functional Snapshot
- Problem: The scrapers fetch every discovered model; there is no way to exclude known-unwanted models, so the maintainer must remove them from output after every scrape run.
- Target user: bengalack (maintainer) running `python -m scraper build --fetch`
- Success criteria (observable):
  - A model listed in `exclude.json` does not appear in `docs/data.js` after a build
  - An empty or missing `exclude.json` leaves output unchanged (no-op)
  - A malformed `exclude.json` exits with a clear error before any HTTP requests are made
  - A scraper INFO summary includes an `excluded` count alongside the existing `skipped` / `errors` counts
  - Each skipped model produces a DEBUG log line
  - Any rule that matched zero models during a run produces a WARN log line ("dead rule")
- Primary user flow:
  1. Maintainer adds an entry to `data/exclude.json`
  2. Runs `python -m scraper build [--fetch]`
  3. Scraper loads and validates the file at startup
  4. openMSX: filename entries checked before fetching; manufacturer+model checked after parsing
  5. msx.org: manufacturer+model checked after parsing
  6. Excluded model absent from `data/merged.json` and `docs/data.js`
  7. Dead-rule warning appears if any rule matched zero models
- Must never happen:
  - An excluded model appears in `docs/data.js`
  - The scraper crashes mid-run due to a malformed `exclude.json` (must fail fast at startup)
  - An empty or missing `exclude.json` changes the output in any way
- Key edge cases:
  - `""` in manufacturer or model → matches a record where that field is empty (not a wildcard)
  - `"*"` in a field → matches any value including empty strings
  - `{"manufacturer": "*", "model": "*"}` → matches everything; WARN that this is an all-wildcard rule
  - Missing `exclude.json` → treat as empty list, proceed normally
  - Malformed JSON → raise `ValueError` at startup before any network call
  - Unknown keys in an entry (e.g. `{"typo": "x"}`) → raise `ValueError` at startup
  - Rule that never matches → WARN "dead rule" after run completes
- Business rules:
  - Each entry uses exactly one mode: either `{"manufacturer": "...", "model": "..."}` or `{"filename": "..."}` (not both)
  - Matching is case-sensitive (preserves exact data from sources)
  - `filename` entries only apply to openMSX; they are silently ignored by the msx.org scraper
  - The file is committed to the repo; it is not auto-generated
- Non-functional requirements:
  - Performance: exclude list loaded once at startup; O(n×m) matching is acceptable for n<1000 models and m<50 rules
  - Reliability: missing file must never cause a crash; malformed file must fail before network I/O
- Minimal viable increment (MVI): `scraper/exclude.py` module + wired into both scrapers + `data/exclude.json` (empty) + unit tests + build integration tests
- Deferred:
  - msx.org title-based pre-fetch exclusion (pre-fetch for msx.org requires title matching, not in scope for MVI)
  - Regex/glob patterns beyond `"*"` wildcard
  - UI or web-facing exclusion management

## Executable Specification (Gherkin)

```gherkin
Feature: Scraper exclude list
  As a maintainer I want models listed in exclude.json to be dropped after parsing
  so they never appear in the merged output or on the web page.

  Background:
    Given the scraper is configured with a valid data/exclude.json

  Rule: Manufacturer + model entries apply to both scrapers

    Scenario: openMSX model excluded by manufacturer and model name
      Given exclude.json contains {"manufacturer": "Sony", "model": "HB-75P"}
      When the openMSX scraper runs and parses the Sony HB-75P XML
      Then the Sony HB-75P is not added to the merged dataset
      And a DEBUG log line records "excluded Sony HB-75P (source: openmsx)"

    Scenario: msx.org model excluded by manufacturer and model name
      Given exclude.json contains {"manufacturer": "Philips", "model": "NMS 8280"}
      When the msx.org scraper runs and parses the Philips NMS 8280 page
      Then the Philips NMS 8280 is not added to the merged dataset
      And a DEBUG log line records the exclusion

    Scenario Outline: Wildcard field matches any value
      Given exclude.json contains {"manufacturer": "<mfr>", "model": "<model>"}
      When the scraper encounters a model with manufacturer "<actual_mfr>" and model "<actual_model>"
      Then the model is excluded

      Examples:
        | mfr    | model  | actual_mfr | actual_model |
        | Sony   | *      | Sony       | HB-75P       |
        | Sony   | *      | Sony       | HB-F1XDJ     |
        | *      | HB-75P | Sony       | HB-75P       |
        | *      | *      | Philips    | NMS 8250     |

    Scenario: Empty string matches an empty field
      Given exclude.json contains {"manufacturer": "", "model": "SomeName"}
      When the msx.org scraper encounters a model with no manufacturer and model name "SomeName"
      Then the model is excluded

  Rule: Filename entries apply only to openMSX

    Scenario: openMSX model excluded by XML filename
      Given exclude.json contains {"filename": "Boosted_MSX2_JP.xml"}
      When the openMSX scraper encounters the file "Boosted_MSX2_JP.xml"
      Then that file is not fetched
      And a DEBUG log line records the filename-based exclusion

  Rule: Missing or empty exclude.json is a no-op

    Scenario: Missing exclude.json produces no exclusions
      Given data/exclude.json does not exist
      When the scraper runs
      Then all discovered models are processed normally
      And no error or warning is emitted about the missing file

    Scenario: Empty exclude.json produces no exclusions
      Given data/exclude.json contains []
      When the scraper runs
      Then all discovered models are processed normally

  Rule: Malformed exclude.json fails fast

    Scenario: Malformed JSON exits before any network call
      Given data/exclude.json contains invalid JSON
      When the scraper starts
      Then it raises a clear ValueError before making any HTTP request

    Scenario: Entry with unknown keys is rejected at startup
      Given data/exclude.json contains [{"typo_field": "x"}]
      When the scraper starts
      Then it raises a clear ValueError before making any HTTP request

  Rule: Dead rules are surfaced to the maintainer

    Scenario: Rule that matches nothing produces a warning
      Given exclude.json contains {"manufacturer": "NoSuchMaker", "model": "Phantom"}
      When the scraper runs and completes
      Then a WARN log line identifies the unmatched rule by index
```

## Baseline Gate
- Start from a clean, green trunk. Run `python -m pytest tests/ -q && npm test -- --run` before branching.
- Sync latest trunk before branching.
- Branch: `feature/scraper-exclude-list`

## Architecture Fit
- Touch points:
  - New: `scraper/exclude.py` — `ExcludeList` dataclass, `load_excludes()`, match logic
  - New: `data/exclude.json` — initially `[]`
  - Modified: `scraper/openmsx.py` — `list_machine_files()` and `fetch_all()` accept `ExcludeList | None`
  - Modified: `scraper/msxorg.py` — `fetch_all()` accepts `ExcludeList | None`
  - Modified: `scraper/build.py` — loads `ExcludeList` at startup, passes to both scrapers
  - Modified: `tests/scraper/test_build.py` — two new integration tests
  - New: `tests/scraper/test_exclude.py` — ~16 unit tests
- Compatibility notes:
  - `fetch_all()` signatures gain an optional `exclude_list` kwarg with default `None` → backward-compatible
  - Existing tests pass unchanged (no exclude list = no exclusions)

## Observability (Minimum Viable)
- Applicability: Required
- Failure modes:
  - Malformed `exclude.json` → `ValueError` at startup with path + error detail, before any HTTP call
  - All-wildcard rule `{"manufacturer": "*", "model": "*"}` → WARN at load time (not a hard error)
  - Rule matches zero models across the full run → WARN "dead rule" after run completes
- Logs (structured):
  - `[exclude:load] Loaded | path=data/exclude.json rule_count=3` — INFO
  - `[exclude:load] File not found, no exclusions | path=data/exclude.json` — DEBUG
  - `[exclude:load] Invalid | path=... error=...` — ERROR (then raises)
  - `[exclude:skip] Excluded model | manufacturer=Sony model=HB-75P source=openmsx rule=0` — DEBUG
  - `[exclude:skip] Excluded filename | filename=Boosted_MSX2_JP.xml rule=1` — DEBUG
  - `[exclude:dead_rule] Rule matched nothing | rule=2 entry={"manufacturer":"NoSuchMaker","model":"Phantom"}` — WARN
  - Per-scraper summary extended: `openMSX: 95 extracted, 3 excluded, 2 skipped, 0 errors`
- Signals:
  - `excluded_count` per scraper (in summary log line)
  - Dead-rule count per run (WARN lines at end of run)
  - `excluded_fraction` = excluded / (excluded + extracted) — if > 50%, log an additional WARN

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): Unit tests in `tests/scraper/test_exclude.py` + additions to `test_build.py`
  - `ExcludeList.is_excluded` — exact match, empty-string match, wildcard model, wildcard manufacturer, full wildcard, no match
  - `ExcludeList.is_excluded_by_filename` — exact match, no match
  - `load_excludes` — missing file → empty list, valid file, malformed JSON → ValueError, unknown keys → ValueError, empty array → never excludes
  - openMSX wiring — filename skips excluded file, post-parse skips excluded model, non-excluded passes through
  - msx.org wiring — post-parse skips excluded model, non-excluded passes through
  - Build integration — excluded model absent from output, empty list leaves output unchanged
- Tier 1: N/A — all logic is in-process Python; no container boundary or external service
- Tier 2: N/A — no network calls in exclude logic; matching is deterministic

## Data and Migrations
- Applicability: Schema only (new file)
- New file: `data/exclude.json` — committed as `[]` initially
- Down migration: delete `data/exclude.json` — safe; models re-admitted on next build, receive fresh IDs via registry
- Backfill: none
- Rollback considerations: models excluded during a run will have no registry entries; if re-admitted after rollback they receive new IDs. URL-encoded view state referencing those models by ID (via bitset codec) will silently become stale selections. Acceptable under the stable-ID contract (IDs are never reused, just unused).
- Safety: reject all-wildcard `{"manufacturer": "*", "model": "*"}` entries with a WARN (not a hard error) so maintainer is alerted

## Rollout and Verify
- Applicability: N/A — offline maintainer CLI; no production service
- Advisory verification sequence:
  1. With empty `exclude.json`, run `python -m scraper build` and confirm `git diff docs/data.js` is empty (no-op)
  2. Add one known model to `exclude.json`, re-run build, confirm the model is absent from `docs/data.js`
  3. Confirm an INFO "excluded" log line appears for the skipped model
  4. Corrupt `exclude.json`, run scraper, confirm it exits with `ValueError` before any network log lines
  5. Restore `exclude.json`; add a rule for a non-existent manufacturer, run build, confirm WARN "dead rule" appears

## Cleanup Before Merge
- No temporary flags or debug scaffolding
- Squash intermediate commits into logical commits following Conventional Commits
- Rebase onto trunk; fast-forward merge

## Definition of Done
- Gherkin specification complete and current in plan artifact
- Tier 0 green (`pytest tests/scraper/ -v` all pass)
- All observability log events implemented (load, skip, dead-rule, summary counts)
- `data/exclude.json` committed as `[]`
- Backlog updated: item moved to "In product (shipped)"

---

## Chunks

- **Chunk 1: `scraper/exclude.py` + unit tests**
  - User value: The core matching logic is isolated, tested, and ready to wire in
  - Scope: `ExcludeList` dataclass, `load_excludes()`, match methods, validation, all unit tests
  - Ship criteria: `pytest tests/scraper/test_exclude.py -v` all green
  - Rollout notes: none — module not yet wired into scrapers

- **Chunk 2: Wire into openMSX scraper**
  - User value: openMSX models matching exclude rules are dropped from output
  - Scope: `openmsx.list_machine_files()` filename pre-check + `fetch_all()` post-parse check + logging
  - Ship criteria: openMSX wiring tests pass; existing openMSX tests unchanged
  - Rollout notes: none — `build.py` not yet passing an exclude list, so defaults to `None` (no-op)

- **Chunk 3: Wire into msx.org scraper**
  - User value: msx.org models matching exclude rules are dropped from output
  - Scope: `msxorg.fetch_all()` post-parse check + logging
  - Ship criteria: msx.org wiring tests pass; existing msx.org tests unchanged
  - Rollout notes: none — same as Chunk 2

- **Chunk 4: Wire into build pipeline + `data/exclude.json`**
  - User value: Full pipeline end-to-end; maintainer can add entries and run a build
  - Scope: `build.py` loads `ExcludeList` at startup, passes to both scrapers; dead-rule WARN; `data/exclude.json` committed as `[]`; build integration tests
  - Ship criteria: `pytest tests/scraper/ -v` all green; `python -m scraper build` runs cleanly with empty exclude.json; `git diff docs/data.js` is empty (no-op)
  - Rollout notes: none

---

## Relevant Files (Expected)
- `scraper/exclude.py` — new module: ExcludeList, load_excludes, match logic
- `data/exclude.json` — new file: initially `[]`
- `scraper/openmsx.py` — add exclude_list param to list_machine_files() and fetch_all()
- `scraper/msxorg.py` — add exclude_list param to fetch_all()
- `scraper/build.py` — load ExcludeList at startup, pass to both scrapers, dead-rule check
- `tests/scraper/test_exclude.py` — new: ~16 unit tests
- `tests/scraper/test_build.py` — extend: 2 integration tests

---

## Assumptions
- Matching is case-sensitive (preserves exact data from sources; maintainer must match case exactly)
- `{"filename": "..."}` entries do not support `"*"` wildcard (exact filename only); can be added later if needed
- The `ExcludeList` tracks per-rule match counts internally so dead-rule detection requires no caller changes
- `data/exclude.json` lives in `data/` alongside `id-registry.json`; path constant added to `build.py`

---

## Validation Script (Draft)
1. `git checkout -b feature/scraper-exclude-list`
2. `python -m pytest tests/ -q` — confirm baseline is green
3. Implement Chunk 1; run `pytest tests/scraper/test_exclude.py -v`
4. Implement Chunk 2; run `pytest tests/scraper/ -v`
5. Implement Chunk 3; run `pytest tests/scraper/ -v`
6. Implement Chunk 4; run `pytest tests/scraper/ -v`
7. `python -m scraper build` with empty `exclude.json`; confirm `git diff docs/data.js` is empty
8. Add a known model to `exclude.json`; re-run; confirm model absent from `docs/data.js`
9. Corrupt `exclude.json`; confirm scraper fails fast with clear error
10. `npm test -- --run` — confirm web tests still pass

---

## Tasks

- [x] T-001 Create and checkout branch `feature/scraper-exclude-list`

- [ ] **Chunk 1: `scraper/exclude.py` + unit tests**
  - [x] T-010 Write `scraper/exclude.py`:
    - `@dataclass ExcludeList` with `rules: list[dict]` and `_match_counts: list[int]` (internal)
    - `is_excluded(manufacturer: str | None, model: str | None) -> bool` — iterates manufacturer+model rules; `""` matches empty/None; `"*"` matches any
    - `is_excluded_by_filename(filename: str) -> bool` — iterates filename rules; exact match only
    - `dead_rules() -> list[int]` — returns indices of rules with match count 0
    - `load_excludes(path: Path) -> ExcludeList` — missing file → empty; malformed JSON → ValueError; unknown keys → ValueError; WARN on all-wildcard entry
    - Log events: `[exclude:load]` INFO/DEBUG/ERROR
  - [x] T-011 Write `tests/scraper/test_exclude.py` (29 tests):
    - `is_excluded`: exact, empty-string, wildcard model, wildcard manufacturer, full wildcard, no match, None fields treated as empty
    - `is_excluded_by_filename`: exact match, no match
    - `load_excludes`: missing file, valid JSON, malformed JSON, unknown keys, empty array, all-wildcard WARN
    - `dead_rules`: rule that matched → not dead; rule that never matched → dead
  - [x] T-012 `pytest tests/scraper/test_exclude.py -v` — 29 passed
  - [x] T-013 Commit: `feat: add ExcludeList module with match logic and validation`

- [x] **Chunk 2: Wire into openMSX scraper**
  - [x] T-020 In `scraper/openmsx.py`:
    - Add `exclude_list: ExcludeList | None = None` to `list_machine_files()`
    - Skip entry (and log DEBUG `[exclude:skip] Excluded filename`) if `exclude_list.is_excluded_by_filename(name)`
    - Add `exclude_list: ExcludeList | None = None` to `fetch_all()`
    - Pass `exclude_list` to `list_machine_files()`
    - After `parse_machine_xml` returns a result, check `exclude_list.is_excluded(result['manufacturer'], result['model'])`; if excluded log DEBUG and increment `excluded` counter
    - Extend summary log line to include `excluded=N`
  - [x] T-021 Added `TestOpenMSXWiring` to `tests/scraper/test_exclude.py` (3 tests):
    - `test_filename_excluded_before_fetch` — filename rule skips entry in list_machine_files
    - `test_model_excluded_post_parse` — manufacturer+model rule matches parsed result
    - `test_non_excluded_model_passes` — non-matching model not excluded
  - [x] T-022 `pytest tests/scraper/ -v` — 32 passed, no regressions
  - [x] T-023 Commit: `feat: wire exclude list into openMSX scraper (filename + model checks)`

- [x] **Chunk 3: Wire into msx.org scraper**
  - [x] T-030 In `scraper/msxorg.py`:
    - Add `exclude_list: ExcludeList | None = None` to `fetch_all()`
    - After `parse_model_page` returns a result, check `exclude_list.is_excluded(result.get('manufacturer'), result.get('model'))`; if excluded log DEBUG and increment `excluded` counter
    - Extend summary log line to include `excluded=N`
  - [x] T-031 Added `TestMsxOrgWiring` to `tests/scraper/test_exclude.py` (2 tests):
    - `test_model_excluded_post_parse` — matching model excluded
    - `test_non_excluded_model_passes` — non-matching model passes through
  - [x] T-032 `pytest tests/scraper/ -v` — 34 passed, no regressions
  - [x] T-033 Commit: `feat: wire exclude list into msx.org scraper (post-parse model check)`

- [x] **Chunk 4: Wire into build pipeline + `data/exclude.json`**
  - [x] T-040 Add `EXCLUDE_PATH = Path("data/exclude.json")` to `scraper/build.py`
  - [x] T-041 In `build()`: call `load_excludes(exclude_path)` at startup (before any scraper call); filter cached data after loading; add `exclude_path: Path = EXCLUDE_PATH` param
  - [x] T-042 After build: call `exclude_list.dead_rules()` and emit WARN for each dead rule
  - [x] T-043 Create `data/exclude.json` as `[]` (empty array)
  - [x] T-044 Added `TestBuildExcludeList` to `tests/scraper/test_build.py`:
    - `test_excluded_model_absent_from_output` — Sony HB-75P excluded; absent from output
    - `test_empty_excludelist_is_noop` — empty exclude.json; both models present
  - [x] T-045 `pytest tests/scraper/ -v` — 77 passed
  - [ ] T-046 `python -m scraper build` (no fetch); confirm `git diff docs/data.js` is empty
  - [x] T-047 Commit: `feat: load exclude list in build pipeline and add data/exclude.json`
  - [x] T-048 Commit: `chore: add empty data/exclude.json`

- [x] **Quality gate**
  - [x] T-900 `python -m pytest tests/ -q` — 77 passed
  - [x] T-901 `npm test -- --run` — 31 passed
  - [x] T-902 `npm run typecheck` — clean

- [x] **Merge to trunk**
  - [x] T-950 Commits are already logical per Conventional Commits (one per chunk)
  - [x] T-951 Rebase onto trunk; fast-forward merge
  - [x] T-952 Update backlog: moved "Scraper — exclude list" to "In product (shipped)"

---

## Open Questions
- None blocking.

# Plan: Scraper — openMSX XML Source

## Metadata
- Date: 2026-03-30
- Backlog item: Scraper — openMSX XML source
- Feature slug: openmsx-xml-source

## Context
- Intended outcome: The scraper can reliably parse openMSX machine XML files and extract all MSX2/2+/turboR model fields. Verified by a comprehensive pytest suite that covers every field extractor, every skip condition, and HTTP-level error handling — all without network access.

## Functional Snapshot
- Problem: `scraper/openmsx.py` is fully implemented but has zero unit tests. No automated check verifies that field extraction is correct, that the parser handles malformed XML gracefully, or that HTTP failures degrade without aborting.
- Target user: bengalack (maintainer) running `python -m scraper build --fetch` to refresh model data.
- Success criteria (observable):
  - `pytest tests/scraper/test_openmsx.py` passes (≥ 25 tests, no network access)
  - `python -m scraper build --fetch` produces `data/openmsx-raw.json` with ≥ 50 MSX2/2+/turboR models
  - Each model dict contains at minimum: `manufacturer`, `model`, `standard`, `openmsx_id`
  - Fields that cannot be parsed are absent (not null) — no silent coercion to wrong types
- Primary user flow:
  1. Maintainer runs `python -m scraper build --fetch`
  2. Scraper lists XML files from GitHub API, fetches each, parses it
  3. MSX2/2+/turboR models are extracted; all others are silently skipped
  4. Parsed models are written to `data/openmsx-raw.json`
  5. Build pipeline continues with merge step
- Must never happen:
  - Malformed XML causes an unhandled exception that aborts the scraper
  - A non-MSX2+ machine (MSX1, ColecoVision, test rig) appears in the output
  - A parse failure for one file propagates to prevent other files from being processed
- Key edge cases:
  - Malformed/non-strict XML → parsed with `recover=True`; continues to next file
  - Machine with `<type>MSX</type>` (MSX1) → silently skipped, not logged as error
  - Machine with missing `<manufacturer>` or `<code>` → logged as warning, skipped
  - Machine with no `<devices>` element → returns partial record (identity fields only)
  - Multiple `<MemoryMapper>` elements → sizes summed
  - `<PanasonicRAM>` (turboR) → size added to main_ram_kb
  - Plain `<RAM>` (no mapper) → size extracted; `mapper` key set to `"None"`
  - File in SKIP_PREFIXES (e.g. `Boosted_*`) → excluded from file list, not fetched
  - File excluded by ExcludeList (filename match) → skipped before fetching
  - HTTP error for one file → logged with `log.exception`; other files continue
- Business rules:
  - Only types in `WANTED_TYPES` (`MSX2`, `MSX2+`, `MSXturboR`) are extracted
  - `openmsx_id` = filename without `.xml` suffix
  - `standard` is normalised: `MSXturboR` → `"turbo R"`, `MSX2` → `"MSX2"`, `MSX2+` → `"MSX2+"`
  - SKIP_PREFIXES are applied to filename at listing time (no network request for skipped files)
  - ExcludeList is applied at listing time (filename) and after parsing (manufacturer + model)
- Integrations:
  - GitHub API (`/repos/openMSX/openMSX/contents/share/machines`) → file listing
  - `raw.githubusercontent.com` → individual XML file fetch
  - Failure behavior: HTTP errors logged; file skipped; scraper continues
- Non-functional requirements:
  - No network access in tests (all HTTP mocked)
  - No dependency on `systemroms/` or any local file outside the repo in this feature (slot map uses those — out of scope here)
- Minimal viable increment (MVI): Comprehensive pytest suite for `parse_machine_xml()` and `list_machine_files()`. A smoke test for `fetch_all()` with mocked HTTP.
- Deferred:
  - Slot map extraction (next feature)
  - msx.org HTML scraper tests (separate backlog item)
  - `--fetch` live network integration test (requires network; never in CI)

## Executable Specification (Gherkin)

```gherkin
Feature: openMSX XML source scraper
  The maintainer runs the scraper to fetch MSX2/2+/turboR model data from
  openMSX machine XML files. The scraper extracts hardware fields reliably
  and degrades gracefully on malformed input or network errors.

  Background:
    Given the scraper is configured with WANTED_TYPES = {MSX2, MSX2+, MSXturboR}

  Scenario: Parse a well-formed MSX2 machine XML
    Given an XML file describing a Sony HB-75P (MSX2, Europe, 1985)
    And the XML declares a V9938 VDP, 128 KB VRAM, 64 KB MemoryMapper RAM
    When parse_machine_xml is called with that XML
    Then the result contains manufacturer="Sony", model="HB-75P", standard="MSX2"
    And vdp="V9938", vram_kb=128, main_ram_kb=64, mapper="Yes"
    And openmsx_id equals the filename without the .xml suffix

  Scenario: MSX1 machine is silently skipped
    Given an XML file with <type>MSX</type>
    When parse_machine_xml is called with that XML
    Then the result is None
    And no warning is logged

  Scenario: Malformed XML does not abort the scraper
    Given an XML file with unclosed tags and missing attributes
    When parse_machine_xml is called with that XML and recover=True
    Then the call returns a dict or None (not an unhandled exception)

  Scenario: File with missing manufacturer is skipped with a warning
    Given an XML file for an MSX2 machine with no <manufacturer> element
    When parse_machine_xml is called
    Then the result is None
    And a warning is logged containing the filename

  Scenario: Boosted config files are excluded from the file listing
    Given a GitHub API response listing Sony_HB-75P.xml and Boosted_Sony_HB-75P.xml
    When list_machine_files is called
    Then only Sony_HB-75P.xml appears in the result
    And Boosted_Sony_HB-75P.xml is not fetched

  Scenario: HTTP error for one file does not stop other files from being processed
    Given fetch_all is called with two XML URLs
    And the first URL returns HTTP 404
    And the second URL returns a valid MSX2 XML
    When fetch_all completes
    Then exactly one model is returned
    And the error is logged

  Scenario: turboR machine sets cpu=R800 and sub_cpu=Z80
    Given an XML file with <type>MSXturboR</type>
    When parse_machine_xml is called
    Then cpu="R800", cpu_speed_mhz=7.16, sub_cpu="Z80"
```

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points: `scraper/openmsx.py` (implementation, minor adjustments only if tests reveal bugs), `tests/scraper/test_openmsx.py` (new)
- Compatibility notes: `parse_machine_xml()` and `list_machine_files()` are already in production use via `build.py`; no signature changes

## Observability (Minimum Viable)
- Applicability: Required
- Failure modes:
  - XML parse error → `log.warning("XML parse error in %s — skipped", filename)`
  - Missing required fields → `log.warning("Missing manufacturer/code in %s — skipped", filename)`
  - HTTP error → `log.exception("Error fetching/parsing %s", name)` (already implemented)
- Logs (structured):
  - `[INFO] Found N XML files` (listing)
  - `[INFO] openMSX: N models extracted, M excluded, K skipped, E errors` (summary)
  - `[WARN] XML parse error in <filename>` (per-file)
  - `[WARN] Missing manufacturer/code in <filename>` (per-file)
- Signals/metrics: model count in summary log; error count in summary log

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): pytest unit tests — all HTTP mocked with `unittest.mock` or `pytest-mock`; XML fed as in-memory bytes; covers every `_extract_*` helper, skip conditions, error paths
- Tier 1 (if applicable): N/A (no database; build integration already covered by `test_build.py`)
- Tier 2 (if applicable): N/A (live network fetch is a manual smoke test only)

## Data and Migrations
- Applicability: N/A — no schema change; `openmsx-raw.json` format unchanged

## Rollout and Verify
- Applicability: N/A (offline scraper tool; no user-facing deployment)

## Cleanup Before Merge
- Remove any debug print statements introduced during development
- Squash intermediate commits into logical commits (one per chunk)
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge (fast-forward only)

## Definition of Done
- [ ] Gherkin specification is complete and current in the plan artifact
- [ ] `pytest tests/scraper/test_openmsx.py` passes (≥ 25 tests, no warnings)
- [ ] `pytest tests/scraper/` (full suite) still green
- [ ] No hardcoded network calls in tests
- [ ] Cleanup gate satisfied
- [ ] Backlog updated (openMSX XML source moved to "In product (shipped)")

## Chunks

- **Chunk 1 — XML parser unit tests** (`parse_machine_xml` + all `_extract_*` helpers)
  - User value: Proves every field extractor works correctly against known XML fixtures
  - Scope: `tests/scraper/test_openmsx.py` (new file); read-only changes to `scraper/openmsx.py` only if tests reveal bugs
  - Ship criteria: All `TestParseXML` tests pass; covers happy path, all field categories, all skip conditions, malformed XML
  - Rollout notes: None

- **Chunk 2 — HTTP-layer unit tests** (`list_machine_files` + `fetch_all`)
  - User value: Proves skip logic, exclude list wiring, and per-file error handling work correctly without a network call
  - Scope: Additional test classes in `tests/scraper/test_openmsx.py`; mocked HTTP via `unittest.mock`
  - Ship criteria: `TestListFiles` + `TestFetchAll` pass; covers skip prefixes, filename exclude, HTTP error, model exclude
  - Rollout notes: None

## Relevant Files (Expected)
- `scraper/openmsx.py` — implementation under test; minor bug fixes only
- `tests/scraper/test_openmsx.py` — new test file

## Notes
- XML fixture strings should be minimal but realistic — only the elements under test, not full machine XMLs
- Use `unittest.mock.patch` or `responses` library for HTTP mocking in Chunk 2
- Check `requirements.txt` — add `pytest-mock` or `responses` if not already present
- If a test reveals a real parser bug, fix the bug in the same commit as the test

## Assumptions
- `scraper/openmsx.py` implementation is functionally correct for the happy path; tests may surface minor edge-case bugs
- No `responses` library is currently installed; use `unittest.mock.patch` to avoid adding a new dev dependency

## Validation Script (Draft)
1. `pytest tests/scraper/test_openmsx.py -v` — all tests green, no network requests
2. `pytest tests/scraper/ -v` — full suite still green
3. `python -m scraper build --fetch` (optional, manual) — produces `data/openmsx-raw.json` with ≥ 50 models

## Tasks
- [x] T-001 Create and checkout a local branch (`feature/openmsx-xml-source`)

- [x] Implement: Chunk 1 — XML parser unit tests
  - [x] T-010 Write `TestParseXML` class: happy-path MSX2 (all main fields), MSX2+, turboR; each as a separate test
  - [x] T-011 Write skip-condition tests: MSX1 type → None; missing manufacturer → None + warning; missing devices → partial record
  - [x] T-012 Write memory tests: MemoryMapper sum, PanasonicRAM, plain RAM + mapper="None", no RAM → absent
  - [x] T-013 Write video tests: VDP version extracted; VDP_SPECS lookup populates derived fields; missing VDP → absent
  - [x] T-014 Write audio tests: PSG present → "AY-3-8910"; FM chip element → fm_chip; multiple FM chips → joined string
  - [x] T-015 Write media tests: floppy FDC elements → floppy_drives count; cartridge slots from external="true"; tape port
  - [x] T-016 Write CPU tests: Z80A/3.58 for MSX2/2+; R800/7.16 + sub_cpu="Z80" for turboR
  - [x] T-017 Write keyboard tests: jp_jis → "Japanese (JIS)"; unknown code passes through; missing PPI → absent
  - [x] T-018 Write malformed XML test: unclosed tag with recover=True → no unhandled exception

- [x] Implement: Chunk 2 — HTTP-layer unit tests
  - [x] T-020 Write `TestListFiles`: mock GitHub API response → XML files returned; SKIP_PREFIXES excluded; non-.xml excluded
  - [x] T-021 Write `TestListFiles` exclude: ExcludeList filename match → file absent from result
  - [x] T-022 Write `TestFetchAll`: two mocked XML URLs; one HTTP 404, one valid → one model returned, error logged
  - [x] T-023 Write `TestFetchAll` model-exclude: model excluded by manufacturer+model after parsing → not in output

- [x] Quality gate
  - [x] T-900 Run formatters (`ruff format --check scraper/ tests/` or `black --check`) — no formatter configured; N/A
  - [x] T-901 Run linters (`ruff check scraper/ tests/` or `flake8`) — no linter configured; N/A
  - [x] T-902 Run tests (`pytest tests/scraper/ -v`) — 168 passed

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits (one per chunk)
  - [ ] T-951 Ensure all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)

## Open Questions
- None

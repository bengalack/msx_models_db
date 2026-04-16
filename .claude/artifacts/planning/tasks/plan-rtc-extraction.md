# Plan: Scraper — RTC Column Extraction from openMSX XML

## Metadata
- Date: 2026-04-16
- Backlog item: Scraper — RTC column extraction
- Feature slug: rtc-extraction

## Context
- Intended outcome: The `rtc` column in `docs/data.js` is populated from openMSX machine XML files. Models with an `<RTC>` element under `<devices>` show "Yes"; those without show "No"; models with no XML file remain empty/null.

## Functional Snapshot
- Problem: The `rtc` column (id=98) exists in the schema but has no scraper extraction logic. All values are currently null unless manually supplied in `data/local-raw.json`. openMSX XML files reliably indicate RTC presence via an `<RTC>` child element under `<devices>`.
- Target user: bengalack (maintainer) running `python -m scraper build`; MSX enthusiasts reading the grid.
- Success criteria (observable):
  - After a build, models known to have RTC hardware (e.g. Panasonic FS-A1GT, Daewoo CPC-400S) show "Yes" in the `rtc` column.
  - Models without `<RTC>` in their XML show "No".
  - Models with no openMSX XML file show an empty cell (null).
  - A value in `data/local-raw.json` for `rtc` overrides the XML-derived value.
- Primary user flow:
  1. Maintainer runs `python -m scraper build`
  2. Scraper parses each openMSX machine XML
  3. Presence of `<RTC>` under `<devices>` is detected per model
  4. "Yes"/"No" written to the merged record
  5. `docs/data.js` is generated; grid shows "Yes"/"No"/empty in the RTC column
- Must never happen:
  - A model with a confirmed `<RTC>` element shows "No" or empty
  - A model with no XML file shows "No" (must be empty/null, not "No")
  - Existing fields on the model record are overwritten by this change
- Key edge cases:
  - `<devices>` absent → rtc not set (null); function not called
  - `<RTC>` present with any `id` attribute → "Yes" (tag presence only; attributes ignored)
  - `local-raw.json` entry provides `rtc` → local value wins per standard merge precedence
- Business rules:
  - Detection is tag-presence only: `<RTC>` anywhere as a direct child of `<devices>`
  - "No" means the XML was parsed and no `<RTC>` was found — not "unknown"
  - Null/empty means no XML data was available for this model
  - `local-raw.json` takes precedence over XML-derived value (existing merge rule, no change needed)
- Non-functional requirements:
  - Performance: one `devices.find("RTC")` call per XML — negligible
  - Reliability: must not affect existing fields or cause any parse failures
- Minimal viable increment (MVI): Add `_extract_rtc` to `scraper/openmsx.py`, wire into `parse_machine_xml`, add unit tests.
- Deferred:
  - Sourcing RTC data from msx.org (explicitly out of scope per PRD)
  - Any sub-field beyond presence/absence (e.g. battery-backed, RTC type)

## Executable Specification (Gherkin)

```gherkin
Feature: RTC column extraction from openMSX XML
  As a maintainer running the scraper,
  I want the rtc field populated from openMSX machine XML files
  so that the grid shows accurate RTC information without manual curation.

  Scenario: Model with RTC element produces "Yes"
    Given an openMSX machine XML for an MSX2+ model
    And the XML contains an <RTC id="Real time clock"> element under <devices>
    When parse_machine_xml processes the file
    Then the result dict contains rtc = "Yes"

  Scenario: Model without RTC element produces "No"
    Given an openMSX machine XML for an MSX2 model
    And the XML has a <devices> section with no <RTC> element
    When parse_machine_xml processes the file
    Then the result dict contains rtc = "No"

  Scenario: Model with no <devices> section produces no rtc field
    Given an openMSX machine XML with no <devices> element
    When parse_machine_xml processes the file
    Then the result dict does not contain an rtc key

  Scenario: local-raw.json value takes precedence over XML-derived value
    Given a merged record with rtc = "Yes" from openMSX XML
    And data/local-raw.json contains an entry for the same model with rtc = "No"
    When the build pipeline applies local overrides
    Then the final record has rtc = "No"
```

## Baseline Gate
- Start from a clean, green trunk. Run `python -m pytest tests/ -q` before branching.
- Sync latest trunk before branching.

## Architecture Fit
- Touch points: `scraper/openmsx.py` only — new `_extract_rtc` function + one call in `parse_machine_xml`
- Compatibility notes: Adds a new field to the result dict; existing fields untouched. Local-raw override path is unchanged (standard merge precedence already handles it).

## Observability (Minimum Viable)
- Applicability: N/A — no new failure modes; detection is a read-only tag search with no branching error paths.

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): Three unit tests in `tests/scraper/test_openmsx.py`:
  - `test_rtc_present` — XML with `<RTC>` → result["rtc"] == "Yes"
  - `test_rtc_absent` — XML with `<devices>` but no `<RTC>` → result["rtc"] == "No"
  - `test_rtc_no_devices` — XML without `<devices>` → "rtc" not in result
- Tier 1: N/A — no external dependency
- Tier 2: N/A

## Data and Migrations
- Applicability: Schema only (new field values in existing column)
- Up migration: Re-run `python -m scraper build` — new "Yes"/"No" values appear in `docs/data.js`
- Down migration: Remove `_extract_rtc` call; values revert to null on next build
- Backfill: None — next build populates all models
- Rollback: Removing the call on revert leaves `rtc` null for all models (safe; no ID changes)

## Rollout and Verify
- Applicability: N/A — offline maintainer CLI; no production service
- Advisory verification:
  1. Run `python -m pytest tests/scraper/test_openmsx.py -v` — new tests pass
  2. Run `python -m scraper build` (no fetch; uses cached XML)
  3. Check `docs/data.js`: search for `"rtc"` — confirm "Yes" values present for turbo R models and known MSX2+ models with RTC (e.g. Daewoo CPC-400S)
  4. Confirm at least one model shows "No" (any MSX2 without RTC)
  5. Confirm no model that was previously empty is now "No" incorrectly (spot-check msx.org-only models)

## Cleanup Before Merge
- No temporary flags or debug code
- Squash into one logical commit: `feat(openmsx): extract rtc field from <RTC> element under <devices>`
- Rebase onto trunk; fast-forward merge

## Definition of Done
- Gherkin specification complete and current in plan artifact
- Tier 0 green (`pytest tests/scraper/test_openmsx.py -v`)
- `docs/data.js` updated with `python -m scraper build` and spot-checked
- Backlog updated: item moved to "In product (shipped)"

---

## Chunks

- **Chunk 1: Extract + test**
  - User value: `rtc` column populated from XML; grid shows "Yes"/"No" for all models with XML data
  - Scope: Add `_extract_rtc()` to `scraper/openmsx.py`; call from `parse_machine_xml` after `_extract_connectivity`; add 3 unit tests
  - Ship criteria: `pytest tests/scraper/test_openmsx.py -v` green; `python -m scraper build` produces "Yes" values for known RTC models
  - Rollout notes: none

---

## Relevant Files (Expected)
- `scraper/openmsx.py` — add `_extract_rtc(devices, out)` and one call site in `parse_machine_xml`
- `tests/scraper/test_openmsx.py` — add 3 unit tests

---

## Assumptions
- `<RTC>` is always a direct child of `<devices>` (confirmed by inspection of CPC-400S and FS-A1GT XMLs)
- Tag presence is sufficient; no attribute or child content inspection needed
- The existing `local-raw.json` override path handles the "manual correction" case without any new code

## Validation Script (Draft)
1. `python -m pytest tests/scraper/test_openmsx.py -v` — confirm 3 new tests pass, no regressions
2. `python -m pytest tests/ -q` — confirm full suite still green
3. `python -m scraper build` — rebuild from cached data
4. `grep -c '"Yes"' docs/data.js` — confirm non-zero count of "Yes" values in RTC position
5. Open `docs/index.html` locally and scroll to RTC column — spot-check Panasonic FS-A1GT shows "Yes"

## Tasks

- [x] T-001 Create and checkout branch `feature/rtc-extraction`

- [x] **Chunk 1: Extract + test**
  - [x] T-010 In `scraper/openmsx.py`, add `_extract_rtc(devices, out)` after `_extract_connectivity`:
    - `out["rtc"] = "Yes" if devices.find("RTC") is not None else "No"`
  - [x] T-011 In `parse_machine_xml`, add `_extract_rtc(devices, result)` call after `_extract_connectivity(devices, result)`
  - [x] T-012 In `tests/scraper/test_openmsx.py`, add 3 tests:
    - `test_rtc_present` — `<devices><RTC id="Real time clock"/></devices>` → `result["rtc"] == "Yes"`
    - `test_rtc_absent` — `<devices><PSG id="PSG"/></devices>` → `result["rtc"] == "No"`
    - `test_rtc_no_devices` — no `<devices>` element → `"rtc" not in result`
  - [x] T-013 Commit: `feat(openmsx): extract rtc field from <RTC> element under <devices>`

- [x] **Quality gate**
  - [x] T-900 `python -m pytest tests/ -q` — all green
  - [x] T-901 `python -m scraper build` — rebuilds cleanly; "Yes" values present in data.js

- [x] **Merge to trunk**
  - [x] T-950 Commits follow Conventional Commits (single logical commit)
  - [x] T-951 Rebase onto trunk; fast-forward merge
  - [x] T-952 Update backlog: move "Scraper — RTC column extraction" to "In product (shipped)"

## Open Questions
- None blocking.

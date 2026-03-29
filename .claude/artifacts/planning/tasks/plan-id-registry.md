# Plan: ID Registry (Python)

## Metadata
- Date: 2026-03-29
- Backlog item: ID registry (Python)
- Feature slug: id-registry

## Context
- Intended outcome: A Python module that manages stable integer IDs for models and columns across scraper runs, ensuring URLs remain valid forever as data evolves.

## Functional Snapshot
- Problem: The scraper pipeline produces merged model data (158 models) but has no formal mechanism to assign and preserve stable integer IDs. The existing `data/id-registry.json` has 10 hand-curated seed entries; scaling to 158+ models requires a reliable, testable module that enforces all ID invariants.
- Target user: The project maintainer running the scraper pipeline on demand.
- Success criteria (observable):
  - Running the scraper assigns new IDs to unmatched models while preserving existing IDs for matched models
  - Re-running the scraper with identical input produces identical output (idempotent)
  - ID 0 is never assigned (reserved sentinel for URL codec)
  - No ID is ever reused or reassigned
  - Retired model IDs are tracked and excluded from reuse
  - `pytest tests/scraper/` exits 0
- Primary user flow:
  1. Maintainer runs `python -m scraper merge ...`
  2. Scraper loads `data/id-registry.json`
  3. For each merged model, registry looks up natural key (`manufacturer|model`, lowercased)
  4. Matched models reuse their existing ID; unmatched models get the next available ID
  5. Updated registry is written back to `data/id-registry.json`
- Must never happen:
  - ID 0 assigned to any model or column
  - An existing model's ID changes between scraper runs
  - A retired ID is reused for a new model
  - Registry file left in a corrupt/partial-write state
  - `next_model_id` or `next_column_id` decreases
- Key edge cases:
  - Registry file missing → create fresh registry (next IDs start at 1)
  - Registry file corrupt JSON → raise clear error, do not overwrite
  - Natural key with mixed case/whitespace → normalise before lookup
  - `next_model_id` approaches uint16 max (65535) → warn, do not wrap
  - Model present in previous run but absent in current run → retire (append to retired list), do not delete from registry
- Business rules:
  - Natural key = `f"{manufacturer}|{model}"` lowercased and stripped
  - IDs are monotonically incrementing uint16 integers (1–65535)
  - Column IDs are pre-assigned and mostly static; the module must support adding new columns
  - Registry is append-only for retirements; IDs are never removed from the models map
- Non-functional requirements:
  - Performance: Registry is tiny (<200 entries); load/save must be <100ms
  - Reliability: Atomic writes (write to temp file, then rename) to prevent corruption
- Minimal viable increment (MVI): `scraper/registry.py` module + unit tests + integration into merge CLI command
- Deferred:
  - Scraper write output (`docs/data.js` generation) — separate backlog item
  - Column ID management beyond simple add (column rename/retire is future work)
  - Interactive conflict resolution for ID collisions (none expected given natural key design)

## Executable Specification (Gherkin)

```gherkin
Feature: Stable ID assignment for MSX models
  The ID registry assigns permanent integer IDs to models and columns,
  ensuring URLs encoded with these IDs remain valid across all future
  scraper runs.

  Background:
    Given a registry file with 10 seed models (IDs 1–10) and 29 columns (IDs 1–29)

  Scenario: Existing model retains its ID
    When the scraper processes a model with natural key "sony|hb-75p"
    Then the registry returns ID 1 for that model
    And next_model_id remains unchanged

  Scenario: New model gets the next available ID
    When the scraper processes a model with natural key "sanyo|phc-77"
    Then the registry returns ID 11
    And next_model_id increments to 12

  Scenario: ID 0 is never assigned
    Given a fresh registry with next_model_id = 1
    When 200 models are processed
    Then no model has ID 0
    And all IDs are in range 1–200

  Scenario: Idempotent across runs
    When the same 158 models are processed twice
    Then the registry state after both runs is identical
    And every model has the same ID in both runs

  Scenario: Retired model ID is never reused
    Given model "panasonic|fs-a1" has ID 3
    When that model is retired
    And a new model "newbrand|newmodel" is processed
    Then the new model does not get ID 3
    And ID 3 appears in the retired_models list

  Scenario: Corrupt registry file causes clear error
    Given the registry file contains invalid JSON
    When the registry is loaded
    Then a clear error is raised with the file path
    And the file is not overwritten

  Scenario: Missing registry file creates fresh registry
    Given no registry file exists at the expected path
    When the registry is loaded
    Then a new registry is created with next_model_id = 1
    And next_column_id = 1
    And no models or columns are registered
```

## Baseline Gate
- Start from clean, green trunk (`main`). All quality checks exit 0 before branching.

## Architecture Fit
- Touch points:
  - `scraper/registry.py` — new; `IDRegistry` class with load/save/assign/retire
  - `scraper/merge.py` — call registry after merge to assign IDs
  - `scraper/__main__.py` — load registry at start of merge command, save after
  - `data/id-registry.json` — existing file, updated by registry module
  - `tests/scraper/test_registry.py` — new; pytest unit tests
- Compatibility notes:
  - The existing `id-registry.json` schema (version 1) is unchanged
  - The `merge.py` module currently returns raw dicts without IDs; the registry adds IDs post-merge
  - Existing scraper commands (`fetch-openmsx`, `fetch-msxorg`) are unaffected

## Observability (Minimum Viable)
- Applicability: Required (ID assignment errors are silent and permanent — must be logged)
- Failure modes:
  - Registry file missing → log warning, create fresh (logged at INFO)
  - Registry file corrupt → raise error with path (logged at ERROR)
  - ID 0 attempted → skip/error (logged at ERROR)
  - next_model_id > 65535 → raise error (logged at ERROR)
  - Write failure → log error, leave previous file intact
- Logs:
  - `[registry:load]` — INFO — fields: path, model_count, column_count, next_model_id
  - `[registry:assign]` — DEBUG — fields: natural_key, assigned_id, is_new
  - `[registry:retire]` — INFO — fields: natural_key, retired_id
  - `[registry:save]` — INFO — fields: path, model_count, new_entries, retired_entries
  - `[registry:error]` — ERROR — fields: error, path

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): `tests/scraper/test_registry.py` — pytest, ~20 test cases:
  - Load/save round-trip (existing file, missing file, corrupt file)
  - Natural key normalisation (case, whitespace, special chars)
  - ID assignment (match existing, assign new, monotonic increment)
  - ID 0 guard (never assigned)
  - Retirement (append-only, no reuse)
  - Idempotency (same input → same IDs)
  - Uint16 boundary (warn/error at 65535)
  - Column ID assignment (match existing, assign new)
- Tier 1: Integration test — registry + merge pipeline end-to-end with fixture data
- Tier 2: N/A

## Data and Migrations
- Applicability: N/A — the `id-registry.json` schema (version 1) is unchanged
- The existing 10 seed model entries and 29 column entries are preserved exactly
- New models (IDs 11+) are appended by the registry during merge runs
- Rollback: restore `data/id-registry.json` from git history; re-run scraper

## Rollout and Verify
- Applicability: N/A (offline CLI tool; no production deployment)
- Verification (manual smoke path after implementation):
  1. Run `pytest tests/scraper/ -v` — all tests green
  2. Run `python -m scraper merge --openmsx data/openmsx-raw.json --msxorg data/msxorg-raw.json -o data/merged.json` — verify registry updated
  3. Check `data/id-registry.json` — seed models (IDs 1–10) unchanged, new models assigned IDs 11+
  4. Re-run same merge command — verify registry is unchanged (idempotent)

## Cleanup Before Merge
- No debug `print()` statements (use logging module)
- All commits follow Conventional Commits
- Squash intermediate commits into logical commits

## Definition of Done
- Gherkin specification is complete and current in this plan artifact
- `pytest tests/scraper/` exits 0 with all registry tests green
- Scraper merge command integrates registry (loads, assigns IDs, saves)
- Existing seed model IDs (1–10) are preserved after a merge run
- Backlog updated (shipped item moved to "In product")

## Chunks

- Chunk 1: IDRegistry module + unit tests
  - User value: The registry logic is proven correct and locked down with tests before integration.
  - Scope: `scraper/registry.py` (IDRegistry class), `tests/scraper/test_registry.py`, `tests/scraper/__init__.py`
  - Ship criteria: `pytest tests/scraper/ -v` exits 0 with ~20 tests green
  - Rollout notes: none

- Chunk 2: Integrate registry into merge command
  - User value: Running the merge command now assigns stable IDs to all models and updates the registry file.
  - Scope: `scraper/__main__.py` (load/save registry in merge), `scraper/merge.py` (accept registry, call assign)
  - Ship criteria: `python -m scraper merge ...` updates `data/id-registry.json` with new model IDs; idempotent re-run
  - Rollout notes: none

## Relevant Files (Expected)
- `scraper/registry.py` — new; IDRegistry class
- `scraper/merge.py` — modify; accept registry for ID assignment
- `scraper/__main__.py` — modify; load/save registry in merge command
- `tests/scraper/__init__.py` — new; empty package init
- `tests/scraper/test_registry.py` — new; pytest unit tests
- `data/id-registry.json` — existing; updated by registry module

## Assumptions
- The existing `natural_key()` function in `scraper/merge.py` produces the canonical key format
- Column IDs are mostly static; new columns are rare and can be added via `assign_column_id()`
- The 158 merged models will include the 10 seed models (matched by natural key)
- Python `os.replace()` provides atomic file rename on Windows (NTFS)

## Validation Script (Draft)
1. Run `pytest tests/scraper/ -v` — all tests green
2. Run `python -m scraper merge --openmsx data/openmsx-raw.json --msxorg data/msxorg-raw.json -o data/merged.json` — no errors
3. Inspect `data/id-registry.json` — verify next_model_id > 10, seed models unchanged
4. Re-run merge — verify registry file is byte-identical (idempotent)
5. Verify no model has ID 0 in registry

## Tasks
- [ ] T-001 Create and checkout local branch `feature/id-registry`

- [ ] Chunk 1: IDRegistry module + unit tests
  - [ ] T-010 Create `scraper/registry.py`: IDRegistry class with `load()`, `save()`, `assign_model_id()`, `assign_column_id()`, `retire_model()`, `get_model_id()`, `get_column_id()`
  - [ ] T-011 Create `tests/scraper/__init__.py` and `tests/scraper/test_registry.py` with unit tests covering: load/save round-trip, natural key normalisation, ID assignment (match + new), ID 0 guard, retirement, idempotency, uint16 boundary, column IDs
  - [ ] T-012 Verify `pytest tests/scraper/ -v` exits 0
  - [ ] T-013 Commit: `feat: add IDRegistry module with stable ID assignment and unit tests`

- [ ] Chunk 2: Integrate registry into merge command
  - [ ] T-020 Modify `scraper/__main__.py` merge command: load registry before merge, pass to merge, save after
  - [ ] T-021 Modify `scraper/merge.py`: accept optional registry parameter, call `assign_model_id()` for each merged model, attach `id` field to output
  - [ ] T-022 Add integration test: merge with registry end-to-end, verify IDs assigned and idempotent
  - [ ] T-023 Verify full pipeline: `python -m scraper merge ...` updates registry correctly
  - [ ] T-024 Commit: `feat: integrate ID registry into scraper merge command`

- [ ] Quality gate
  - [ ] T-900 Run `pytest tests/scraper/ -v` — confirm 0 failures
  - [ ] T-901 Run merge end-to-end — confirm registry updated correctly
  - [ ] T-902 Verify idempotency — re-run merge, confirm registry unchanged

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Confirm all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge fast-forward only

## Open Questions
- None

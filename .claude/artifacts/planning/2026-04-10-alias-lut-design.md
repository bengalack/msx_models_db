# Alias LUT — Design Document

**Date:** 2026-04-10
**Status:** Approved

## Problem

Different data sources (msxorg, openmsx, local) use different names for the same manufacturer or model. For example, `"Al Alamiah"` (msxorg) and `"Sakhr"` (openmsx) refer to the same brand. Without normalization, these records never merge and appear as duplicates.

## Goal

A JSON-driven alias LUT that maps known source name variants to their canonical form. Applied at merge time so that cross-source records that were previously missed (due to natural key mismatch) now merge correctly. Raw cached data is never modified.

## Data File

**Path:** `data/aliases.json`

```json
{
  "manufacturer": {
    "CIEL": ["CIEL (Ademir Carchano)"],
    "Sakhr": ["Al Alamiah"]
  },
  "model": {
    "Expert Turbo": ["Expert 2+ Turbo"],
    "ML-G30 Model 1": ["ML-G30/model 1"],
    "ML-G30 Model 2": ["ML-G30/model 2"],
    "FS-A1mkII": ["FS-A1MK2"]
  }
}
```

**Rules:**
- Top-level keys are column/field names (any field present in a model record).
- Each sub-key is the **canonical** name; its array lists alias strings (source values to replace).
- Matching is **case-insensitive** — the source value is lowercased for lookup; replacement is always the canonical form as written.
- An alias string appearing under two different canonical names is a load-time error.

## Module: `scraper/aliases.py`

### `load_aliases(path: Path) -> dict`

- Reads and parses JSON.
- Raises `FileNotFoundError` if the file does not exist.
- Raises `ValueError` if:
  - JSON root is not a dict
  - Any column's value is not a dict
  - Any alias string appears under two different canonical names (conflict)
- Internally calls `_validate_no_conflicts`.
- Returns an **inverted lookup** `{column: {alias_lower: canonical}}` for O(1) case-insensitive lookups at apply time.

### `apply_aliases(record: dict, lut: dict) -> None`

- Mutates `record` in-place.
- For each column in `lut`: if `record.get(column, "").lower()` matches an alias key, replaces the field value with the canonical name.
- No-op if the column is absent from the record or the value has no alias.

### `_validate_no_conflicts(inverted: dict) -> None` (internal)

- Raises `ValueError("duplicate alias '{alias}' in column '{col}': maps to both '{a}' and '{b}'")`  on the first conflict found.

## Integration: `scraper/merge.py`

In `merge_models()`, after loading raw records from all sources, before computing `natural_key()`:

```python
alias_lut = load_aliases(Path("data/aliases.json"))

for record in all_records:
    apply_aliases(record, alias_lut)
```

`natural_key()` then operates on already-normalized names, enabling cross-source matches that were previously impossible.

## Error Handling

- Missing `data/aliases.json` → `FileNotFoundError` (no silent fallback).
- Malformed JSON → `ValueError`.
- Conflicting alias definitions → `ValueError` at load time.

## Testing: `tests/scraper/test_aliases.py`

| Test | What it checks |
|------|---------------|
| `test_load_aliases_returns_inverted_lut` | Basic happy path |
| `test_apply_aliases_replaces_canonical` | Alias value gets replaced with canonical |
| `test_apply_aliases_case_insensitive` | `"al alamiah"` matches alias `"Al Alamiah"` |
| `test_apply_aliases_canonical_unchanged` | Canonical value itself is never replaced |
| `test_apply_aliases_unknown_field_noop` | No error if column not in record |
| `test_duplicate_alias_raises_value_error` | Same alias under two canonicals → error |
| `test_missing_file_raises_file_not_found` | FileNotFoundError on missing file |
| `test_not_a_dict_raises_value_error` | Non-dict JSON root → ValueError |
| `test_invalid_json_raises_value_error` | Bad JSON → ValueError |
| `test_merge_uses_aliases` | Integration: two records with different manufacturer names merge into one |

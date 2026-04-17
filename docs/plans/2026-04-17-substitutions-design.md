# Substitutions Feature Design

**Date:** 2026-04-17
**Status:** Approved

## Overview

Add a `data/substitutions.json` config file that allows cell-value replacements to be applied as the final step of the scraper merge process — after `merge_models()` returns, before derived columns are computed.

## Use Case

Some scraped values are semantically empty but appear as non-null strings (e.g. `"none"` in the `manufacturer` column). Substitutions let maintainers clean these up declaratively without touching scraper code.

Example: replace `"none"` in `manufacturer` with `null` (renders as empty / em-dash in the UI).

## File Format: `data/substitutions.json`

```json
{
  "manufacturer": [
    {"match": "none", "replace": null}
  ],
  "region": [
    {"match": "^unknown", "replace": null},
    {"match": "south korea", "replace": "Korea"}
  ]
}
```

- **Keys** — model field names (same keys used in merged model dicts)
- **`match`** — regex pattern; matched via `re.search` (substring match)
- **`replace`** — `null` or a string; the replacement value when the pattern matches
- **Rule evaluation** — first matching rule wins per field per model
- **Absent file** — not an error; substitutions step is silently skipped

## New Functions in `merge.py`

### `load_substitutions(path: Path) -> dict[str, list[dict]]`

- Returns `{}` if the file does not exist
- Reads the JSON and compiles each `match` string into a `re.Pattern` (stored as `"pattern"` key)
- Raises `re.error` on invalid regex

### `apply_substitutions(models: list[dict], subs: dict) -> None`

- Mutates models in-place
- For each model, for each column in `subs`, for each rule:
  - Skip if current value is `None`
  - If `re.search(pattern, str(value))` matches → set field to `rule["replace"]`; stop checking further rules for that field

## Integration in `build.py`

New constant:
```python
SUBSTITUTIONS_PATH = Path("data/substitutions.json")
```

New parameter on `build()`:
```python
substitutions_path: Path = SUBSTITUTIONS_PATH
```

Pipeline insertion — between step 3 (merge) and step 4 (derive):
```python
subs = merge.load_substitutions(substitutions_path)
if subs:
    merge.apply_substitutions(merged, subs)
```

## Tests

Add to `tests/scraper/test_merge.py`:

- Exact substring match replaces value
- Partial substring match (pattern appears mid-value) replaces value
- Full regex pattern (e.g. `^none$`) works correctly
- No match leaves value unchanged
- `null` replacement sets field to `None`
- String replacement sets field to the new string
- First matching rule wins when multiple rules match
- Absent file returns `{}` from `load_substitutions`
- `None` values are skipped (not passed to `re.search`)

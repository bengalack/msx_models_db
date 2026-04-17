# Substitutions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `data/substitutions.json` support — column-keyed regex rules that replace cell values as the final step after merge, before derived columns are computed.

**Architecture:** Two new functions in `merge.py` (`load_substitutions`, `apply_substitutions`), called from `build.py` between step 3 (merge) and step 4 (derive). Rules use `re.search` (substring match). File absent = silent skip.

**Tech Stack:** Python stdlib only (`re`, `json`, `pathlib`). Tests via `pytest`.

---

### Task 1: `load_substitutions()` — tests then implementation

**Files:**
- Modify: `tests/scraper/test_merge.py` (append new test class)
- Modify: `scraper/merge.py` (append new function after `save_conflicts`)

**Step 1: Write the failing tests**

Append to `tests/scraper/test_merge.py`:

```python
import re
from pathlib import Path
import json
import tempfile
import os

from scraper.merge import load_substitutions


class TestLoadSubstitutions:
    def _write(self, data: dict) -> Path:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.write(fd, json.dumps(data).encode())
        os.close(fd)
        return Path(path)

    def test_absent_file_returns_empty(self):
        result = load_substitutions(Path("/nonexistent/substitutions.json"))
        assert result == {}

    def test_loads_single_rule(self):
        path = self._write({"manufacturer": [{"match": "none", "replace": None}]})
        result = load_substitutions(path)
        assert "manufacturer" in result
        assert len(result["manufacturer"]) == 1
        rule = result["manufacturer"][0]
        assert isinstance(rule["pattern"], re.Pattern)
        assert rule["replace"] is None

    def test_loads_string_replacement(self):
        path = self._write({"region": [{"match": "korea", "replace": "Korea"}]})
        result = load_substitutions(path)
        assert result["region"][0]["replace"] == "Korea"

    def test_compiles_regex(self):
        path = self._write({"manufacturer": [{"match": "^none$", "replace": None}]})
        result = load_substitutions(path)
        pattern = result["manufacturer"][0]["pattern"]
        assert pattern.search("none")
        assert not pattern.search("someone")

    def test_multiple_columns(self):
        path = self._write({
            "manufacturer": [{"match": "none", "replace": None}],
            "region": [{"match": "unknown", "replace": None}],
        })
        result = load_substitutions(path)
        assert set(result.keys()) == {"manufacturer", "region"}

    def test_multiple_rules_per_column(self):
        path = self._write({
            "manufacturer": [
                {"match": "none", "replace": None},
                {"match": "n/a", "replace": None},
            ]
        })
        result = load_substitutions(path)
        assert len(result["manufacturer"]) == 2
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/scraper/test_merge.py::TestLoadSubstitutions -v
```

Expected: `ImportError` or `AttributeError` — `load_substitutions` does not exist yet.

**Step 3: Implement `load_substitutions` in `merge.py`**

Append after `print_conflict_summary` (around line 415):

```python
# ── Substitutions ────────────────────────────────────────────────────


def load_substitutions(path: Path) -> dict[str, list[dict]]:
    """Load substitutions.json and compile regex patterns.

    Format: {"column_key": [{"match": "<regex>", "replace": <str|null>}, ...]}

    Returns {} if the file does not exist.
    Each rule dict in the returned structure has a compiled "pattern" key
    (re.Pattern) instead of the raw "match" string.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw: dict[str, list[dict]] = json.load(f)
    result: dict[str, list[dict]] = {}
    for column, rules in raw.items():
        compiled = []
        for rule in rules:
            compiled.append({
                "pattern": re.compile(rule["match"]),
                "replace": rule["replace"],
            })
        result[column] = compiled
    return result
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scraper/test_merge.py::TestLoadSubstitutions -v
```

Expected: all 6 tests PASS.

**Step 5: Commit**

```bash
git add scraper/merge.py tests/scraper/test_merge.py
git commit -m "feat(merge): add load_substitutions with regex compilation"
```

---

### Task 2: `apply_substitutions()` — tests then implementation

**Files:**
- Modify: `tests/scraper/test_merge.py` (append new test class)
- Modify: `scraper/merge.py` (append new function)

**Step 1: Write the failing tests**

Append to `tests/scraper/test_merge.py`:

```python
from scraper.merge import apply_substitutions
import re


class TestApplySubstitutions:
    def _subs(self, column: str, match: str, replace) -> dict:
        return {column: [{"pattern": re.compile(match), "replace": replace}]}

    def test_exact_substring_match_replaces_with_null(self):
        models = [{"manufacturer": "none", "model": "X"}]
        apply_substitutions(models, self._subs("manufacturer", "none", None))
        assert models[0]["manufacturer"] is None

    def test_partial_substring_match_replaces(self):
        models = [{"manufacturer": "Some none value"}]
        apply_substitutions(models, self._subs("manufacturer", "none", None))
        assert models[0]["manufacturer"] is None

    def test_no_match_leaves_value_unchanged(self):
        models = [{"manufacturer": "Yamaha"}]
        apply_substitutions(models, self._subs("manufacturer", "^none$", None))
        assert models[0]["manufacturer"] == "Yamaha"

    def test_string_replacement(self):
        models = [{"region": "south korea"}]
        apply_substitutions(models, self._subs("region", "south korea", "Korea"))
        assert models[0]["region"] == "Korea"

    def test_none_value_is_skipped(self):
        models = [{"manufacturer": None}]
        apply_substitutions(models, self._subs("manufacturer", "none", "X"))
        assert models[0]["manufacturer"] is None  # unchanged

    def test_missing_field_is_skipped(self):
        models = [{"model": "HB-10"}]
        apply_substitutions(models, self._subs("manufacturer", "none", None))
        assert "manufacturer" not in models[0]

    def test_first_matching_rule_wins(self):
        subs = {"manufacturer": [
            {"pattern": re.compile("none"), "replace": None},
            {"pattern": re.compile("none"), "replace": "NEVER"},
        ]}
        models = [{"manufacturer": "none"}]
        apply_substitutions(models, subs)
        assert models[0]["manufacturer"] is None

    def test_multiple_models_all_substituted(self):
        models = [{"manufacturer": "none"}, {"manufacturer": "none"}, {"manufacturer": "Yamaha"}]
        apply_substitutions(models, self._subs("manufacturer", "^none$", None))
        assert models[0]["manufacturer"] is None
        assert models[1]["manufacturer"] is None
        assert models[2]["manufacturer"] == "Yamaha"

    def test_empty_subs_is_noop(self):
        models = [{"manufacturer": "none"}]
        apply_substitutions(models, {})
        assert models[0]["manufacturer"] == "none"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/scraper/test_merge.py::TestApplySubstitutions -v
```

Expected: `ImportError` — `apply_substitutions` does not exist yet.

**Step 3: Implement `apply_substitutions` in `merge.py`**

Append after `load_substitutions`:

```python
def apply_substitutions(models: list[dict[str, Any]], subs: dict[str, list[dict]]) -> None:
    """Apply substitution rules to merged models in-place.

    For each model, for each column in subs, for each rule in order:
    if re.search(pattern, str(value)) matches, replace the field value
    with rule["replace"] and move on to the next field (first match wins).

    Fields absent from the model or set to None are skipped.
    """
    for model in models:
        for column, rules in subs.items():
            value = model.get(column)
            if value is None:
                continue
            for rule in rules:
                if rule["pattern"].search(str(value)):
                    model[column] = rule["replace"]
                    break
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scraper/test_merge.py::TestApplySubstitutions -v
```

Expected: all 9 tests PASS.

**Step 5: Run full test suite to check for regressions**

```bash
pytest tests/scraper/test_merge.py -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add scraper/merge.py tests/scraper/test_merge.py
git commit -m "feat(merge): add apply_substitutions — post-merge cell-value replacement"
```

---

### Task 3: Wire into `build.py`

**Files:**
- Modify: `scraper/build.py`

**Step 1: Add constant near top of file (with other path constants, around line 36)**

In `build.py`, after `DATA_JS_PATH = Path("docs/data.js")`, add:

```python
SUBSTITUTIONS_PATH = Path("data/substitutions.json")
```

**Step 2: Add parameter to `build()` signature**

In the `build()` function signature (around line 128), add after `resolutions_path`:

```python
substitutions_path: Path = SUBSTITUTIONS_PATH,
```

**Step 3: Insert substitutions step between step 3 and step 4**

After the `merge_models(...)` call block (around line 261) and before the `# Step 4:` comment, insert:

```python
    # Step 3b: Apply substitutions
    subs = merge.load_substitutions(substitutions_path)
    if subs:
        merge.apply_substitutions(merged, subs)
```

**Step 4: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add scraper/build.py
git commit -m "feat(build): apply substitutions after merge, before derive"
```

---

### Task 4: Create `data/substitutions.json` with example rule

**Files:**
- Create: `data/substitutions.json`

**Step 1: Write the file**

```json
{
  "manufacturer": [
    {"match": "(?i)^none$", "replace": null}
  ]
}
```

Note: `(?i)` makes it case-insensitive so `"None"`, `"NONE"`, `"none"` all match.

**Step 2: Verify the build still works (smoke test)**

```bash
python -m scraper build --local-only
```

Expected: completes without error, log shows normal build output.

**Step 3: Commit**

```bash
git add data/substitutions.json
git commit -m "data: add substitutions.json — map none → null in manufacturer"
```

---

## Done

All four tasks complete. The `data/substitutions.json` file is the maintainer-facing config — add new rules there as needed, no code changes required.

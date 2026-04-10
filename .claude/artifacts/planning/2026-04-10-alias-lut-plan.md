# Alias LUT Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a JSON-driven alias LUT (`data/aliases.json`) that normalizes manufacturer/model/any-field name variants to canonical forms at merge time, enabling cross-source records that were previously unmatched to merge correctly.

**Architecture:** New module `scraper/aliases.py` with `load_aliases()` and `apply_aliases()`. `merge_models()` in `scraper/merge.py` calls `apply_aliases()` on every raw record before computing `natural_key()`. Matching is case-insensitive; conflicting alias definitions raise `ValueError` at load time.

**Tech Stack:** Python stdlib only (`json`, `pathlib`). No new dependencies.

---

### Task 1: Create `scraper/aliases.py` with load/validate/apply

**Files:**
- Create: `scraper/aliases.py`
- Test: `tests/scraper/test_aliases.py`

**Step 1: Write the failing tests**

Create `tests/scraper/test_aliases.py`:

```python
"""Unit tests for scraper/aliases.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scraper.aliases import apply_aliases, load_aliases


# ---------------------------------------------------------------------------
# load_aliases — happy path
# ---------------------------------------------------------------------------

def test_load_aliases_returns_inverted_lut(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
        "model": {"Expert Turbo": ["Expert 2+ Turbo"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    # Inverted: {column: {alias_lower: canonical}}
    assert lut["manufacturer"]["al alamiah"] == "Sakhr"
    assert lut["model"]["expert 2+ turbo"] == "Expert Turbo"


def test_load_aliases_multiple_aliases(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"CIEL": ["CIEL (Ademir Carchano)", "ciel computers"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut["manufacturer"]["ciel (ademir carchano)"] == "CIEL"
    assert lut["manufacturer"]["ciel computers"] == "CIEL"


# ---------------------------------------------------------------------------
# apply_aliases
# ---------------------------------------------------------------------------

def test_apply_aliases_replaces_canonical(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Al Alamiah", "model": "AX-350"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"
    assert record["model"] == "AX-350"  # untouched


def test_apply_aliases_case_insensitive(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "al alamiah"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"


def test_apply_aliases_canonical_unchanged(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Sakhr"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"


def test_apply_aliases_unknown_field_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"model": "AX-350"}  # no 'manufacturer' key
    apply_aliases(record, lut)
    assert record == {"model": "AX-350"}


def test_apply_aliases_none_value_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": None}
    apply_aliases(record, lut)
    assert record["manufacturer"] is None


# ---------------------------------------------------------------------------
# load_aliases — error cases
# ---------------------------------------------------------------------------

def test_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        load_aliases(missing)


def test_not_a_dict_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_aliases(lut_file)


def test_column_value_not_dict_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({"manufacturer": ["Al Alamiah"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="manufacturer"):
        load_aliases(lut_file)


def test_invalid_json_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_aliases(lut_file)


def test_duplicate_alias_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {
            "Sakhr":    ["Al Alamiah"],
            "Al Sakhr": ["Al Alamiah"],  # same alias, different canonical
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate alias"):
        load_aliases(lut_file)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/scraper/test_aliases.py -v
```

Expected: `ImportError` — `scraper.aliases` does not exist yet.

**Step 3: Implement `scraper/aliases.py`**

```python
"""Alias LUT — normalize field values to canonical names at merge time."""
from __future__ import annotations

import json
from pathlib import Path


def load_aliases(path: Path) -> dict[str, dict[str, str]]:
    """Load and validate an alias JSON file.

    Returns an inverted lookup: {column: {alias_lower: canonical}}.
    Raises FileNotFoundError if the file is absent.
    Raises ValueError on malformed JSON, wrong structure, or conflicting aliases.
    """
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object at top level")

    inverted: dict[str, dict[str, str]] = {}
    for column, mappings in raw.items():
        if not isinstance(mappings, dict):
            raise ValueError(
                f"{path}: value for column '{column}' must be an object"
            )
        col_lut: dict[str, str] = {}
        for canonical, aliases in mappings.items():
            for alias in aliases:
                key = alias.lower()
                if key in col_lut and col_lut[key] != canonical:
                    raise ValueError(
                        f"{path}: duplicate alias '{alias}' in column '{column}': "
                        f"maps to both '{col_lut[key]}' and '{canonical}'"
                    )
                col_lut[key] = canonical
        inverted[column] = col_lut

    return inverted


def apply_aliases(record: dict, lut: dict[str, dict[str, str]]) -> None:
    """Replace alias values in *record* with their canonical names (in-place)."""
    for column, alias_map in lut.items():
        value = record.get(column)
        if not isinstance(value, str):
            continue
        canonical = alias_map.get(value.lower())
        if canonical is not None:
            record[column] = canonical
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scraper/test_aliases.py -v
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add scraper/aliases.py tests/scraper/test_aliases.py
git commit -m "feat(aliases): add alias LUT module with load/validate/apply"
```

---

### Task 2: Wire alias LUT into `merge_models()`

**Files:**
- Modify: `scraper/merge.py`
- Modify: `tests/scraper/test_aliases.py` (add integration test)

**Step 1: Add integration test**

Append to `tests/scraper/test_aliases.py`:

```python
# ---------------------------------------------------------------------------
# Integration — alias application in merge_models
# ---------------------------------------------------------------------------

def test_merge_uses_aliases(tmp_path):
    """Two records with alias manufacturer names merge into one after alias application."""
    from scraper.merge import merge_models

    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")

    openmsx_records = [{"manufacturer": "Sakhr",     "model": "AX-350", "generation": "MSX2"}]
    msxorg_records  = [{"manufacturer": "Al Alamiah","model": "AX-350", "generation": "MSX2"}]

    merged = merge_models(openmsx_records, msxorg_records, alias_path=alias_file)
    assert len(merged) == 1
    assert merged[0]["manufacturer"] == "Sakhr"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/scraper/test_aliases.py::test_merge_uses_aliases -v
```

Expected: FAIL — `merge_models` does not accept `alias_path` yet.

**Step 3: Update `scraper/merge.py`**

Open `scraper/merge.py`. Find the `merge_models()` signature. Add the `alias_path` parameter and apply aliases before `natural_key()` indexing.

- Add import at top of file:
  ```python
  from scraper.aliases import apply_aliases, load_aliases
  ```

- Update `merge_models()` signature to accept `alias_path`:
  ```python
  def merge_models(
      openmsx: list[dict],
      msxorg: list[dict],
      local: list[dict] | None = None,
      alias_path: Path | None = None,
  ) -> list[dict]:
  ```

- Early in `merge_models()`, before building any index, add:
  ```python
  alias_lut: dict = {}
  if alias_path is not None:
      alias_lut = load_aliases(alias_path)

  all_records = [*openmsx, *(msxorg or []), *(local or [])]
  for record in all_records:
      apply_aliases(record, alias_lut)
  ```

  Make sure this happens **before** any `natural_key()` call on those records.

**Step 4: Update `scraper/build.py` to pass `alias_path`**

In `build.py`, find where `merge_models()` is called. Pass the alias file path:

```python
from pathlib import Path
# ...
merged = merge_models(
    openmsx_models,
    msxorg_models,
    local=local_models,
    alias_path=Path("data/aliases.json") if Path("data/aliases.json").exists() else None,
)
```

If `data/aliases.json` does not exist, `alias_path=None` is passed and no aliasing occurs (graceful degradation — useful before the file is created).

**Step 5: Run integration test to verify it passes**

```bash
pytest tests/scraper/test_aliases.py -v
```

Expected: all tests PASS.

**Step 6: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS. If any existing test breaks because `merge_models` signature changed, update the test to pass `alias_path=None` explicitly or rely on the default.

**Step 7: Commit**

```bash
git add scraper/merge.py scraper/build.py tests/scraper/test_aliases.py
git commit -m "feat(merge): apply alias LUT before natural_key merge"
```

---

### Task 3: Create `data/aliases.json` with known aliases

**Files:**
- Create: `data/aliases.json`

**Step 1: Create the file**

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

**Step 2: Verify the file is valid**

```bash
python -c "from scraper.aliases import load_aliases; from pathlib import Path; lut = load_aliases(Path('data/aliases.json')); print('OK:', {c: len(v) for c, v in lut.items()})"
```

Expected output: `OK: {'manufacturer': 2, 'model': 4}`

**Step 3: Run a build to confirm aliases fire correctly**

```bash
python -m scraper build 2>&1 | head -40
```

Verify no errors. If `--fetch` was previously run and cached data exists, the merged output should now correctly unify alias names.

**Step 4: Commit**

```bash
git add data/aliases.json
git commit -m "feat(data): add aliases.json with known manufacturer and model variants"
```

---

### Task 4: Add alias LUT entry count to test_build.py (smoke test)

**Files:**
- Modify: `tests/scraper/test_build.py`

Check whether `test_build.py` has a test that validates the alias file structure. If not, add a lightweight smoke test to catch future file corruption:

**Step 1: Add smoke test**

Find the section in `tests/scraper/test_build.py` that validates data files (near the slotmap LUT tests). Add:

```python
def test_aliases_json_loads_without_error():
    from scraper.aliases import load_aliases
    lut = load_aliases(Path("data/aliases.json"))
    assert isinstance(lut, dict)
    assert "manufacturer" in lut or "model" in lut
```

**Step 2: Run the test**

```bash
pytest tests/scraper/test_build.py::test_aliases_json_loads_without_error -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add tests/scraper/test_build.py
git commit -m "test(build): add smoke test for data/aliases.json"
```

---

### Task 5: Add to product requirements

**Files:**
- Modify: `.claude/artifacts/planning/product-requirements.md`

Add a section documenting the alias LUT rule. Find the section on merge/normalization rules and append:

```markdown
### Alias normalization (merge time)

Before computing `natural_key()` during merge, all records are passed through an alias LUT (`data/aliases.json`). The LUT maps canonical names to arrays of known aliases, keyed by column name. Any alias value found in a record is replaced with the canonical name. Matching is case-insensitive. Conflicting alias definitions (same alias mapped to two different canonical names) are rejected at load time with a `ValueError`. If the file is absent, no aliasing occurs.
```

**Step 2: Commit**

```bash
git add .claude/artifacts/planning/product-requirements.md
git commit -m "docs(requirements): document alias LUT normalization rule"
```

# Expansion Slots Column + Slotmap-Derived Cart Slots Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an "Exp Slots" column (id=101) to the Media group and make both `cartridge_slots` and `expansion_slots` derived from the final merged slotmap, with a scraped fallback for cart slots.

**Architecture:** The scrapers rename their raw cart-slot output to `scraped_cart_slots` (a new hidden column). A shared `_count_slotmap(model, kind)` helper in `columns.py` walks the 64 slotmap keys and counts matching CS*/ES* sub-slots. Both `cartridge_slots` (id=19) and `expansion_slots` (id=101) gain `derive` lambdas that call this helper; cart slots falls back to `scraped_cart_slots` when the slotmap is empty.

**Tech Stack:** Python 3.11+, pytest — no new dependencies.

---

### Task 1: Rename `cartridge_slots` → `scraped_cart_slots` in `scraper/openmsx.py`

**Files:**
- Modify: `scraper/openmsx.py:322-323`
- Test: `tests/scraper/test_openmsx.py:264-272`

**Step 1: Write the failing test**

In `tests/scraper/test_openmsx.py`, update the existing test `test_cartridge_slots_from_external_primary` to assert `scraped_cart_slots` instead of `cartridge_slots`:

```python
def test_cartridge_slots_from_external_primary(self):
    extra = (
        '<primary slot="0"/>'
        '<primary slot="1" external="true"/>'
        '<primary slot="2" external="true"/>'
    )
    xml = _xml(_info(), extra_root=extra)
    result = parse_machine_xml(xml, "test.xml")
    assert result["scraped_cart_slots"] == 2
    assert "cartridge_slots" not in result
```

**Step 2: Run test to verify it fails**

```
pytest tests/scraper/test_openmsx.py::TestMemory::test_cartridge_slots_from_external_primary -v
```

Expected: FAIL — `KeyError: 'scraped_cart_slots'` (key not yet renamed)

**Step 3: Implement**

In `scraper/openmsx.py` line 322-323, change:

```python
    if cart_count:
        out["cartridge_slots"] = cart_count
```

to:

```python
    if cart_count:
        out["scraped_cart_slots"] = cart_count
```

**Step 4: Run test to verify it passes**

```
pytest tests/scraper/test_openmsx.py::TestMemory::test_cartridge_slots_from_external_primary -v
```

Expected: PASS

**Step 5: Run full test suite to check for regressions**

```
pytest tests/scraper/test_openmsx.py -v
```

Expected: all tests pass

**Step 6: Commit**

```bash
git add scraper/openmsx.py tests/scraper/test_openmsx.py
git commit -m "refactor(openmsx): rename cartridge_slots → scraped_cart_slots"
```

---

### Task 2: Rename `cartridge_slots` → `scraped_cart_slots` in `scraper/msxorg.py`

**Files:**
- Modify: `scraper/msxorg.py:218-270` (three occurrences)
- Test: `tests/scraper/test_msxorg.py`

**Step 1: Write a failing test**

In `tests/scraper/test_msxorg.py`, find or add a test that asserts `scraped_cart_slots` is set from parsed page text. Add this test to the appropriate class (likely `TestParseModelPage` or similar):

```python
def test_cartridge_slots_from_specs_table(self):
    """msxorg parser stores raw slot count under scraped_cart_slots."""
    html = """
    <html><body>
    <table class="wikitable">
      <tr><th>Cartridge slots</th><td>2 cartridge slots</td></tr>
    </table>
    </body></html>
    """
    from scraper.msxorg import _parse_specs_table
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    result = _parse_specs_table(soup)
    assert result.get("scraped_cart_slots") == 2
    assert "cartridge_slots" not in result
```

**Step 2: Run test to verify it fails**

```
pytest tests/scraper/test_msxorg.py -k "cartridge" -v
```

Expected: FAIL — `scraped_cart_slots` not yet set

**Step 3: Implement**

In `scraper/msxorg.py`, replace all three occurrences of `"cartridge_slots"` with `"scraped_cart_slots"`:

- Line ~218-220 (specs table extraction):
  ```python
  result["scraped_cart_slots"] = int(m.group(1))
  ```
- Line ~268-270 (connections section):
  ```python
  result["scraped_cart_slots"] = int(m.group(1))
  # ...
  elif "scraped_cart_slots" not in result:
      result["scraped_cart_slots"] = 2  # common default
  ```

**Step 4: Run test to verify it passes**

```
pytest tests/scraper/test_msxorg.py -k "cartridge" -v
```

Expected: PASS

**Step 5: Run full msxorg test suite**

```
pytest tests/scraper/test_msxorg.py -v
```

Expected: all tests pass

**Step 6: Commit**

```bash
git add scraper/msxorg.py tests/scraper/test_msxorg.py
git commit -m "refactor(msxorg): rename cartridge_slots → scraped_cart_slots"
```

---

### Task 3: Update `_PREFER_OPENMSX` in `scraper/merge.py`

**Files:**
- Modify: `scraper/merge.py:80`

**Step 1: Write a failing test**

In `tests/scraper/test_merge.py`, add a test that verifies `scraped_cart_slots` (not `cartridge_slots`) is the field where openMSX wins on conflict:

```python
def test_scraped_cart_slots_prefers_openmsx():
    """scraped_cart_slots conflict: openMSX value wins."""
    from scraper.merge import merge_models
    o = [{"manufacturer": "Acme", "model": "X", "scraped_cart_slots": 2}]
    m = [{"manufacturer": "Acme", "model": "X", "scraped_cart_slots": 1}]
    merged = merge_models(o, m)
    assert merged[0]["scraped_cart_slots"] == 2
```

**Step 2: Run test to verify it fails**

```
pytest tests/scraper/test_merge.py::test_scraped_cart_slots_prefers_openmsx -v
```

Expected: FAIL — `scraped_cart_slots` not yet in `_PREFER_OPENMSX`, so msx.org value (1) wins instead of openMSX (2), or the field may not be present at all

**Step 3: Implement**

In `scraper/merge.py` line 80, change:

```python
_PREFER_OPENMSX: set[str] = {"cartridge_slots", "vdp", "vram_kb", "main_ram_kb", "psg"}
```

to:

```python
_PREFER_OPENMSX: set[str] = {"scraped_cart_slots", "vdp", "vram_kb", "main_ram_kb", "psg"}
```

**Step 4: Run test to verify it passes**

```
pytest tests/scraper/test_merge.py::test_scraped_cart_slots_prefers_openmsx -v
```

Expected: PASS

**Step 5: Run full merge test suite**

```
pytest tests/scraper/test_merge.py -v
```

Expected: all tests pass

**Step 6: Commit**

```bash
git add scraper/merge.py tests/scraper/test_merge.py
git commit -m "refactor(merge): track scraped_cart_slots in _PREFER_OPENMSX"
```

---

### Task 4: Add `_count_slotmap`, `scraped_cart_slots`, and derived columns to `scraper/columns.py`

**Files:**
- Modify: `scraper/columns.py`
- Test: `tests/scraper/test_columns.py`

**Step 1: Write failing tests**

Add a new test class to `tests/scraper/test_columns.py`:

```python
import re
from scraper.columns import _count_slotmap, COLUMNS, column_by_key


class TestCountSlotmap:
    """Tests for the _count_slotmap helper."""

    def _model(self, mapping: dict) -> dict:
        """Build a sparse model dict with only the specified slotmap keys."""
        m: dict = {}
        for ms in range(4):
            for ss in range(4):
                m[f"slotmap_{ms}_{ss}_0"] = None
        m.update(mapping)
        return m

    def test_counts_cs_slots(self):
        model = self._model({"slotmap_1_0_0": "CS1", "slotmap_2_0_0": "CS2"})
        assert _count_slotmap(model, "CS") == 2

    def test_counts_es_slots(self):
        model = self._model({"slotmap_0_1_0": "ES1", "slotmap_0_2_0": "ES2"})
        assert _count_slotmap(model, "ES") == 2

    def test_bang_suffix_counted(self):
        model = self._model({"slotmap_1_1_0": "CS1!", "slotmap_1_2_0": "ES1!"})
        assert _count_slotmap(model, "CS") == 1
        assert _count_slotmap(model, "ES") == 1

    def test_empty_slotmap_returns_none(self):
        model = self._model({})
        assert _count_slotmap(model, "CS") is None
        assert _count_slotmap(model, "ES") is None

    def test_cs_does_not_count_es(self):
        model = self._model({"slotmap_0_0_0": "ES1"})
        assert _count_slotmap(model, "CS") is None

    def test_non_slot_values_ignored(self):
        model = self._model({"slotmap_0_0_0": "MAIN", "slotmap_0_1_0": "MM"})
        assert _count_slotmap(model, "CS") is None


class TestDerivedSlotColumns:
    """Tests for cartridge_slots and expansion_slots derive functions."""

    def _col(self, key):
        return next(c for c in COLUMNS if c.key == key)

    def test_cartridge_slots_derive_uses_slotmap(self):
        col = self._col("cartridge_slots")
        model = {f"slotmap_{ms}_{ss}_0": None for ms in range(4) for ss in range(4)}
        model["slotmap_1_0_0"] = "CS1"
        model["slotmap_2_0_0"] = "CS2"
        assert col.derive(model) == 2

    def test_cartridge_slots_fallback_to_scraped(self):
        col = self._col("cartridge_slots")
        model = {f"slotmap_{ms}_{ss}_0": None for ms in range(4) for ss in range(4)}
        model["scraped_cart_slots"] = 2
        assert col.derive(model) == 2

    def test_cartridge_slots_slotmap_beats_scraped(self):
        col = self._col("cartridge_slots")
        model = {f"slotmap_{ms}_{ss}_0": None for ms in range(4) for ss in range(4)}
        model["slotmap_1_0_0"] = "CS1"
        model["scraped_cart_slots"] = 3  # should be ignored
        assert col.derive(model) == 1

    def test_expansion_slots_derive(self):
        col = self._col("expansion_slots")
        model = {f"slotmap_{ms}_{ss}_0": None for ms in range(4) for ss in range(4)}
        model["slotmap_0_1_0"] = "ES1"
        assert col.derive(model) == 1

    def test_expansion_slots_no_fallback(self):
        col = self._col("expansion_slots")
        model = {f"slotmap_{ms}_{ss}_0": None for ms in range(4) for ss in range(4)}
        assert col.derive(model) is None

    def test_scraped_cart_slots_is_hidden(self):
        col = self._col("scraped_cart_slots")
        assert col.hidden is True

    def test_expansion_slots_in_media_group(self):
        col = self._col("expansion_slots")
        assert col.group == "media"
        assert col.id == 101
```

**Step 2: Run tests to verify they fail**

```
pytest tests/scraper/test_columns.py::TestCountSlotmap tests/scraper/test_columns.py::TestDerivedSlotColumns -v
```

Expected: FAIL — `_count_slotmap` not importable, `expansion_slots` not in COLUMNS

**Step 3: Implement**

Add to `scraper/columns.py`, after the imports and before `@dataclass class Group`:

```python
import re

_SLOTMAP_ABBR_RE = re.compile(r"^(CS|ES)\d+!?$")


def _count_slotmap(model: dict, kind: str) -> int | None:
    """Count distinct sub-slots in the merged slotmap whose page-0 cell is kind+N[!].

    ``kind`` is either ``"CS"`` (cartridge) or ``"ES"`` (expansion).
    Returns the integer count, or ``None`` when no matching sub-slot is found.
    """
    count = 0
    for ms in range(4):
        for ss in range(4):
            v = model.get(f"slotmap_{ms}_{ss}_0") or ""
            if _SLOTMAP_ABBR_RE.match(v) and v.startswith(kind):
                count += 1
    return count if count else None
```

Then in the `COLUMNS` list, make these changes:

1. Replace the `cartridge_slots` (id=19) entry:

```python
    Column(id=19, key="cartridge_slots",  label="Cartridge Slots",      group="media",    type="number", short_label="Cart Slots",   tooltip="Cartridge Slots",
           derive=lambda m: _count_slotmap(m, "CS") or m.get("scraped_cart_slots")),
```

2. After the `cartridge_slots` line, add the new `expansion_slots` column and the hidden `scraped_cart_slots` column:

```python
    Column(id=101, key="expansion_slots", label="Expansion Slots",      group="media",    type="number", short_label="Exp Slots",    tooltip="Expansion Slots",
           derive=lambda m: _count_slotmap(m, "ES")),
    Column(id=20, key="tape_interface",   label="Tape Interface",       group="media",    type="string", short_label="Tape I/F",     tooltip="Tape Interface"),
```

And add the hidden column anywhere after the media section (before the slotmap block is fine):

```python
    # Hidden scraper inputs (not shipped to browser; available to derive functions)
    Column(id=102, key="scraped_cart_slots", label="Scraped Cart Slots", group="media", type="number", hidden=True),
```

> **Note:** Remove the existing `Column(id=20, key="tape_interface" ...)` line from its current position to avoid a duplicate — it moves to sit after `expansion_slots`.

**Step 4: Run tests to verify they pass**

```
pytest tests/scraper/test_columns.py::TestCountSlotmap tests/scraper/test_columns.py::TestDerivedSlotColumns -v
```

Expected: all PASS

**Step 5: Run full columns test suite**

```
pytest tests/scraper/test_columns.py -v
```

Expected: all tests pass

**Step 6: Commit**

```bash
git add scraper/columns.py tests/scraper/test_columns.py
git commit -m "feat(columns): add expansion_slots (id=101); derive both slot counts from slotmap"
```

---

### Task 5: Run full test suite and rebuild data

**Step 1: Run all scraper tests**

```
pytest tests/scraper/ -v
```

Expected: all tests pass. Fix any failures before continuing.

**Step 2: Rebuild data.js**

```
python -m scraper build
```

Expected: build completes without errors. Check that the output `docs/data.js` includes `expansion_slots` values for models with ES* slots.

**Step 3: Spot-check the output**

```bash
python -c "
import json, re
src = open('docs/data.js').read()
data = json.loads(re.search(r'window\.MSX_DATA\s*=\s*(\{.*\})', src, re.DOTALL).group(1))
cols = {c['key']: c for c in data['columns']}
print('expansion_slots col:', cols.get('expansion_slots'))
print('scraped_cart_slots in cols:', 'scraped_cart_slots' in cols)
# Show a few models with expansion slots
for m in data['models']:
    idx = next(i for i,c in enumerate(data['columns']) if c['key'] == 'expansion_slots')
    if m['values'][idx]:
        print(m['values'][0], m['values'][1], 'exp_slots=', m['values'][idx])
"
```

Expected:
- `expansion_slots` column present
- `scraped_cart_slots` NOT in columns (it is hidden)
- Some models show expansion slot counts

**Step 4: Commit the rebuilt data**

```bash
git add docs/data.js docs/bundle.js
git commit -m "data: rebuild — add expansion_slots column; slot counts from slotmap"
```

---

### Task 6: Update the product backlog

**Files:**
- Modify: `.claude/artifacts/planning/product-backlog.md`

Move the feature to "In product (shipped)" and update "Now / Next".

**Step 1: Edit backlog**

In `.claude/artifacts/planning/product-backlog.md`:

- Remove the current "Now / Next" entry (if any relates to this feature)
- Add to the "In product (shipped)" section:

```markdown
  - Expansion Slots column (id=101, Media group)
    - Derived from final slotmap ES* count; no scraped fallback
  - Cart Slots (id=19) now derived from final slotmap CS* count
    - Fallback to scraped_cart_slots (hidden, from msx.org/openMSX parsers) when no slotmap
```

**Step 2: Commit**

```bash
git add .claude/artifacts/planning/product-backlog.md
git commit -m "docs(backlog): mark expansion_slots + slotmap-derived cart slots as shipped"
```

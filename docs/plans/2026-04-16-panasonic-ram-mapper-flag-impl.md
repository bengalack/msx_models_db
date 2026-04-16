# PanasonicRAM Implies Memory Mapper — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When a machine XML contains `<PanasonicRAM>`, set `mapper = "Yes"` in the parsed output, because PanasonicRAM is a proprietary implementation of the standard MSX memory mapper interface.

**Architecture:** Single guard added to `_extract_memory` in `scraper/openmsx.py` — after the PanasonicRAM size loop, check whether any PanasonicRAM elements were found and whether `mapper` is not yet set, then assign `"Yes"`. No other files in the scraper pipeline need changing; the value flows through merge/build unchanged.

**Tech Stack:** Python 3, lxml (via `devices.iter()`), pytest

---

### Task 1: Update technical design doc

**Files:**
- Modify: `.claude/artifacts/planning/technical-design.md`

**Step 1: Find the memory extraction section**

Open `.claude/artifacts/planning/technical-design.md` and locate the paragraph that describes how `<MemoryMapper>`, `<PanasonicRAM>`, and plain `<RAM>` elements are handled (search for `PanasonicRAM`).

**Step 2: Add the new rule**

In that section, add the following bullet alongside the existing RAM rules:

```
- `<PanasonicRAM>` present → `mapper = "Yes"` (proprietary implementation of the standard MSX memory mapper interface; takes precedence over plain `<RAM>`)
```

**Step 3: Commit**

```bash
git add .claude/artifacts/planning/technical-design.md
git commit -m "docs(technical-design): document PanasonicRAM implies mapper=Yes rule"
```

---

### Task 2: Add failing tests

**Files:**
- Modify: `tests/scraper/test_openmsx.py`

**Step 1: Update existing `test_panasonic_ram` to assert mapper**

Find `test_panasonic_ram` (currently only asserts `main_ram_kb`). Add the mapper assertion:

```python
def test_panasonic_ram(self):
    xml = _xml(_info(msx_type="MSXturboR"),
               '<PanasonicRAM id="Main RAM"><size>256</size></PanasonicRAM>')
    result = parse_machine_xml(xml, "test.xml")
    assert result["main_ram_kb"] == 256
    assert result["mapper"] == "Yes"
```

**Step 2: Add new test for PanasonicRAM + MemoryMapper coexistence**

Add directly after `test_panasonic_ram`:

```python
def test_panasonic_ram_with_memory_mapper_does_not_duplicate(self):
    xml = _xml(
        _info(msx_type="MSXturboR"),
        '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>'
        '<PanasonicRAM id="Extra RAM"><size>256</size></PanasonicRAM>',
    )
    result = parse_machine_xml(xml, "test.xml")
    assert result["mapper"] == "Yes"
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/scraper/test_openmsx.py::TestMemory::test_panasonic_ram -v
pytest tests/scraper/test_openmsx.py::TestMemory::test_panasonic_ram_with_memory_mapper_does_not_duplicate -v
```

Expected: `test_panasonic_ram` FAILS (`KeyError: 'mapper'`), new test PASSES (MemoryMapper already sets `"Yes"` — confirms no regression).

---

### Task 3: Implement the rule

**Files:**
- Modify: `scraper/openmsx.py:224-230`

**Step 1: Track PanasonicRAM presence and set mapper**

Replace the PanasonicRAM loop block (lines 224–230):

```python
# PanasonicRAM is used by turbo R and some MSX2+ machines.
# It is a proprietary implementation of the standard MSX memory mapper interface.
panasonic_ram_found = False
for pram in devices.iter("PanasonicRAM"):
    size = _int(pram.find("size"))
    if size:
        total_ram += size
    panasonic_ram_found = True
if panasonic_ram_found and "mapper" not in out:
    out["mapper"] = "Yes"
if total_ram:
    out["main_ram_kb"] = total_ram
```

**Step 2: Run tests to verify they pass**

```bash
pytest tests/scraper/test_openmsx.py::TestMemory -v
```

Expected: all memory tests PASS.

**Step 3: Run full test suite**

```bash
pytest tests/scraper/test_openmsx.py -v
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add scraper/openmsx.py tests/scraper/test_openmsx.py
git commit -m "feat: PanasonicRAM implies mapper=Yes in memory extraction"
```

# OpenMSX ID Link + Smart Tooltip Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a clickable GitHub link and smart tooltip to the `openMSX Machine ID` column, mirroring the existing behaviour of the `Model` column.

**Architecture:** Mark `openmsx_id` as `linkable=True, truncate_limit=20` in `scraper/columns.py`; extend the links loop in `scraper/build.py` to emit a GitHub URL; no frontend changes needed — `grid.ts` already handles any `linkable` column generically.

**Tech Stack:** Python 3.11 (scraper), TypeScript + Vitest (web), pytest (scraper tests)

---

### Task 1: Scraper test — openmsx_id link generation

**Design reference:** `.claude/artifacts/planning/2026-04-18-openmsx-id-link-design.md`

**Files:**
- Modify: `tests/scraper/test_build.py`

**Step 1: Write the failing tests**

Add a new class at the bottom of `tests/scraper/test_build.py`:

```python
class TestOpenMSXIdLink:
    """Build emits correct GitHub link for openmsx_id column."""

    def _run_build(self, tmp_path, openmsx_data, msxorg_data=None):
        import re as _re
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path  = tmp_path / "msxorg.json"
        output_path  = tmp_path / "data.js"
        openmsx_path.write_text(json.dumps(openmsx_data))
        msxorg_path.write_text(json.dumps(msxorg_data or []))
        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=tmp_path / "reg.json",
            output_path=output_path,
        )
        content = output_path.read_text(encoding="utf-8")
        data = json.loads(
            _re.search(r"window\.MSX_DATA\s*=\s*(\{.*\})\s*;", content, _re.DOTALL).group(1)
        )
        return data

    def test_openmsx_id_column_is_linkable(self, tmp_path):
        """openmsx_id ColumnDef has linkable=true in data.js."""
        data = self._run_build(tmp_path, [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
             "openmsx_id": "Sony_HB-75P"},
        ])
        col = next(c for c in data["columns"] if c["key"] == "openmsx_id")
        assert col.get("linkable") is True

    def test_openmsx_id_column_has_truncate_limit_20(self, tmp_path):
        """openmsx_id ColumnDef has truncateLimit=20 in data.js."""
        data = self._run_build(tmp_path, [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
             "openmsx_id": "Sony_HB-75P"},
        ])
        col = next(c for c in data["columns"] if c["key"] == "openmsx_id")
        assert col.get("truncateLimit") == 20

    def test_openmsx_id_link_emitted_when_id_present(self, tmp_path):
        """Model record has links.openmsx_id set to the correct GitHub URL."""
        data = self._run_build(tmp_path, [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
             "openmsx_id": "Sony_HB-75P"},
        ])
        col_keys = [c["key"] for c in data["columns"]]
        mfr_idx = col_keys.index("manufacturer")
        mdl_idx = col_keys.index("model")
        sony = next(
            m for m in data["models"]
            if m["values"][mfr_idx] == "Sony" and m["values"][mdl_idx] == "HB-75P"
        )
        expected = "https://github.com/openMSX/openMSX/blob/master/share/machines/Sony_HB-75P.xml"
        assert sony.get("links", {}).get("openmsx_id") == expected

    def test_openmsx_id_link_absent_when_id_missing(self, tmp_path):
        """Model record has no links.openmsx_id when openmsx_id is null."""
        data = self._run_build(tmp_path, [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"},
        ])
        col_keys = [c["key"] for c in data["columns"]]
        mfr_idx = col_keys.index("manufacturer")
        mdl_idx = col_keys.index("model")
        sony = next(
            m for m in data["models"]
            if m["values"][mfr_idx] == "Sony" and m["values"][mdl_idx] == "HB-75P"
        )
        assert "openmsx_id" not in sony.get("links", {})

    def test_both_model_and_openmsx_id_links_coexist(self, tmp_path):
        """When both msxorg_title and openmsx_id are present, both links are emitted."""
        data = self._run_build(
            tmp_path,
            openmsx_data=[
                {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
                 "openmsx_id": "Sony_HB-75P"},
            ],
            msxorg_data=[
                {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
                 "msxorg_title": "Sony HB-75P"},
            ],
        )
        col_keys = [c["key"] for c in data["columns"]]
        mfr_idx = col_keys.index("manufacturer")
        mdl_idx = col_keys.index("model")
        sony = next(
            m for m in data["models"]
            if m["values"][mfr_idx] == "Sony" and m["values"][mdl_idx] == "HB-75P"
        )
        links = sony.get("links", {})
        assert "model" in links
        assert "openmsx_id" in links
```

**Step 2: Run tests to verify they fail**

```bash
cd c:/source/repos/msx_models_db
pytest tests/scraper/test_build.py::TestOpenMSXIdLink -v
```

Expected: all 5 tests FAIL (linkable/truncateLimit not set, no link emitted).

**Step 3: Implement — `scraper/columns.py`**

Find line 182 and add `linkable=True, truncate_limit=20`:

```python
# Before
Column(id=28, key="openmsx_id", label="openMSX Machine ID", group="emulation",
       type="string", short_label="openMSX ID", tooltip="openMSX Machine ID"),

# After
Column(id=28, key="openmsx_id", label="openMSX Machine ID", group="emulation",
       type="string", short_label="openMSX ID", tooltip="openMSX Machine ID",
       linkable=True, truncate_limit=20),
```

**Step 4: Implement — `scraper/build.py`**

In the links loop (around line 329–333), extend the `if` to also handle `openmsx_id`:

```python
# Before
        for col in active_cols:
            if col.linkable and col.key == "model":
                msxorg_title = model.get("msxorg_title")
                if msxorg_title:
                    links[col.key] = f"https://www.msx.org/wiki/{msxorg_title.replace(' ', '_')}"

# After
        for col in active_cols:
            if col.linkable and col.key == "model":
                msxorg_title = model.get("msxorg_title")
                if msxorg_title:
                    links[col.key] = f"https://www.msx.org/wiki/{msxorg_title.replace(' ', '_')}"
            elif col.linkable and col.key == "openmsx_id":
                oid = model.get("openmsx_id")
                if oid:
                    links[col.key] = f"https://github.com/openMSX/openMSX/blob/master/share/machines/{oid}.xml"
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/scraper/test_build.py::TestOpenMSXIdLink -v
```

Expected: all 5 PASS.

**Step 6: Run full scraper test suite to check for regressions**

```bash
pytest tests/scraper/ -v
```

Expected: all pass.

**Step 7: Commit**

```bash
cd c:/source/repos/msx_models_db
git add scraper/columns.py scraper/build.py tests/scraper/test_build.py
git commit -m "feat(emulation): add link and smart tooltip to openMSX Machine ID column"
```

---

### Task 2: Web test — openmsx_id link cell rendering

**Files:**
- Modify: `tests/web/cell-truncation.test.ts`

These tests use the existing `buildGrid()` infrastructure. No changes to `src/grid.ts` are needed — the frontend already handles any `linkable` column generically.

**Step 1: Write the tests**

Add a new describe block at the bottom of `tests/web/cell-truncation.test.ts`, after the last existing describe block. The `makeData` helper already supports `linkable` and `links` — create a separate helper for openmsx data:

```typescript
// ── openMSX ID link cell ─────────────────────────────────────────────────

describe('openmsx_id link cell', () => {
  const GITHUB_URL =
    'https://github.com/openMSX/openMSX/blob/master/share/machines/Panasonic_FS-A1WSX.xml';

  function makeOpenMSXData(overrides?: {
    openmsxId?: string;
    limit?: number;
    withUrl?: boolean;
  }): MSXData {
    const {
      openmsxId = 'Panasonic_FS-A1WSX',
      limit = 20,
      withUrl = true,
    } = overrides ?? {};

    return {
      version: 1,
      generated: '2026-04-18',
      groups: [{ id: 7, key: 'emulation', label: 'Emulation', order: 7 }],
      columns: [
        {
          id: 28,
          key: 'openmsx_id',
          label: 'openMSX Machine ID',
          shortLabel: 'openMSX ID',
          groupId: 7,
          type: 'string',
          linkable: true,
          ...(limit > 0 ? { truncateLimit: limit } : {}),
        },
      ],
      models: [
        {
          id: 1,
          values: [openmsxId],
          ...(withUrl ? { links: { openmsx_id: GITHUB_URL } } : {}),
        },
      ],
      slotmap_lut: {},
    };
  }

  it('renders as <a class="cell-link"> with the GitHub URL as href', () => {
    const wrap = getGrid(makeOpenMSXData());
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a).not.toBeNull();
    expect(a.href).toBe(GITHUB_URL);
  });

  it('opens in a new tab (target=_blank)', () => {
    const wrap = getGrid(makeOpenMSXData());
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.target).toBe('_blank');
  });

  it('sets a.title to "fullId \u2014 url" when ID exceeds truncate limit', () => {
    // 'Panasonic_FS-A1WSX' = 18 chars, limit = 16 → truncated
    const wrap = getGrid(makeOpenMSXData({ limit: 16 }));
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(`Panasonic_FS-A1WSX \u2014 ${GITHUB_URL}`);
  });

  it('clips the link text when ID exceeds truncate limit', () => {
    // limit=16 → first 15 chars + '…' = 'Panasonic_FS-A1…'
    const wrap = getGrid(makeOpenMSXData({ limit: 16 }));
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.textContent).toBe('Panasonic_FS-A1\u2026');
  });

  it('sets a.title to URL only when ID is at or below truncate limit', () => {
    // 'Sony_HB-75P' = 11 chars, limit = 20 → no truncation
    const wrap = getGrid(makeOpenMSXData({ openmsxId: 'Sony_HB-75P' }));
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(GITHUB_URL);
  });

  it('shows full ID text (no ellipsis) when at or below the limit', () => {
    const wrap = getGrid(makeOpenMSXData({ openmsxId: 'Sony_HB-75P' }));
    const td = getCell(wrap, 0)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.textContent).toBe('Sony_HB-75P');
  });

  it('mouseenter handler skips the openmsx_id link cell', () => {
    const wrap = getGrid(makeOpenMSXData());
    const td = getCell(wrap, 0)!;
    td.removeAttribute('title');
    fireMouseEnter(td);
    // Handler must skip link cells; td.title stays empty
    expect(td.title).toBe('');
  });

  it('renders as plain text (no <a>) when no link URL is available', () => {
    const wrap = getGrid(makeOpenMSXData({ withUrl: false }));
    const td = getCell(wrap, 0)!;
    expect(td.querySelector('a.cell-link')).toBeNull();
    expect(td.textContent).toContain('Panasonic_FS-A1WSX');
  });
});
```

**Step 2: Run tests to verify they pass**

These tests exercise the existing grid rendering path with a new column key — they should pass immediately because `grid.ts` handles `linkable` generically.

```bash
cd c:/source/repos/msx_models_db
npm test -- --run tests/web/cell-truncation.test.ts
```

Expected: all new tests PASS (plus all existing tests still pass).

**Step 3: Run full web test suite to check for regressions**

```bash
npm test -- --run
```

Expected: all pass.

**Step 4: Commit**

```bash
git add tests/web/cell-truncation.test.ts
git commit -m "test(web): add openmsx_id link and smart-tooltip tests"
```

---

### Task 3: Regenerate data.js

This applies the column config change to the actual output file.

**Step 1: Run the build**

```bash
python -m scraper build
```

Expected: completes without errors; `docs/data.js` is updated.

**Step 2: Verify the output**

```bash
grep -A5 '"openmsx_id"' docs/data.js | head -20
```

Expected output shows `"linkable": true` and `"truncateLimit": 20` in the `openmsx_id` column definition, and at least some model records with a `links` object containing an `openmsx_id` key.

**Step 3: Commit**

```bash
git add docs/data.js docs/bundle.js
git commit -m "chore(data): regenerate data.js with openmsx_id link support"
```

---

### Done

After Task 3 the user verifies by opening `docs/index.html` in a browser and confirming:
- OpenMSX Machine ID cells for known models render as hyperlinks
- Clicking opens the correct GitHub XML file in a new tab
- Long IDs show tooltip `"full id — url"`; short IDs show URL only

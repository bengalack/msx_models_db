# Design: Single-Source Column Configuration

## Date
2026-03-29

## Problem
Column definitions are spread across multiple files (`src/columns.ts`, `docs/data.js`, `data/id-registry.json`, scraper extraction code). Adding a column requires editing 4+ files. Removing or retiring a column has no clear process. There is no support for derived columns (computed from other column values).

## Design

### Single source of truth: `scraper/columns.py`

All column and group definitions live in one Python file. Everything else is generated from it.

```python
@dataclass
class Group:
    id: int
    key: str
    label: str
    order: int

@dataclass
class Column:
    id: int               # stable, permanent, never reused
    key: str              # matches scraper field key
    label: str            # display label
    group: str            # group key (resolved to groupId at build time)
    type: str             # "string" | "number" | "boolean"
    short_label: str | None = None
    tooltip: str | None = None
    linkable: bool = False
    hidden: bool = False    # scraped, available to derive, not in data.js
    retired: bool = False   # permanently removed, ID preserved, not in data.js
    derive: Callable[[dict[str, Any]], Any] | None = None
```

### Column categories

| Category | Scraped | In data.js | In grid | Use case |
|----------|---------|------------|---------|----------|
| Regular  | Yes     | Yes        | Yes     | Normal visible column |
| Derived  | No (computed) | Yes  | Yes     | Computed from other columns |
| Hidden   | Yes     | No         | No      | Input for derived columns |
| Retired  | No      | No         | No      | Removed post-release, ID preserved |

### Display order

Column order in the grid = order in the `COLUMNS` list. To reorder, move entries in the list. The `id` is stable and independent of position.

### Derived columns

A derived column has a `derive` callable that receives the full merged row dict (including hidden fields) and returns the computed value. Derivation runs during the build step; the result is stored in `data.js`. The derive function acts as a **fallback**: if the field already has a value (from scraping or a local override), the derive result is ignored. This ensures local overrides always take precedence.

```python
def derive_nmos_cmos(row: dict[str, Any]) -> str | None:
    vdp = row.get("vdp", "")
    if vdp and vdp.startswith("T97"):
        return "CMOS"
    return "NMOS" if vdp else None

Column(id=30, key="nmos_cmos", label="NMOS/CMOS", group="cpu", type="string",
       derive=derive_nmos_cmos)
```

### Validation rules (enforced at build time)

- No duplicate IDs or keys
- ID 0 never used (reserved sentinel for URL codec)
- Every column's `group` key exists in `GROUPS`
- A column cannot be both `hidden` and `retired`
- A `derive` column must have a callable; a non-derive column must not
- Retired columns must not have `derive`

### Build command

```
python -m scraper build              # merge cached data -> derive -> assign IDs -> write data.js
python -m scraper build --fetch      # fetch fresh data first, then build
```

Build pipeline steps:
1. Load cached raw data (`data/openmsx-raw.json`, `data/msxorg-raw.json`)
2. If `--fetch`: fetch fresh data from sources first
3. Merge sources
4. Derive: compute derived column values for each model
5. Assign model IDs via registry
6. Build output: generate `data.js` with groups, active columns, and model values
7. Atomic write `docs/data.js` and `data/id-registry.json`

### ID registry simplification

Column IDs are now defined explicitly in `columns.py`. The registry simplifies to model IDs only:

```json
{
  "version": 2,
  "models": { "sony|hb-75p": 1, ... },
  "retired_models": [],
  "next_model_id": 11
}
```

### Files deleted

- `src/columns.ts` — replaced by `scraper/columns.py`. Not imported by any runtime code; web page reads columns from `data.js`.

### Files unchanged

- `src/types.ts` — TypeScript interfaces stay for type-checking
- `src/grid.ts`, `src/main.ts`, `src/url/codec.ts` — already consume `window.MSX_DATA`
- Vite build — still bundles `src/` into `docs/bundle.js`

## Maintainer workflows

**Add a column:** Add one `Column(...)` entry to `columns.py`. If scraped, add extraction logic to `openmsx.py`/`msxorg.py`. Run `python -m scraper build`.

**Add a derived column:** Add a derive function and a `Column(...)` with `derive=fn`. Run `python -m scraper build`.

**Remove a column (pre-release):** Delete the entry from `COLUMNS`. Run build.

**Retire a column (post-release):** Set `retired=True`. Run build. ID is preserved.

**Reorder columns:** Move entries in the `COLUMNS` list. Run build.

**Rebuild after config change:** `python -m scraper build` (no fetch needed).

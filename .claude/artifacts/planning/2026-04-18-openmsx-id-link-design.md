# Feature Design: OpenMSX ID Column — Link and Smart Tooltip

## Metadata
- Date: 2026-04-18
- Author: bengalack

## Overview

The `openmsx_id` column gains the same link + smart-tooltip behaviour as the `model` column:
- Each cell links to the corresponding openMSX machine XML file on GitHub.
- A `truncate_limit=20` clips long IDs in the display; the tooltip shows `"full id — url"` when truncated, and just the URL when not.

No frontend code changes are required. The existing `linkable` + `links` architecture in `build.py` and `grid.ts` handles this generically once the column is marked `linkable`.

## Approach

Reuse the existing `linkable` / `links` architecture (same as `model` column):

1. Mark the column `linkable=True` and add `truncate_limit=20` in `scraper/columns.py`.
2. Extend the links loop in `scraper/build.py` to emit a GitHub URL when `openmsx_id` is present.
3. No changes to `src/grid.ts` or `src/types.ts` — they already handle any linkable column.

Rejected alternatives:
- **`link_template` field on `ColumnDef`**: more generalizable but YAGNI — only two linkable columns exist.
- **`link_fn` callable on `Column`**: flexible but adds complexity not needed here.

## URL Format

```
https://github.com/openMSX/openMSX/blob/master/share/machines/{openmsx_id}.xml
```

`openmsx_id` is the XML filename without the `.xml` suffix (e.g. `Panasonic_FS-A1ST`).

## Schema Changes

### `scraper/columns.py`

```python
# Before
Column(id=28, key="openmsx_id", label="openMSX Machine ID", group="emulation",
       type="string", short_label="openMSX ID", tooltip="openMSX Machine ID")

# After
Column(id=28, key="openmsx_id", label="openMSX Machine ID", group="emulation",
       type="string", short_label="openMSX ID", tooltip="openMSX Machine ID",
       linkable=True, truncate_limit=20)
```

### `scraper/build.py` — links loop

```python
# Extend to cover openmsx_id alongside the existing model key logic
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

## Data Flows Affected

| Path | Change |
|------|--------|
| `scraper/columns.py` | Add `linkable=True, truncate_limit=20` to `openmsx_id` column |
| `scraper/build.py` | Add `elif col.linkable and col.key == "openmsx_id"` branch in links loop |
| `src/grid.ts` | No change |
| `src/types.ts` | No change |
| `docs/data.js` | Regenerated: `openmsx_id` column gains `"linkable": true` and `"truncateLimit": 20`; model records with a non-null `openmsx_id` gain `links.openmsx_id` |

## Tests

### Web (Vitest) — `tests/web/cell-truncation.test.ts`

Add a new describe block `'openmsx_id link cell'`:
- Link renders as `<a class="cell-link">` with correct GitHub href
- `a.title` is `"full id — url"` when ID exceeds truncate limit
- `a.title` is URL-only when ID is at or below the limit
- mouseenter handler skips link cells (already tested generically, but verify with openmsx key)

### Scraper (pytest) — `tests/scraper/test_build.py`

- When `openmsx_id` is non-null, `model["links"]["openmsx_id"]` equals the expected GitHub URL
- When `openmsx_id` is null/absent, no `links.openmsx_id` key is emitted
- When both `model` and `openmsx_id` links are present, both appear in `links`

## Documentation Updates

- `product-requirements.md` — add acceptance criteria under "Cell value truncation" and a new bullet under the Emulation column descriptions noting `openmsx_id` is linkable
- `ux-design-guide.md` — note that two columns (`model`, `openmsx_id`) use the link + smart-tooltip pattern

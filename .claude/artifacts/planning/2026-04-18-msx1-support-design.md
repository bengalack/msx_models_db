# Design: MSX1 Support

## Metadata
- Date: 2026-04-18
- Branch: feature/msx1-support

## Overview

Extend the scraper to include MSX1 models alongside the existing MSX2, MSX2+, and turbo R models. No frontend changes are required — the grid already renders all rows from `data.js` regardless of generation.

## 1. Category listing with auto-pagination

### New category entry

Add `"MSX1"` to `CATEGORY_URLS` in `scraper/msxorg.py`:

```python
CATEGORY_URLS: dict[str, str] = {
    "MSX1":     f"{WIKI_URL}Category:MSX1_Computers",
    "MSX2":     f"{WIKI_URL}Category:MSX2_Computers",
    "MSX2+":    f"{WIKI_URL}Category:MSX2%2B_Computers",
    "turbo R":  f"{WIKI_URL}Category:MSX_turbo_R_Computers",
}
```

`GENERATION_RANK` already contains `"MSX1": 0` — no change needed.

Add `"MSX1"` to `SKIP_TITLES` to prevent the MSX1 overview article from being scraped as a model:

```python
SKIP_TITLES = {
    "MSX1", "MSX2", "MSX2+", "MSX turbo R",
}
```

### Automatic pagination

`list_model_pages` currently fetches exactly one page per category. After parsing each category page, detect MediaWiki's "next page" link in `#mw-pages`:

```html
<a href="/wiki/Category:MSX1_Computers?pagefrom=...">next 200</a>
```

If found, pass the full `href` URL back to `source.fetch_category` with `page=2`, `page=3`, etc. Continue until no next-page link is found or the source returns `None`. This applies to all categories (future-proof).

### `PageSource` protocol — `page` parameter

Add `page: int = 1` to `fetch_category` in the `PageSource` protocol and all implementations:

- **`LivePageSource`** — ignores `page`; uses the next-page URL verbatim (the MediaWiki `?pagefrom=...` URL is self-contained).
- **`MirrorPageSource`** — for `page == 1`, behaviour unchanged. For `page > 1`, derives the mirror filename by appending `_pageN` to the base slug before ` - MSX Wiki.html`:
  - Page 1: `Category_MSX1 Computers - MSX Wiki.html`
  - Page 2: `Category_MSX1 Computers_page2 - MSX Wiki.html`
  - Page N: `Category_MSX1 Computers_pageN - MSX Wiki.html`
  The slug is extracted from the base URL (stripping any `?pagefrom=...` query string before applying `slug_to_filename`).
- **`FallbackPageSource`** — passes `page` through to both delegates.

## 2. Data schema

`generation` is already a free-form string field. `"MSX1"` becomes a valid value with no schema changes. The existing ranking `MSX1 < MSX2 < MSX2+ < turbo R` in `GENERATION_RANK` already handles models appearing in multiple categories correctly.

## 3. PRD and UX doc changes

### product-requirements.md
- Remove `"MSX1 models (future iteration)"` from the Non-Goals section.
- Update the Problem Statement scope sentence to include MSX1.
- Update the **Grid display** acceptance criteria to include MSX1 in the in-scope generations.
- Update the **Scraper process** acceptance criteria to include MSX1.

### technical-design.md
- Update the scope references (Problem Statement, Scraper CLI component description) to include MSX1.

## 4. Tests

New test class in `tests/scraper/test_msxorg.py`:

| Test | What it verifies |
|------|-----------------|
| MSX1 category page → models have `generation == "MSX1"` | MSX1 entry in CATEGORY_URLS wired correctly |
| Page 1 has "next 200" link → page 2 is fetched, its models included | Pagination loop runs |
| Page 2 returns `None` → pagination stops gracefully | No infinite loop |
| MSX1 model in page 1, also in MSX2 page → `generation == "MSX2"` | Ranking still applies across pages |
| Mirror mode page 2 → reads `Category_MSX1 Computers_page2 - MSX Wiki.html` | Mirror filename convention |
| Mirror page 2 missing → warning logged, models from page 1 still returned | Graceful degradation |

## 5. No frontend changes

The grid renders all rows from `data.js` regardless of `generation`. No TypeScript, CSS, or URL codec changes are needed.

## Data flows affected

| File | Change |
|------|--------|
| `scraper/msxorg.py` | Add `"MSX1"` to `CATEGORY_URLS` and `SKIP_TITLES`; add pagination loop in `list_model_pages`; add `page: int = 1` to `PageSource.fetch_category` calls |
| `scraper/mirror.py` | Add `page: int = 1` to `PageSource` protocol and all implementations; implement `_pageN` filename logic in `MirrorPageSource.fetch_category` |
| `tests/scraper/test_msxorg.py` | New pagination + MSX1 test class |
| `.claude/artifacts/planning/product-requirements.md` | Remove MSX1 from Non-Goals; add to scope in Goals, Grid display, Scraper process |
| `.claude/artifacts/planning/technical-design.md` | Update scope references to include MSX1 |

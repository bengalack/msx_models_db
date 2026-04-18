# MSX1 Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add MSX1 models to the scraper output alongside MSX2/MSX2+/turbo R, with automatic multi-page category pagination.

**Architecture:** Add `"MSX1"` to `CATEGORY_URLS` and `SKIP_TITLES`; add a pagination loop to `list_model_pages` that follows MediaWiki's "next 200" link; extend the `PageSource.fetch_category` signature with `page: int = 1` so `MirrorPageSource` can resolve the `_pageN` filename convention. No frontend changes needed.

**Tech Stack:** Python 3.11, pytest, BeautifulSoup4/lxml, existing `scraper/msxorg.py` and `scraper/mirror.py`.

---

### Task 1: Update PRD and technical design docs

**Files:**
- Modify: `.claude/artifacts/planning/product-requirements.md`
- Modify: `.claude/artifacts/planning/technical-design.md`

**Step 1: Remove MSX1 from Non-Goals in PRD**

In `product-requirements.md`, remove this line from the Non-Goals section:
```
- MSX1 models (future iteration).
```

**Step 2: Update scope references in PRD**

- Problem Statement sentence: change `"MSX2, MSX2+, and MSX turbo R models"` → `"MSX1, MSX2, MSX2+, and MSX turbo R models"`.
- **Grid display** acceptance criteria first bullet: add `"All MSX1,"` before `"MSX2,"`.
- **Scraper process** acceptance criteria: change `"It scrapes MSX2, MSX2+, and MSX turbo R model pages"` → `"It scrapes MSX1, MSX2, MSX2+, and MSX turbo R model pages"`.

**Step 3: Update technical design**

In `technical-design.md`, update the two scope references in the Scraper CLI component and Scraper build flow descriptions to include MSX1 alongside MSX2/MSX2+/turbo R.

**Step 4: Commit**

```bash
rtk git add .claude/artifacts/planning/product-requirements.md .claude/artifacts/planning/technical-design.md
rtk git commit -m "docs: add MSX1 to scope in PRD and technical design"
```

---

### Task 2: Add `page` parameter to `PageSource` protocol and all implementations

**Files:**
- Modify: `scraper/mirror.py`

**Step 1: Write the failing test**

In `tests/scraper/test_mirror.py`, add at the end:

```python
class TestMirrorPageSourcePagination:
    """MirrorPageSource.fetch_category resolves _pageN filenames for page > 1."""

    def test_page1_reads_standard_filename(self, tmp_path):
        content = b"<html><body></body></html>"
        (tmp_path / "Category_MSX1 Computers - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers",
            page=1,
        )
        assert result == content

    def test_page2_reads_page2_filename(self, tmp_path):
        content = b"<html><body>page2</body></html>"
        (tmp_path / "Category_MSX1 Computers_page2 - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        # URL is the live pagefrom URL — mirror strips query string
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=Sony+HX-10",
            page=2,
        )
        assert result == content

    def test_page3_reads_page3_filename(self, tmp_path):
        content = b"<html><body>page3</body></html>"
        (tmp_path / "Category_MSX1 Computers_page3 - MSX Wiki.html").write_bytes(content)
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=Z",
            page=3,
        )
        assert result == content

    def test_page2_missing_returns_none(self, tmp_path):
        source = MirrorPageSource(tmp_path)
        result = source.fetch_category(
            "MSX1",
            "https://www.msx.org/wiki/Category:MSX1_Computers?pagefrom=X",
            page=2,
        )
        assert result is None
```

**Step 2: Run to verify they fail**

```bash
pytest tests/scraper/test_mirror.py::TestMirrorPageSourcePagination -v
```
Expected: `FAILED` — `fetch_category()` doesn't accept `page` yet.

**Step 3: Implement `page` parameter in `scraper/mirror.py`**

Update the `PageSource` protocol signature:
```python
def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
```

Update `LivePageSource.fetch_category` (add `page: int = 1`, ignore it):
```python
def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
    try:
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception:
        log.exception(
            "Failed to fetch category page for %s (%s) — skipping", standard, url
        )
        return None
```

Update `MirrorPageSource.fetch_category`:
```python
def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
    if page == 1:
        filename = slug_to_filename(url)
    else:
        # Strip query string, derive base filename, insert _pageN suffix
        base_url = url.split("?")[0]
        base_filename = slug_to_filename(base_url)
        stem = base_filename[: -len(" - MSX Wiki.html")]
        filename = f"{stem}_page{page} - MSX Wiki.html"
    return self._read(filename, f"category {standard!r} page {page}")
```

Update `FallbackPageSource.fetch_category`:
```python
def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
    content = self._live.fetch_category(standard, url, page=page)
    if content is not None:
        return content
    log.info("Live fetch failed for category %r page %d — falling back to mirror", standard, page)
    return self._mirror.fetch_category(standard, url, page=page)
```

**Step 4: Run to verify they pass**

```bash
pytest tests/scraper/test_mirror.py::TestMirrorPageSourcePagination -v
```
Expected: all 4 PASS.

**Step 5: Run full mirror test suite to check no regressions**

```bash
pytest tests/scraper/test_mirror.py -v
```
Expected: all PASS.

**Step 6: Commit**

```bash
rtk git add scraper/mirror.py tests/scraper/test_mirror.py
rtk git commit -m "feat: add page parameter to PageSource.fetch_category for pagination support"
```

---

### Task 3: Add MSX1 category and pagination loop to `msxorg.py`

**Files:**
- Modify: `scraper/msxorg.py`
- Modify: `tests/scraper/test_msxorg.py`

**Step 1: Write the failing tests**

At the top of `tests/scraper/test_msxorg.py`, update `_StubSource` to accept `page`:
```python
class _StubSource:
    """Minimal PageSource stub for testing list_model_pages."""

    def __init__(self, category_results: list[bytes | None]):
        self._cats = iter(category_results)

    def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
        return next(self._cats, None)

    def fetch_page(self, title: str, url: str) -> bytes | None:  # pragma: no cover
        return None
```

Add a new `_PagedStubSource` class (after `_StubSource`):
```python
class _PagedStubSource:
    """PageSource stub that serves content keyed by (standard, page)."""

    def __init__(self, pages: dict[tuple[str, int], bytes | None]) -> None:
        self._pages = pages

    def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
        return self._pages.get((standard, page))

    def fetch_page(self, title: str, url: str) -> bytes | None:  # pragma: no cover
        return None
```

Add the new test classes at the end of the file:

```python
# ---------------------------------------------------------------------------
# MSX1 generation support
# ---------------------------------------------------------------------------

_EMPTY_CAT = b"<html><body><div id='mw-pages'></div></body></html>"

_MSX1_CAT_WITH_MODEL = (
    b"<html><body>"
    b'<div id="mw-pages">'
    b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
    b"</div></body></html>"
)

_MSX2_CAT_WITH_SAME_MODEL = (
    b"<html><body>"
    b'<div id="mw-pages">'
    b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
    b"</div></body></html>"
)


class TestMSX1Generation:
    def test_msx1_model_gets_msx1_generation(self):
        source = _PagedStubSource({
            ("MSX2", 1): _EMPTY_CAT,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _MSX1_CAT_WITH_MODEL,
        })
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX1"

    def test_msx1_model_also_in_msx2_gets_msx2(self):
        source = _PagedStubSource({
            ("MSX2", 1): _MSX2_CAT_WITH_SAME_MODEL,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _MSX1_CAT_WITH_MODEL,
        })
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX2"

    def test_msx1_overview_title_is_skipped(self):
        """The 'MSX1' overview article must not appear as a model."""
        cat = (
            b"<html><body><div id='mw-pages'>"
            b'<a href="/wiki/MSX1" title="MSX1">MSX1</a>'
            b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
            b"</div></body></html>"
        )
        source = _PagedStubSource({
            ("MSX2", 1): _EMPTY_CAT,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): cat,
        })
        pages = list_model_pages(source, delay=0)
        assert all(p["title"] != "MSX1" for p in pages)


# ---------------------------------------------------------------------------
# Pagination — following "next 200" links
# ---------------------------------------------------------------------------

_PAGE1_WITH_NEXT = (
    b"<html><body>"
    b'<div id="mw-pages">'
    b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
    b'<a href="/wiki/Category:MSX1_Computers?pagefrom=Sony+HX-10#mw-pages">next 200</a>'
    b"</div></body></html>"
)

_PAGE2_NO_NEXT = (
    b"<html><body>"
    b'<div id="mw-pages">'
    b'<a href="/wiki/Sony_HX-10" title="Sony HX-10">Sony HX-10</a>'
    b"</div></body></html>"
)


class TestListModelPagesPagination:
    def test_follows_next_page_link_collects_both_pages(self):
        source = _PagedStubSource({
            ("MSX2", 1): _EMPTY_CAT,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _PAGE1_WITH_NEXT,
            ("MSX1", 2): _PAGE2_NO_NEXT,
        })
        pages = list_model_pages(source, delay=0)
        titles = [p["title"] for p in pages]
        assert "Sony HB-75P" in titles
        assert "Sony HX-10" in titles

    def test_pagination_stops_when_page2_returns_none(self):
        source = _PagedStubSource({
            ("MSX2", 1): _EMPTY_CAT,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _PAGE1_WITH_NEXT,
            # MSX1 page 2 absent → None → stop
        })
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["title"] == "Sony HB-75P"

    def test_pagination_stops_when_no_next_link(self):
        source = _PagedStubSource({
            ("MSX2", 1): _EMPTY_CAT,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _PAGE2_NO_NEXT,  # no next link
        })
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1

    def test_deduplication_across_pages_keeps_highest_generation(self):
        """A model on MSX1 page 2 that also appears in MSX2 gets MSX2."""
        msx2_with_hx10 = (
            b"<html><body><div id='mw-pages'>"
            b'<a href="/wiki/Sony_HX-10" title="Sony HX-10">Sony HX-10</a>'
            b"</div></body></html>"
        )
        source = _PagedStubSource({
            ("MSX2", 1): msx2_with_hx10,
            ("MSX2+", 1): _EMPTY_CAT,
            ("turbo R", 1): _EMPTY_CAT,
            ("MSX1", 1): _PAGE1_WITH_NEXT,
            ("MSX1", 2): _PAGE2_NO_NEXT,  # Sony HX-10 also here as MSX1
        })
        pages = list_model_pages(source, delay=0)
        hx10 = next(p for p in pages if p["title"] == "Sony HX-10")
        assert hx10["standard"] == "MSX2"
```

**Step 2: Run to verify they fail**

```bash
pytest tests/scraper/test_msxorg.py::TestMSX1Generation tests/scraper/test_msxorg.py::TestListModelPagesPagination -v
```
Expected: FAILED — `MSX1` not in `CATEGORY_URLS`, no pagination, `page` param not accepted.

**Step 3: Implement in `scraper/msxorg.py`**

Add `"MSX1"` to `SKIP_TITLES`:
```python
SKIP_TITLES = {
    "MSX1", "MSX2", "MSX2+", "MSX turbo R",
}
```

Add `"MSX1"` to `CATEGORY_URLS` (last, so existing sequential `_StubSource` tests are unaffected):
```python
CATEGORY_URLS: dict[str, str] = {
    "MSX2":     f"{WIKI_URL}Category:MSX2_Computers",
    "MSX2+":    f"{WIKI_URL}Category:MSX2%2B_Computers",
    "turbo R":  f"{WIKI_URL}Category:MSX_turbo_R_Computers",
    "MSX1":     f"{WIKI_URL}Category:MSX1_Computers",
}
```

Add helper function (after `SKIP_TITLES`, before `_RE_KB`):
```python
def _find_next_page_url(soup: BeautifulSoup) -> str | None:
    """Return the MediaWiki 'next N' pagination URL from a category page, or None."""
    mw_pages = soup.find(id="mw-pages")
    if not mw_pages:
        return None
    for a in mw_pages.find_all("a"):
        href = a.get("href", "")
        if "next" in _text_content(a).lower() and "pagefrom=" in href:
            return urljoin(BASE_URL, href)
    return None
```

Replace the body of `list_model_pages` with a paginated version:
```python
def list_model_pages(
    source: PageSource,
    *,
    delay: float = 0.5,
) -> list[dict[str, str]]:
    """Enumerate all model page URLs from the category pages.

    Returns list of {title, url, standard}.
    """
    url_to_entry: dict[str, dict[str, str]] = {}

    for standard, cat_url in CATEGORY_URLS.items():
        current_url = cat_url
        page_num = 1
        while True:
            log.info("Fetching category page for %s (page %d)…", standard, page_num)
            content = source.fetch_category(standard, current_url, page=page_num)
            if content is None:
                break
            soup = BeautifulSoup(content, "lxml")

            for a_tag in soup.select("#mw-pages a, .mw-category a"):
                href = a_tag.get("href", "")
                title = a_tag.get("title", "") or _text_content(a_tag)
                if not href or not title:
                    continue
                if "/wiki/Category:" in href or "/wiki/Special:" in href:
                    continue
                if title in SKIP_TITLES:
                    continue
                full_url = urljoin(BASE_URL, href)
                if full_url in url_to_entry:
                    entry = url_to_entry[full_url]
                    if GENERATION_RANK.get(standard, -1) > GENERATION_RANK.get(entry["standard"], -1):
                        entry["standard"] = standard
                    continue
                url_to_entry[full_url] = {
                    "title": title,
                    "url": full_url,
                    "standard": standard,
                }

            next_url = _find_next_page_url(soup)
            if next_url is None:
                break
            current_url = next_url
            page_num += 1
            if delay:
                time.sleep(delay)

        if delay:
            time.sleep(delay)

    models = list(url_to_entry.values())
    log.info("Found %d model pages across all categories", len(models))
    return models
```

**Step 4: Run new tests to verify they pass**

```bash
pytest tests/scraper/test_msxorg.py::TestMSX1Generation tests/scraper/test_msxorg.py::TestListModelPagesPagination -v
```
Expected: all PASS.

**Step 5: Run full msxorg test suite to check no regressions**

```bash
pytest tests/scraper/test_msxorg.py -v
```
Expected: all PASS.

**Step 6: Run full scraper test suite**

```bash
pytest tests/scraper/ -v
```
Expected: all PASS.

**Step 7: Commit**

```bash
rtk git add scraper/msxorg.py tests/scraper/test_msxorg.py
rtk git commit -m "feat: add MSX1 category and auto-pagination to msxorg scraper"
```

---

### Task 4: Smoke-test with local mirror

This task is manual — run the scraper against the local mirror and verify MSX1 models appear.

**Step 1: Run the scraper in build mode with mirror**

```bash
python -m scraper build --local-msxorg-only --local-openmsx-only
```

Check the log output:
- Should see `"Fetching category page for MSX1 (page 1)…"`
- Should see `"Fetching category page for MSX1 (page 2)…"` (because local mirror has page 2)
- Should see MSX1 models in the final count

**Step 2: Verify MSX1 models appear in output**

```bash
python -c "
import json, re
with open('docs/data.js') as f:
    js = f.read()
match = re.search(r'window\.MSX_DATA\s*=\s*({.*})', js, re.DOTALL)
data = json.loads(match.group(1))
models = data['models']
# Find generation column index
gen_col = next(i for i, c in enumerate(data['columns']) if c['key'] == 'generation')
msx1 = [m for m in models if m['values'][gen_col] == 'MSX1']
print(f'MSX1 models: {len(msx1)}')
for m in msx1[:5]:
    print(m['values'][:3])
"
```
Expected: nonzero count of MSX1 models printed.

**Step 3: Do NOT commit — user will test first**

(No commit step — per instructions, let the user verify before committing.)

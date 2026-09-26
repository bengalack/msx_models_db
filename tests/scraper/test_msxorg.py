"""Unit tests for scraper/msxorg.py — graceful error handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scraper.mirror import MirrorPageSource
from scraper.msxorg import _parse_vdp, _parse_connections, fetch_all, list_model_pages, parse_model_page
from bs4 import BeautifulSoup


_GOOD_CATEGORY_HTML = (
    b"<html><body>"
    b'<div id="mw-pages"><a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a></div>'
    b"</body></html>"
)

_GOOD_MODEL_HTML = b"""
<html><body>
<table class="wikitable">
  <tr><th>Brand</th><td>Sony</td></tr>
  <tr><th>Model</th><td>HB-75P</td></tr>
  <tr><th>Year</th><td>1985</td></tr>
  <tr><th>Region</th><td>Europe</td></tr>
</table>
</body></html>
"""


class _StubSource:
    """Minimal PageSource stub for testing list_model_pages."""

    def __init__(self, category_results: list[bytes | None]):
        self._cats = iter(category_results)

    def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
        return next(self._cats, None)

    def fetch_page(self, title: str, url: str) -> bytes | None:  # pragma: no cover
        return None


class _PagedStubSource:
    """PageSource stub that serves content keyed by (standard, page)."""

    def __init__(self, pages: dict[tuple[str, int], bytes | None]) -> None:
        self._pages = pages

    def fetch_category(self, standard: str, url: str, page: int = 1) -> bytes | None:
        return self._pages.get((standard, page))

    def fetch_page(self, title: str, url: str) -> bytes | None:  # pragma: no cover
        return None


# ---------------------------------------------------------------------------
# _parse_vdp — pick highest when multiple VDPs listed
# ---------------------------------------------------------------------------

class TestParseVdp:
    def test_single_v9938(self):
        assert _parse_vdp("Yamaha V9938") == "V9938"

    def test_single_v9958(self):
        assert _parse_vdp("Yamaha V9958") == "V9958"

    def test_multiple_picks_highest(self):
        assert _parse_vdp("V9938 / V9958") == "V9958"

    def test_multiple_reversed_order_still_picks_highest(self):
        assert _parse_vdp("V9958 / V9938") == "V9958"

    def test_tms_is_lowest(self):
        assert _parse_vdp("TMS9918A / V9938") == "V9938"

    def test_no_match_returns_none(self):
        assert _parse_vdp("no vdp here") is None

    @pytest.mark.parametrize("raw,expected", [
        ("Texas Instruments TMS9118NL", "TMS9118"),   # NL = package suffix, not part of the chip
        ("Texas Instruments TMS9128NL", "TMS9128"),
        ("Texas Instruments TMS9129NL", "TMS9129"),
        ("Texas Instruments TMS9129A", "TMS9129A"),
        ("Texas Instruments TMS-9118NL", "TMS9118"),  # hyphenated spelling
        ("Texas Instruments  TMS9118NL", "TMS9118"),
        ("TMS9918ANL", "TMS9918A"),
        ("Toshiba T6950", "T6950"),
        ("Toshiba T6950A", "T6950A"),
        ("Yamaha YM2220", "YM2220"),
    ])
    def test_ti_91xx_family_toshiba_and_yamaha_clones(self, raw, expected):
        assert _parse_vdp(raw) == expected

    @pytest.mark.parametrize("raw", ["probably Toshiba T6950", "? Toshiba T6950"])
    def test_uncertainty_prefix_still_finds_the_chip(self, raw):
        assert _parse_vdp(raw) == "T6950"

    def test_clone_ranks_below_v9938(self):
        assert _parse_vdp("TMS9129 / V9938") == "V9938"


# ---------------------------------------------------------------------------
# list_model_pages — pick highest generation for multi-category models
# ---------------------------------------------------------------------------

class TestListModelPagesHighestGeneration:
    """A model in multiple categories gets the highest generation standard."""

    _MSX2_CAT = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/1chipMSX" title="1chipMSX">1chipMSX</a>'
        b"</div></body></html>"
    )
    _MSX2PLUS_CAT = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/1chipMSX" title="1chipMSX">1chipMSX</a>'
        b"</div></body></html>"
    )
    _EMPTY_CAT = b"<html><body><div id='mw-pages'></div></body></html>"

    def test_model_in_both_msx2_and_msx2plus_gets_msx2plus(self):
        # MSX2 category first, then MSX2+ — model should end up as MSX2+
        source = _StubSource([self._MSX2_CAT, self._MSX2PLUS_CAT, self._EMPTY_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX2+"

    def test_model_only_in_msx2_stays_msx2(self):
        source = _StubSource([self._MSX2_CAT, self._EMPTY_CAT, self._EMPTY_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "MSX2"

    def test_model_only_in_turbor_gets_turbor(self):
        source = _StubSource([self._EMPTY_CAT, self._EMPTY_CAT, self._MSX2_CAT])
        pages = list_model_pages(source, delay=0)
        assert len(pages) == 1
        assert pages[0]["standard"] == "turbo R"


# ---------------------------------------------------------------------------
# parse_model_page — split combined models on " / "
# ---------------------------------------------------------------------------

class TestParseModelPageSplit:
    """Model field with ' / ' produces one entry per variant."""

    _COMBINED_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sakhr</td></tr>
      <tr><th>Model</th><td>AX-350II / AX-350IIF</td></tr>
      <tr><th>Year</th><td>1987</td></tr>
    </table></body></html>
    """
    _SINGLE_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sony</td></tr>
      <tr><th>Model</th><td>HB-75P</td></tr>
    </table></body></html>
    """

    def test_combined_model_splits_into_two(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert len(results) == 2
        assert results[0]["model"] == "AX-350II"
        assert results[1]["model"] == "AX-350IIF"

    def test_split_entries_share_manufacturer(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert all(r["manufacturer"] == "Sakhr" for r in results)

    def test_split_entries_share_fields(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert all(r["year"] == 1987 for r in results)
        assert all(r["generation"] == "MSX2" for r in results)

    def test_single_model_returns_one_entry(self):
        results = parse_model_page(self._SINGLE_HTML, "MSX2", "Sony HB-75P")
        assert len(results) == 1
        assert results[0]["model"] == "HB-75P"

    def test_triple_split(self):
        html = b"""
        <html><body><table class="wikitable">
          <tr><th>Brand</th><td>Sanyo</td></tr>
          <tr><th>Model</th><td>PHC-23J / PHC-23J(B) / PHC-23(GR)</td></tr>
        </table></body></html>
        """
        results = parse_model_page(html, "MSX2", "Sanyo PHC-23J")
        assert len(results) == 3
        assert [r["model"] for r in results] == ["PHC-23J", "PHC-23J(B)", "PHC-23(GR)"]

    def test_no_specs_table_returns_empty(self):
        html = b"<html><body><p>No table here.</p></body></html>"
        results = parse_model_page(html, "MSX2", "Missing")
        assert results == []


class TestParseModelPageMapper:
    """mapper is derived from the Slot Map section of the model page."""

    @staticmethod
    def _page(slot_map_cell: str | None) -> bytes:
        specs = (
            '<table class="wikitable">'
            "<tr><th>Brand</th><td>Sony</td></tr>"
            "<tr><th>Model</th><td>HB-F1XD / HB-F1XDmk2</td></tr>"
            "</table>"
        )
        slot_map = "" if slot_map_cell is None else (
            '<h2><span id="Slot_Map" class="mw-headline">Slot Map</span></h2>'
            "<table><tr><td></td><th>Slot 0</th></tr>"
            f'<tr><th>Page 0000h~3FFFh</th><td>{slot_map_cell}</td></tr></table>'
        )
        return f"<html><body>{specs}{slot_map}</body></html>".encode()

    def test_mapper_yes_for_every_variant(self):
        results = parse_model_page(self._page("128kB Memory Mapper"), "MSX2", "Sony HB-F1XD")
        assert [r.get("mapper") for r in results] == ["Yes"] * len(results)

    def test_mapper_no_when_slot_map_lacks_mapper(self):
        results = parse_model_page(self._page("64kB RAM"), "MSX2", "Sony HB-F1XD")
        assert all(r.get("mapper") == "No" for r in results)

    def test_mapper_absent_without_slot_map(self):
        results = parse_model_page(self._page(None), "MSX2", "Sony HB-F1XD")
        assert all("mapper" not in r for r in results)


class TestListModelPagesGraceful:
    """Category page fetch failures are logged and skipped; other categories continue."""

    def test_single_category_none_returns_empty(self):
        # All categories return None (e.g. 403 on live, or missing file in mirror)
        source = _StubSource([None, None, None])
        pages = list_model_pages(source, delay=0)
        assert pages == []

    def test_partial_category_failure_still_returns_others(self):
        """If one category returns None, pages from successful ones are still returned."""
        # Three categories: first fails, second succeeds, third fails
        source = _StubSource([None, _GOOD_CATEGORY_HTML, None])
        pages = list_model_pages(source, delay=0)
        assert len(pages) >= 1
        assert any(p["title"] == "Sony HB-75P" for p in pages)


class TestFetchAllGraceful:
    """fetch_all with a LivePageSource that errors returns [] gracefully."""

    def test_network_error_returns_empty_not_raises(self):
        session = MagicMock()
        session.get.side_effect = Exception("403 Forbidden")
        models = fetch_all(session=session, delay=0)
        assert models == []


# ---------------------------------------------------------------------------
# MirrorPageSource integration with fetch_all
# ---------------------------------------------------------------------------

class TestFetchAllWithMirror:
    """fetch_all reads from a local MirrorPageSource."""

    _CATEGORY_HTML = (
        b"<html><body>"
        b'<div id="mw-pages">'
        b'<a href="/wiki/Sony_HB-75P" title="Sony HB-75P">Sony HB-75P</a>'
        b"</div></body></html>"
    )
    _MODEL_HTML = b"""
    <html><body><table class="wikitable">
      <tr><th>Brand</th><td>Sony</td></tr>
      <tr><th>Model</th><td>HB-75P</td></tr>
      <tr><th>Year</th><td>1985</td></tr>
      <tr><th>Region</th><td>Europe</td></tr>
    </table></body></html>
    """

    def test_reads_models_from_mirror(self, tmp_path):
        # Write category and model files using the expected filename convention
        (tmp_path / "Category_MSX2 Computers - MSX Wiki.html").write_bytes(self._CATEGORY_HTML)
        (tmp_path / "Category_MSX2+ Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX turbo R Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX1 Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Sony HB-75P - MSX Wiki.html").write_bytes(self._MODEL_HTML)

        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert len(models) == 1
        assert models[0]["manufacturer"] == "Sony"

    def test_missing_category_file_skipped(self, tmp_path):
        # No category files written at all → zero models, no exception
        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert models == []

    def test_missing_model_file_skipped(self, tmp_path):
        # Category present, model file absent → skip that model
        (tmp_path / "Category_MSX2 Computers - MSX Wiki.html").write_bytes(self._CATEGORY_HTML)
        (tmp_path / "Category_MSX2+ Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX turbo R Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX1 Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        # Model file deliberately not written

        source = MirrorPageSource(tmp_path)
        models = fetch_all(source=source, delay=0)
        assert models == []

    def test_no_http_calls_with_mirror(self, tmp_path, monkeypatch):
        """No requests.Session.get calls are made when using a MirrorPageSource."""
        import requests
        original_get = requests.Session.get

        def should_not_be_called(*args, **kwargs):
            raise AssertionError("HTTP request made during mirror mode")

        monkeypatch.setattr(requests.Session, "get", should_not_be_called)
        (tmp_path / "Category_MSX2 Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX2+ Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX turbo R Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        (tmp_path / "Category_MSX1 Computers - MSX Wiki.html").write_bytes(b"<html><body></body></html>")
        source = MirrorPageSource(tmp_path)
        fetch_all(source=source, delay=0)  # no exception = no HTTP calls


# ---------------------------------------------------------------------------
# _parse_connections — per-bullet granularity and negation detection
# ---------------------------------------------------------------------------

def _connections_soup(bullets: list[str], *, note: str | None = None) -> BeautifulSoup:
    """Build a minimal soup with a Connections <h3> and a <ul> of bullets."""
    items = "".join(f"<li>{b}</li>" for b in bullets)
    note_html = f"<p>{note}</p>" if note else ""
    html = f"<html><body><h3>Connections</h3><ul>{items}</ul>{note_html}</body></html>"
    return BeautifulSoup(html, "lxml")


class TestParseConnections:

    def test_cassette_bullet_sets_tape_interface(self):
        soup = _connections_soup(["Cassette port"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"
        assert "Cassette" in result.get("connectivity", "")

    def test_data_recorder_bullet_sets_tape_interface(self):
        soup = _connections_soup(["Data Recorder port"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"

    def test_printer_bullet_sets_printer(self):
        soup = _connections_soup(["Centronics printer port"])
        result = _parse_connections(soup)
        assert "Printer" in result.get("connectivity", "")

    def test_no_printer_port_note_suppresses_printer(self):
        """Regression: 1chipMSX — 'Note: No printer port!' must not set Printer."""
        soup = _connections_soup(
            ["Data Recorder (RCA)", "2 cartridge slots"],
            note="Note: No printer port!",
        )
        result = _parse_connections(soup)
        assert "Printer" not in result.get("connectivity", "")

    def test_no_printer_bullet_suppresses_printer(self):
        """A bullet explicitly saying 'no printer' must not set Printer."""
        soup = _connections_soup(["No printer port", "Cassette port"])
        result = _parse_connections(soup)
        assert "Printer" not in result.get("connectivity", "")
        assert result.get("tape_interface") == "Yes"

    def test_negation_in_one_bullet_does_not_suppress_other_ports(self):
        """Negation in the printer bullet must not suppress the tape detection."""
        soup = _connections_soup(["Cassette port", "No printer interface"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"
        assert "Printer" not in result.get("connectivity", "")

    def test_no_cassette_bullet_suppresses_tape(self):
        soup = _connections_soup(["No cassette port", "Printer port"])
        result = _parse_connections(soup)
        assert "tape_interface" not in result
        assert "Printer" in result.get("connectivity", "")

    def test_without_printer_suppresses_printer(self):
        soup = _connections_soup(["RGB video output", "Without printer"])
        result = _parse_connections(soup)
        assert "Printer" not in result.get("connectivity", "")

    def test_both_cassette_and_printer_present(self):
        soup = _connections_soup(["Cassette connector", "Parallel printer port"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"
        assert "Printer" in result.get("connectivity", "")
        assert "Cassette" in result.get("connectivity", "")

    def test_cartridge_slots_stored_as_scraped_cart_slots(self):
        """msxorg parser stores raw slot count under scraped_cart_slots, not cartridge_slots."""
        soup = _connections_soup(["2 cartridge slots"])
        result = _parse_connections(soup)
        assert result.get("scraped_cart_slots") == 2
        assert "cartridge_slots" not in result


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


# ---------------------------------------------------------------------------
# list_model_pages — mirror without category pages (directory scan fallback)
# ---------------------------------------------------------------------------

from urllib.parse import quote

from scraper.mirror import slug_to_filename
from scraper.msxorg import CATEGORY_URLS, GENERATION_RANK, WIKI_URL


def _cat_path(standard: str) -> str:
    return "/wiki/" + CATEGORY_URLS[standard].split("/wiki/", 1)[1]


def _mirror_page(slug: str, standards: list[str], *, sidebar: str | None = None, body: str = "") -> bytes:
    """A browser-saved model page: wgPageName, category links, optional sidebar link."""
    cats = " | ".join(f'<a href="{_cat_path(s)}">{s}</a>' for s in standards)
    side = f'<div id="sidebar"><a href="{_cat_path(sidebar)}">x</a></div>' if sidebar else ""
    return (
        f'<html><head><script>var wgPageName="{slug.replace("/", chr(92) + "/")}";</script></head>'
        f"<body>{side}{body}"
        f'<div id="catlinks"><div id="mw-normal-catlinks"><a href="/wiki/Special:Categories">Categories</a>: {cats}'
        f"</div></div></body></html>"
    ).encode("utf-8")


def _write_page(tmp_path, slug: str, content: bytes) -> None:
    (tmp_path / slug_to_filename(WIKI_URL + quote(slug, safe="/"))).write_bytes(content)


class TestListModelPagesFromMirrorScan:
    _by_rank = sorted(GENERATION_RANK, key=GENERATION_RANK.__getitem__)

    def test_standard_is_highest_ranked_category(self, tmp_path):
        low, high = self._by_rank[0], self._by_rank[-1]
        _write_page(tmp_path, "Acme_X-1", _mirror_page("Acme_X-1", [high, low]))
        pages = list_model_pages(MirrorPageSource(tmp_path), delay=0)
        assert [(p["title"], p["standard"]) for p in pages] == [("Acme X-1", high)]

    def test_url_maps_back_to_saved_file(self, tmp_path):
        slug = "Yamaha_CX7M/128"
        content = _mirror_page(slug, [self._by_rank[0]])
        _write_page(tmp_path, slug, content)
        src = MirrorPageSource(tmp_path)
        pages = list_model_pages(src, delay=0)
        assert len(pages) == 1
        assert src.fetch_page(pages[0]["title"], pages[0]["url"]) == content

    def test_category_link_outside_catlinks_is_ignored(self, tmp_path):
        _write_page(tmp_path, "MSX_Fair", _mirror_page("MSX_Fair", [], sidebar=self._by_rank[0]))
        assert list_model_pages(MirrorPageSource(tmp_path), delay=0) == []

    def test_category_files_and_pages_without_slug_are_skipped(self, tmp_path):
        std = self._by_rank[0]
        (tmp_path / "Category_Acme X - MSX Wiki.html").write_bytes(_mirror_page("Category:Acme_X", [std]))
        (tmp_path / "Acme X-2 - MSX Wiki.html").write_bytes(
            _mirror_page("Acme_X-2", [std]).replace(b"wgPageName", b"wgOther")
        )
        assert list_model_pages(MirrorPageSource(tmp_path), delay=0) == []

    def test_category_pages_take_precedence_over_scan(self, tmp_path):
        std = self._by_rank[0]
        (tmp_path / slug_to_filename(CATEGORY_URLS[std])).write_bytes(_GOOD_CATEGORY_HTML)
        _write_page(tmp_path, "Acme_X-1", _mirror_page("Acme_X-1", [std]))
        pages = list_model_pages(MirrorPageSource(tmp_path), delay=0)
        assert [p["title"] for p in pages] == ["Sony HB-75P"]

    def test_fetch_all_parses_scanned_pages(self, tmp_path):
        body = _GOOD_MODEL_HTML.decode().split("<body>", 1)[1].rsplit("</body>", 1)[0]
        std = self._by_rank[0]
        _write_page(tmp_path, "Sony_HB-75P", _mirror_page("Sony_HB-75P", [std], body=body))
        models = fetch_all(source=MirrorPageSource(tmp_path), delay=0)
        assert [(m["manufacturer"], m["model"], m["generation"]) for m in models] == [("Sony", "HB-75P", std)]


# ---------------------------------------------------------------------------
# Series pages — member pages without a specs table defer to their series
# ---------------------------------------------------------------------------

_MEMBER_PAGE = b"""
<html><body><div id="bodyContent">
<p>This machine was aimed at the European market - see
<a href="/wiki/Category:Sony_HB-10">HB-10 series</a> for the technical details</p>
</div></body></html>
"""

_SERIES_PAGE = b"""
<html><body><div id="bodyContent">
<table>
<tr><th>Product</th><th>Region</th><th>Keyboard</th></tr>
<tr><td>Sony HB-10</td><td>JP</td><td>QWERTY/JP50on</td></tr>
<tr><td>Sony HB-10P</td><td>NL</td><td>QWERTY with &#163; key</td></tr>
</table>
<table>
<tr><th>Brand</th><td>Sony</td></tr>
<tr><th>Model</th><td>HB-10 / HB-10P</td></tr>
<tr><th>Year</th><td>Late 1985 (HB-10) or 1986 (other models)</td></tr>
<tr><th>Region</th><td>See table above</td></tr>
<tr><th>RAM</th><td>16kB in slot 0 (HB-10) or 64kB in slot 3 (other models)</td></tr>
<tr><th>Video</th><td>Texas Instruments TMS9118NL (HB-10) or Toshiba T6950 (other models)</td></tr>
<tr><th>Chipset</th><td>Yamaha S3527</td></tr>
</table>
<h2><span id="Slot_Map_for_16kB_model" class="mw-headline">Slot Map for 16kB model</span></h2>
<table><tr><td></td><th>Slot 0</th><th>Slot 3</th></tr>
<tr><th>Page 0000h~3FFFh</th><td>Main-ROM</td><td></td></tr></table>
<h2><span id="Slot_Map_for_64kB_models" class="mw-headline">Slot Map for 64kB models</span></h2>
<table><tr><td></td><th>Slot 0</th><th>Slot 3</th></tr>
<tr><th>Page 0000h~3FFFh</th><td>Main-ROM</td><td>64kB Memory Mapper</td></tr></table>
</div>
<div id="mw-pages"><a href="/wiki/Sony_HB-10">Sony HB-10</a><a href="/wiki/Sony_HB-10P">Sony HB-10P</a></div>
</body></html>
"""


class TestParseModelPageSeries:
    """A member page with no specs table is parsed from its series page, for its own variant."""

    @staticmethod
    def _loader(requested: list[str]):
        def load(slug: str) -> bytes | None:
            requested.append(slug)
            return _SERIES_PAGE if slug == "Sony_HB-10" else None
        return load

    def test_member_gets_its_variant_values(self):
        requested: list[str] = []
        results = parse_model_page(_MEMBER_PAGE, "MSX1", "Sony HB-10P", series_loader=self._loader(requested))
        assert requested == ["Sony_HB-10"]
        assert len(results) == 1
        r = results[0]
        assert (r["manufacturer"], r["model"]) == ("Sony", "HB-10P")
        assert r["msxorg_title"] == "Sony HB-10P"      # links to the member's own page
        assert r["year"] == 1986
        assert r["region"] == "Netherlands"
        assert r["main_ram_kb"] == 64
        assert r["vdp"] == "T6950"
        assert r["engine_raw"] == "Yamaha S3527"

    def test_slot_map_and_mapper_come_from_the_variants_slot_map(self):
        results = parse_model_page(_MEMBER_PAGE, "MSX1", "Sony HB-10P", series_loader=self._loader([]))
        assert results[0]["mapper"] == "Yes"             # 64kB models table has a memory mapper
        results = parse_model_page(_MEMBER_PAGE, "MSX1", "Sony HB-10", series_loader=self._loader([]))
        assert results[0]["mapper"] == "No"              # 16kB model table does not
        assert results[0]["main_ram_kb"] == 16

    def test_without_loader_the_member_page_is_skipped(self):
        assert parse_model_page(_MEMBER_PAGE, "MSX1", "Sony HB-10P") == []

    def test_missing_series_page_skips_the_member(self):
        assert parse_model_page(_MEMBER_PAGE.replace(b"Sony_HB-10", b"Sony_HB-99"), "MSX1",
                                "Sony HB-10P", series_loader=self._loader([])) == []

    def test_page_with_own_specs_ignores_series(self):
        requested: list[str] = []
        page = (b'<html><body><table class="wikitable"><tr><th>Brand</th><td>Sony</td></tr>'
                b'<tr><th>Model</th><td>HB-75P</td></tr></table></body></html>')
        results = parse_model_page(page, "MSX1", "Sony HB-75P", series_loader=self._loader(requested))
        assert requested == []
        assert results[0]["model"] == "HB-75P"


class TestFetchAllSeries:
    def test_series_page_is_fetched_once_through_the_page_source(self):
        fetched: list[str] = []

        class Source:
            def fetch_category(self, standard, url, page=1):
                return None

            def scan_pages(self):
                return iter([])

            def fetch_page(self, title, url):
                fetched.append(url.rsplit("/wiki/", 1)[1])
                return _SERIES_PAGE if "Category:" in url else _MEMBER_PAGE

        with patch_list_pages([("Sony HB-10", "MSX1"), ("Sony HB-10P", "MSX1")]):
            models = fetch_all(source=Source(), delay=0)

        assert sorted(m["model"] for m in models) == ["HB-10", "HB-10P"]
        assert fetched.count("Category:Sony_HB-10") == 1


def patch_list_pages(pages):
    from unittest.mock import patch as _patch
    entries = [{"title": t, "url": "https://www.msx.org/wiki/" + t.replace(" ", "_"), "standard": s}
               for t, s in pages]
    return _patch("scraper.msxorg.list_model_pages", return_value=entries)


# ---------------------------------------------------------------------------
# Model name cleanup — editorial notes are not part of the name
# ---------------------------------------------------------------------------

class TestModelNameNotes:
    @staticmethod
    def _page(model_field: str) -> bytes:
        return (f'<html><body><table class="wikitable"><tr><th>Brand</th><td>Pioneer</td></tr>'
                f'<tr><th>Model</th><td>{model_field}</td></tr></table></body></html>').encode()

    @pytest.mark.parametrize("field,expected", [
        ("PX-7(HB) - note: to not be confused with the Japanese Pioneer PX-7 (BK)!", "PX-7(HB)"),
        ("PX-7(HB) (note: not the Japanese PX-7)", "PX-7(HB)"),
        ("PX-7(HB) - Note: see below", "PX-7(HB)"),
    ])
    def test_note_is_dropped(self, field, expected):
        [record] = parse_model_page(self._page(field), "MSX1", "Pioneer PX-7(HB)")
        assert record["model"] == expected

    def test_cleaned_name_is_recorded_as_former_name(self):
        from scraper.aliases import FORMER_MODEL_FIELD
        field = "PX-7(HB) - note: to not be confused with the Japanese Pioneer PX-7 (BK)!"
        [record] = parse_model_page(self._page(field), "MSX1", "Pioneer PX-7(HB)")
        assert record[FORMER_MODEL_FIELD] == field

    def test_ordinary_names_are_untouched(self):
        from scraper.aliases import FORMER_MODEL_FIELD
        [record] = parse_model_page(self._page("PX-7"), "MSX1", "Pioneer PX-7")
        assert record["model"] == "PX-7"
        assert FORMER_MODEL_FIELD not in record

    def test_split_models_are_cleaned_too(self):
        results = parse_model_page(self._page("PX-7 / PX-7(HB) - note: not the PX-7 (BK)"), "MSX1", "Pioneer PX-7")
        assert [r["model"] for r in results] == ["PX-7", "PX-7(HB)"]


def test_cleaned_name_keeps_its_registry_id(tmp_path):
    """The id registered under the note-laden name carries over to the clean name."""
    import json
    from scraper.aliases import FORMER_MODEL_FIELD
    from scraper.build import build
    from scraper.registry import IDRegistry

    note_name = "PX-7(HB) - note: to not be confused with the Japanese Pioneer PX-7 (BK)!"
    (tmp_path / "registry.json").write_text(json.dumps({
        "version": 2, "models": {f"pioneer|{note_name.lower()}": 269},
        "retired_models": [], "next_model_id": 500,
    }))
    (tmp_path / "openmsx.json").write_text(json.dumps([]))
    (tmp_path / "msxorg.json").write_text(json.dumps([{
        "manufacturer": "Pioneer", "model": "PX-7(HB)", "generation": "MSX1",
        "msxorg_title": "Pioneer PX-7(HB)", FORMER_MODEL_FIELD: note_name,
    }]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json", registry_path=tmp_path / "registry.json",
          output_path=tmp_path / "data.js")
    reg = IDRegistry.load(tmp_path / "registry.json")
    assert reg.models["pioneer|px-7(hb)"] == 269
    assert reg.next_model_id == 500

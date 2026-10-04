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

    def test_split_entries_share_brand(self):
        results = parse_model_page(self._COMBINED_HTML, "MSX2", "Sakhr AX-350II")
        assert all(r["brand"] == "Sakhr" for r in results)

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
        assert models[0]["brand"] == "Sony"

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

    def test_data_recorder_bullet_sets_tape_interface(self):
        soup = _connections_soup(["Data Recorder port"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"

    def test_printer_bullet_sets_printer(self):
        soup = _connections_soup(["Centronics printer port"])
        result = _parse_connections(soup)
        assert result["printer_port"] == "Yes"

    def test_no_printer_port_note_suppresses_printer(self):
        """Regression: 1chipMSX — 'Note: No printer port!' must not set Printer."""
        soup = _connections_soup(
            ["Data Recorder (RCA)", "2 cartridge slots"],
            note="Note: No printer port!",
        )
        result = _parse_connections(soup)
        assert result["printer_port"] == "No"

    def test_no_printer_bullet_suppresses_printer(self):
        """A bullet explicitly saying 'no printer' must not set Printer."""
        soup = _connections_soup(["No printer port", "Cassette port"])
        result = _parse_connections(soup)
        assert result["printer_port"] == "No"
        assert result.get("tape_interface") == "Yes"

    def test_negation_in_one_bullet_does_not_suppress_other_ports(self):
        """Negation in the printer bullet must not suppress the tape detection."""
        soup = _connections_soup(["Cassette port", "No printer interface"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"
        assert result["printer_port"] == "No"

    def test_no_cassette_bullet_suppresses_tape(self):
        soup = _connections_soup(["No cassette port", "Printer port"])
        result = _parse_connections(soup)
        assert result["tape_interface"] == "No"
        assert result["printer_port"] == "Yes"

    def test_without_printer_suppresses_printer(self):
        soup = _connections_soup(["RGB video output", "Without printer"])
        result = _parse_connections(soup)
        assert result["printer_port"] == "No"

    def test_both_cassette_and_printer_present(self):
        soup = _connections_soup(["Cassette connector", "Parallel printer port"])
        result = _parse_connections(soup)
        assert result.get("tape_interface") == "Yes"
        assert result["printer_port"] == "Yes"

    def test_no_connections_section_leaves_printer_port_unknown(self):
        result = _parse_connections(BeautifulSoup("<html><body><p>Nothing</p></body></html>", "lxml"))
        assert "printer_port" not in result
        assert "tape_interface" not in result

    def test_tape_connector_needing_an_adapter(self):
        soup = _connections_soup(["MT/IF connector (requires the FA-32 CMT I/F package to connect a tape recorder)"])
        assert _parse_connections(soup)["tape_interface"] == "Adapter"

    def test_plain_cassette_port_beats_adapter(self):
        soup = _connections_soup(["Cassette port", "CMT I/F adapter port"])
        assert _parse_connections(soup)["tape_interface"] == "Yes"

    def test_connections_without_cassette_means_no_tape(self):
        result = _parse_connections(_connections_soup(["Printer port", "RGB output"]))
        assert result["tape_interface"] == "No"

    def test_connections_without_printer_means_no(self):
        result = _parse_connections(_connections_soup(["Cassette port", "RGB output"]))
        assert result["printer_port"] == "No"

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
        assert [(m["brand"], m["model"], m["generation"]) for m in models] == [("Sony", "HB-75P", std)]


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
        assert (r["brand"], r["model"]) == ("Sony", "HB-10P")
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
        "brand": "Pioneer", "model": "PX-7(HB)", "generation": "MSX1",
        "msxorg_title": "Pioneer PX-7(HB)", FORMER_MODEL_FIELD: note_name,
    }]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json", registry_path=tmp_path / "registry.json",
          output_path=tmp_path / "data.js")
    reg = IDRegistry.load(tmp_path / "registry.json")
    assert reg.models["pioneer|px-7(hb)"] == 269
    assert reg.next_model_id == 500


# ---------------------------------------------------------------------------
# Regional pages — "Panasonic CF-2700 (GE)" whose specs name the base model
# ---------------------------------------------------------------------------

class TestRegionalPages:
    @staticmethod
    def _page(brand: str, model: str) -> bytes:
        return (f'<html><body><table class="wikitable"><tr><th>Brand</th><td>{brand}</td></tr>'
                f'<tr><th>Model</th><td>{model}</td></tr></table></body></html>').encode()

    def test_named_after_the_title(self):
        [record] = parse_model_page(self._page("Maker A", "M-1"), "MSX1", "Maker B M-1 (GE)")
        assert (record["brand"], record["model"]) == ("Maker B", "M-1 (GE)")
        assert record["msxorg_title"] == "Maker B M-1 (GE)"

    def test_multi_word_brand(self):
        [record] = parse_model_page(self._page("Maker", "M-1"), "MSX1", "Big Maker M-1 (UK)")
        assert (record["brand"], record["model"]) == ("Big Maker", "M-1 (UK)")

    @pytest.mark.parametrize("model,title", [
        ("M-1", "Maker M-1"),              # no tag
        ("M-1 (GE)", "Maker M-1 (GE)"),    # specs already carry the tag
        ("M-1", "Maker M-10 (GE)"),        # title names another model
        ("M-1", "Maker M-1 (v2)"),         # not a country tag
        ("M-1", "M-1 (GE)"),               # no brand in the title
    ])
    def test_other_pages_keep_the_specs_name(self, model, title):
        [record] = parse_model_page(self._page("Maker", model), "MSX1", title)
        assert (record["brand"], record["model"]) == ("Maker", model)


def _build_with_aliases(tmp_path, monkeypatch, aliases, openmsx, msxorg, registry=None):
    import json
    import scraper.build as build_module
    from scraper.build import build
    from scraper.registry import IDRegistry

    (tmp_path / "aliases.json").write_text(json.dumps(aliases))
    monkeypatch.setattr(build_module, "ALIASES_PATH", tmp_path / "aliases.json")
    if registry is not None:
        (tmp_path / "registry.json").write_text(json.dumps(registry))
    (tmp_path / "openmsx.json").write_text(json.dumps(openmsx))
    (tmp_path / "msxorg.json").write_text(json.dumps(msxorg))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json", registry_path=tmp_path / "registry.json",
          output_path=tmp_path / "data.js")
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    return data, IDRegistry.load(tmp_path / "registry.json")


def test_regional_page_joins_the_openmsx_machine(tmp_path, monkeypatch):
    """msx.org "(GE)" page + openMSX "(DE)" machine are one row with the page's data."""
    data, _ = _build_with_aliases(
        tmp_path, monkeypatch, {"variant_tag": {"DE": ["GE"]}},
        openmsx=[{"brand": "Maker B", "model": "M-1 (DE)", "generation": "MSX1",
                  "openmsx_id": "Maker_B_M-1_DE"}],
        msxorg=[{"brand": "Maker B", "model": "M-1 (GE)", "generation": "MSX1",
                 "msxorg_title": "Maker B M-1 (GE)", "vram_kb": 16}],
    )
    keys = [c["key"] for c in data["columns"]]
    rows = [dict(zip(keys, m["values"])) for m in data["models"]]
    assert [(r["brand"], r["model"]) for r in rows] == [("Maker B", "M-1 (DE)")]
    assert rows[0]["vram_kb"] == 16


def test_canonicalised_tag_keeps_its_registry_id(tmp_path, monkeypatch):
    _, reg = _build_with_aliases(
        tmp_path, monkeypatch, {"variant_tag": {"GB": ["UK"]}},
        openmsx=[{"brand": "Maker", "model": "M-7(UK)", "generation": "MSX1"}],
        msxorg=[],
        registry={"version": 2, "models": {"maker|m-7(uk)": 42}, "retired_models": [], "next_model_id": 500},
    )
    assert reg.models["maker|m-7(gb)"] == 42
    assert reg.next_model_id == 500


# ---------------------------------------------------------------------------
# Several models, localised products and other names in one Model field
# ---------------------------------------------------------------------------

from scraper.msxorg import split_model_field


@pytest.mark.parametrize("raw,models,products,others", [
    ("M-1", ["M-1"], {}, []),
    ("M-1 / M-1F", ["M-1", "M-1F"], {}, []),
    ("MX5 or MX5/128", ["MX5", "MX5/128"], {}, []),
    ("FM-1 or QB2515", ["FM-1"], {}, ["QB2515"]),
    ("MX5 (MX5A, MX5C or MX5U)", ["MX5"], {"MX5A": "MX5", "MX5C": "MX5", "MX5U": "MX5"}, []),
    ("Perfect One (DPC-1CD)", ["Perfect One (DPC-1CD)"], {}, []),   # one name in parentheses: kept
    ("AB-2 (Manufacturer: Maker)", ["AB-2 (Manufacturer: Maker)"], {}, []),
    ("PX-7(HB) - note: not the PX-7", ["PX-7(HB)"], {}, []),
])
def test_split_model_field(raw, models, products, others):
    assert split_model_field(raw) == (models, products, others)


def _multi_page(model: str, ram: str, extra: str = "", table: str = "") -> bytes:
    return (f'<html><body>{table}<table class="wikitable">'
            f'<tr><th>Brand</th><td>Maker</td></tr><tr><th>Model</th><td>{model}</td></tr>'
            f'<tr><th>Region</th><td>Europe</td></tr><tr><th>RAM</th><td>{ram}</td></tr>'
            f'<tr><th>Keyboard layout</th><td>QWERTY</td></tr>{extra}</table></body></html>').encode()


_PRODUCT_TABLE = ('<table><tr><th>Product</th><th>Region</th><th>Keyboard</th><th>VDP</th></tr>'
                  '<tr><td>MX5A</td><td>AU, NZ</td><td>QWERTY with £ key</td><td>TMS9929A</td></tr>'
                  '<tr><td>MX5U</td><td>US</td><td>QWERTY</td><td>TMS9918A</td></tr></table>')


class TestSeveralModelsOnOnePage:
    def test_or_models_take_their_own_values(self):
        records = parse_model_page(_multi_page("MX5 or MX5/128", "64kB (MX5) or 128kB (MX5/128)"), "MSX1", "Maker MX5")
        assert {r["model"]: r["main_ram_kb"] for r in records} == {"MX5": 64, "MX5/128": 128}
        assert {r["msxorg_title"] for r in records} == {"Maker MX5"}

    def test_or_name_is_another_name(self):
        from scraper.aliases import KNOWN_AS_FIELD
        [record] = parse_model_page(_multi_page("FM-1 or QB2515", "16kB"), "MSX1", "Maker FM-1")
        assert record["model"] == "FM-1"
        assert record[KNOWN_AS_FIELD] == ["QB2515"]

    def test_combined_name_is_a_former_name(self):
        from scraper.aliases import FORMER_MODEL_FIELD
        records = parse_model_page(_multi_page("MX5 or MX5/128", "64kB"), "MSX1", "Maker MX5")
        assert records[0][FORMER_MODEL_FIELD] == "MX5 or MX5/128"
        assert FORMER_MODEL_FIELD not in records[1]

    def test_shared_lead_then_labelled_item(self):
        extra = "<tr><th>Audio</th><td>PSG (AY-3-8910), (M-1 version) SFG, MIDI</td></tr>"
        records = parse_model_page(_multi_page("M-1 / M-1F", "64kB", extra), "MSX1", "Maker M-1")
        by_model = {r["model"]: r for r in records}
        assert by_model["M-1F"]["psg"] == by_model["M-1"]["psg"]
        assert by_model["M-1F"]["psg"] is not None


class TestLocalisedProducts:
    def test_listed_products_take_their_table_row(self):
        from scraper.aliases import LOCALISED_FIELD
        page = _multi_page("MX5 (MX5A or MX5U)", "32kB", table=_PRODUCT_TABLE)
        records = {r["model"]: r for r in parse_model_page(page, "MSX1", "Maker MX5")}
        assert set(records) == {"MX5", "MX5A", "MX5U"}
        assert LOCALISED_FIELD not in records["MX5"]
        u = records["MX5U"]
        assert u[LOCALISED_FIELD] == "MX5"
        assert (u["region"], u["keyboard_layout"], u["vdp"]) == ("United States", "QWERTY", "TMS9918A")
        assert u["main_ram_kb"] == records["MX5"]["main_ram_kb"]
        assert u["msxorg_title"] == "Maker MX5"

    def test_table_only_products_localise_the_longest_prefix(self):
        from scraper.aliases import LOCALISED_FIELD
        table = _PRODUCT_TABLE.replace("MX5A", "MX5/128A")
        page = _multi_page("MX5 or MX5/128", "64kB (MX5) or 128kB (MX5/128)", table=table)
        records = {r["model"]: r for r in parse_model_page(page, "MSX1", "Maker MX5")}
        assert records["MX5/128A"][LOCALISED_FIELD] == "MX5/128"
        assert records["MX5/128A"]["main_ram_kb"] == 128
        assert records["MX5U"][LOCALISED_FIELD] == "MX5"


def test_localised_products_join_only_openmsx_machines(tmp_path, monkeypatch):
    """A localised record that is not a version becomes a row only for an openMSX machine without an msx.org page of its own."""
    from scraper.aliases import LOCALISED_FIELD
    page = "Maker MX5"
    msxorg = [
        {"brand": "Maker", "model": "MX5", "generation": "MSX1", "msxorg_title": page, "vram_kb": 16},
        {"brand": "Maker", "model": "MX5U", "generation": "MSX1", "msxorg_title": page,
         "vram_kb": 16, "keyboard_layout": "QWERTY", LOCALISED_FIELD: "MX5"},
        {"brand": "Maker", "model": "MX5A", "generation": "MSX1", "msxorg_title": page,
         "vram_kb": 16, LOCALISED_FIELD: "MX5"},
        {"brand": "Maker", "model": "MX5C", "generation": "MSX1", "msxorg_title": page,
         "vram_kb": 16, LOCALISED_FIELD: "MX5"},
        {"brand": "Maker", "model": "MX5C", "generation": "MSX1", "msxorg_title": "Maker MX5C",
         "vram_kb": 32},
    ]
    openmsx = [{"brand": "Maker", "model": m, "generation": "MSX1"} for m in ("MX5", "MX5U", "MX5C")]
    data, _ = _build_with_aliases(tmp_path, monkeypatch, {}, openmsx=openmsx, msxorg=msxorg)
    keys = [c["key"] for c in data["columns"]]
    rows = {r["model"]: (r, m.get("links", {})) for m in data["models"] for r in [dict(zip(keys, m["values"]))]}
    assert set(rows) == {"MX5", "MX5U", "MX5C"}           # MX5A: no openMSX machine
    assert rows["MX5U"][0]["vram_kb"] == 16
    assert rows["MX5U"][1]["model"] == rows["MX5"][1]["model"]
    assert rows["MX5C"][0]["vram_kb"] == 32                # its own page wins


class TestBuiltInDataRecorder:
    @staticmethod
    def _page(media: str, extras: str, connections: list[str]) -> bytes:
        items = "".join(f"<li>{c}</li>" for c in connections)
        return (f'<html><body><table class="wikitable"><tr><th>Brand</th><td>Maker</td></tr>'
                f'<tr><th>Model</th><td>M-1</td></tr><tr><th>Media</th><td>{media}</td></tr>'
                f'<tr><th>Extras</th><td>{extras}</td></tr></table>'
                f'<h3>Connections</h3><ul>{items}</ul></body></html>').encode()

    def test_media_cassette_tapes_means_yes(self):
        page = self._page("MSX cartridges, cassette tapes", "reset button", ["Note: No Data Recorder connector!"])
        [record] = parse_model_page(page, "MSX1", "Maker M-1")
        assert record["tape_interface"] == "Yes"

    def test_extras_built_in_data_recorder_means_yes(self):
        page = self._page("MSX cartridges", "reset button, built-in data recorder", ["RF output"])
        [record] = parse_model_page(page, "MSX1", "Maker M-1")
        assert record["tape_interface"] == "Yes"

    def test_negated_extras_item_does_not_count(self):
        page = self._page("MSX cartridges", "no data recorder", ["RF output"])
        [record] = parse_model_page(page, "MSX1", "Maker M-1")
        assert record["tape_interface"] == "No"


# ---------------------------------------------------------------------------
# Market status — "Unreleased" / "Rare" about the page's own model
# ---------------------------------------------------------------------------

from scraper.msxorg import MARKET_RARE, MARKET_UNRELEASED, market_status


def _status(sentences: list[str], specs: dict[str, str] | None = None,
            names: list[str] | None = None, brand: str = "Maker") -> str | None:
    html = "<html><body><div id='bodyContent'>" + "".join(f"<p>{s}</p>" for s in sentences) + "</div></body></html>"
    return market_status(html.encode(), specs or {}, names or ["MX-1"], brand)


class TestMarketStatus:
    @pytest.mark.parametrize("field,value", [
        ("Year", "unreleased"),
        ("Year", "1986 (never released)"),
        ("Region", "unreleased"),
        ("Launch price", "unreleased"),
        ("Year", "unreleased, the prototype was built ≥1988"),
    ])
    def test_unreleased_from_specs(self, field, value):
        assert _status([], {field: value}) == MARKET_UNRELEASED

    @pytest.mark.parametrize("sentence", [
        "Although announced in several magazines, this computer has never been released.",
        "It was announced for 2690 FF but was never released for unknown reasons.",
        "The Maker MX-1 is a computer that has never been released onto the public market.",
        "The MX-1 is an unreleased prototype MSX2.",
        "It has remained at the prototype level.",
    ])
    def test_unreleased_from_description(self, sentence):
        assert _status([sentence]) == MARKET_UNRELEASED

    @pytest.mark.parametrize("sentence", [
        "The Maker MX-1 is a rare MSX1 computer.",
        "The MX-1 is a very rare computer.",
        "This model is very rare.",
        "This model seems to be very rare.",
        "It's a rare version of the MX-2 and looks almost exactly the same.",
        "This rare machine was available only in red.",
        "Note: This version seems to be very rare.",
        "The Maker MX-1, a.k.a Wavy1 , is a rare computer.",
        "The MX-1 a.k.a. Wavy1SK is a very rare MSX1 computer, that seems to look like the MX-2.",
        "The MX-1 is an extremely rare computer.",
        "They sold a little more than 100 computers, so it means that this machine is very rare.",
        "Very little is known about the computer, and very few units are known to exist.",
    ])
    def test_rare(self, sentence):
        assert _status([sentence]) == MARKET_RARE

    @pytest.mark.parametrize("sentence", [
        "A few rare cartridges use SW1 and SW2 as GND.",
        "A lightpen was planned in option with its dedicated cartridge, but was never released.",
        "It was also planned to put the firmware in a model for Europe, but it has never been released.",
        "There were plans for an European version with more RAM, but it has never been released.",
        "The MX-1 is one of the rare MSX1 computers having a Kanji-ROM.",
        "The SVI-728 is a MSX1 with a numeric keypad (rare for a MSX1).",
        "There's also a rare white version - see MX-9.",
        "A very rare version was also designed, probably as prototype.",
        "The Maker MX-9 is a very rare computer.",          # another model
        "This model can be upgraded with two chips (rare nowadays).",
        "The MX-1 was released in 1984.",
    ])
    def test_not_about_the_model(self, sentence):
        assert _status([sentence]) is None

    def test_unreleased_wins_over_rare(self):
        assert _status(["The MX-1 is a very rare computer, it's actually an unreleased prototype.",
                        "This model is very rare."], {"Launch price": "unreleased"}) == MARKET_UNRELEASED

    def test_page_records_carry_the_status_and_status_is_not_a_region(self):
        page = (b'<html><body><div id="bodyContent"><p>This model is very rare.</p></div>'
                b'<table class="wikitable"><tr><th>Brand</th><td>Maker</td></tr>'
                b'<tr><th>Model</th><td>MX-1 / MX-1F</td></tr><tr><th>Region</th><td>unreleased</td></tr>'
                b'</table></body></html>')
        records = parse_model_page(page, "MSX1", "Maker MX-1")
        assert {r["market_status"] for r in records} == {MARKET_UNRELEASED}
        assert all("region" not in r for r in records)


# ---------------------------------------------------------------------------
# Modem — built-in modem only ("Yes"); never "No"
# ---------------------------------------------------------------------------

from scraper.msxorg import MODEM_YES, modem_from_specs, modem_in_description


class TestModem:
    @pytest.mark.parametrize("extras,expected", [
        ("Telecom firmware, Modem, probably MSX-Modem BASIC", True),
        ("floppy disk drive, built-in modem with access to The LINKS network", True),
        ("Kanji-ROM, non-standard modem, remote controller", True),
        ("reset button, RS-232C interface", False),
        ("no modem, reset button", False),
        ("", False),
    ])
    def test_extras(self, extras, expected):
        assert modem_from_specs({"Extras": extras}) is expected

    @pytest.mark.parametrize("items,expected", [
        (["RJ11 modular connector (telephone line)"], True),
        (["Two RJ11 modular connectors for modem (line in and telephone out)"], True),
        (["RS-232C connector (DB-25) with switch for terminal/modem operation"], False),
        (["Printer port", "Cassette port"], False),
    ])
    def test_connections(self, items, expected):
        result = _parse_connections(_connections_soup(items))
        assert (result.get("modem") == MODEM_YES) is expected

    @staticmethod
    def _desc(sentences: list[str]) -> bytes:
        return ("<html><body><div id='bodyContent'>" + "".join(f"<p>{s}</p>" for s in sentences)
                + "</div></body></html>").encode()

    @pytest.mark.parametrize("sentence", [
        "The Maker MX-1 is similar to the MX-2 but has a built-in modem.",
        "It has a Russian keyboard and a non-standard modem with switch (CALL COMINI does not work).",
        "This computer comes with a modem and a telephone handset.",
    ])
    def test_description_about_the_model(self, sentence):
        assert modem_in_description(self._desc([sentence]), ["MX-1"], "Maker")

    @pytest.mark.parametrize("sentence", [
        "There is also a special version of the MX-1 with a built-in modem.",
        "The firmware can also be found in the FS-CM1 modem.",
        "The modem speed is 300/1200bps.",
        "The Maker MX-9 has a built-in modem.",
    ])
    def test_description_side_notes_do_not_count(self, sentence):
        assert not modem_in_description(self._desc([sentence]), ["MX-1"], "Maker")

    def test_page_records_carry_the_modem(self):
        page = (b'<html><body><div id="bodyContent"><p>The MX-1 has a built-in modem.</p></div>'
                b'<table class="wikitable"><tr><th>Brand</th><td>Maker</td></tr>'
                b'<tr><th>Model</th><td>MX-1 / MX-1F</td></tr></table></body></html>')
        assert {r.get("modem") for r in parse_model_page(page, "MSX1", "Maker MX-1")} == {MODEM_YES}

    def test_no_modem_means_no_value(self):
        page = (b'<html><body><table class="wikitable"><tr><th>Brand</th><td>Maker</td></tr>'
                b'<tr><th>Model</th><td>MX-1</td></tr></table>'
                b'<h3>Connections</h3><ul><li>Printer port</li></ul></body></html>')
        [record] = parse_model_page(page, "MSX1", "Maker MX-1")
        assert "modem" not in record


@pytest.mark.parametrize("audio", ["PSG (AY-3-8910)", "PSG (YM2149 integrated in MSX-Engine S3527)", "AY-3-8910"])
def test_psg_is_yes(audio):
    from scraper.msxorg import _parse_audio
    assert _parse_audio(audio)["psg"] == "Yes"


# ── Versions of a model (version lists, Product/Version tables) ───────────

_VERSION_LIST = ("<p>Four models were produced, with the keyboard as difference:</p><ul>"
                 "<li>MX 80/00 for the Dutch and Belgian markets, keyboard layout is QWERTY</li>"
                 "<li>MX 80/16 for the Spanish market, keyboard layout is QWERTY with ñ key</li>"
                 "<li>MX 80/19 Version sold in France (AZERTY)</li></ul>")


class TestVersions:
    @pytest.mark.parametrize("name,model,expected", [
        ("MX 80/16", "MX 80", True), ("MX5A", "MX5", True), ("HC-90(V)", "HC-90", True), ("MX 80-16", "MX 80", True),
        ("MX 800", "MX 80", False), ("Other MX 80", "MX 80", False), ("MX 80 Pack", "MX 80", False),
    ])
    def test_is_version(self, name, model, expected):
        from scraper.msxorg import is_version
        assert is_version(name, model) is expected

    @pytest.mark.parametrize("text,expected", [
        ("MX 80/00 for the Dutch and Belgian markets, keyboard layout is QWERTY",
         {"Region": "Dutch, Belgian", "Keyboard layout": "QWERTY"}),
        ("MX 80/00 Version sold mainly in Belgium, France and The Netherlands",
         {"Region": "Belgium, France, The Netherlands"}),
        ("MX 80/16 Version sold in Spain (with ñ key)", {"Region": "Spain"}),
        ("MX5A: Australian market", {}),
    ])
    def test_list_item_specs(self, text, expected):
        from scraper.msxorg import list_item_specs
        assert list_item_specs(text) == expected

    def test_list_versions_become_flagged_records_with_their_own_values(self):
        from scraper.aliases import LOCALISED_FIELD, VERSION_FIELD
        page = _multi_page("MX 80", "128kB", table=_VERSION_LIST)
        records = {r["model"]: r for r in parse_model_page(page, "MSX2", "Maker MX 80")}
        assert set(records) == {"MX 80", "MX 80/00", "MX 80/16", "MX 80/19"}
        v16 = records["MX 80/16"]
        assert (v16[LOCALISED_FIELD], v16[VERSION_FIELD]) == ("MX 80", True)
        assert (v16["region"], v16["keyboard_layout"]) == ("Spanish", "QWERTY with ñ key")
        assert v16["main_ram_kb"] == records["MX 80"]["main_ram_kb"]
        assert VERSION_FIELD not in records["MX 80"]

    def test_version_table_rows_give_ram_and_vdp(self):
        from scraper.aliases import OWN_FIELDS_FIELD, VERSION_FIELD
        table = ('<table><tr><th>Version</th><th>RAM</th><th>VDP</th></tr>'
                 '<tr><td>MX 9</td><td>64kB</td><td>V9938</td></tr>'
                 '<tr><td>MX 9(V)</td><td>256kB</td><td>V9958</td></tr></table>')
        page = _multi_page("MX 9", "256kB (version V) or 64kB (other versions)", table=table)
        records = {r["model"]: r for r in parse_model_page(page, "MSX2", "Maker MX 9")}
        assert records["MX 9(V)"][VERSION_FIELD] is True
        assert (records["MX 9(V)"]["main_ram_kb"], records["MX 9(V)"]["vdp"]) == (256, "V9958")
        assert {"main_ram_kb", "vdp"} <= set(records["MX 9(V)"][OWN_FIELDS_FIELD])
        assert (records["MX 9"]["main_ram_kb"], records["MX 9"]["vdp"]) == (64, "V9938")   # its own table row

    def test_a_model_listed_in_several_rows_has_no_row_of_its_own(self):
        table = ('<table><tr><th>Product</th><th>Region</th></tr>'
                 '<tr><td>MX 7</td><td>NL</td></tr><tr><td>MX 7</td><td>FR</td></tr></table>')
        [record] = [r for r in parse_model_page(_multi_page("MX 7", "64kB", table=table), "MSX1", "Maker MX 7")
                    if r["model"] == "MX 7"]
        assert record["region"] == "Europe"

    def test_other_products_of_a_table_are_not_versions(self):
        from scraper.aliases import VERSION_FIELD
        table = ('<table><tr><th>Product</th><th>Description</th></tr>'
                 '<tr><td>NMS 100</td><td>Megapack: MX5 + printer</td></tr></table>')
        records = {r["model"]: r for r in parse_model_page(_multi_page("MX5", "32kB", table=table), "MSX1", "Maker MX5")}
        assert VERSION_FIELD not in records.get("NMS 100", {})


def test_versions_become_rows_marked_variant_of_their_main_model(tmp_path, monkeypatch):
    """Versions without an openMSX machine are rows; /00 is the main model; openMSX spellings join."""
    from scraper.aliases import LOCALISED_FIELD, OWN_FIELDS_FIELD, VERSION_FIELD
    page = "Maker MX 80"
    main = {"brand": "Maker", "model": "MX 80", "generation": "MSX2", "msxorg_title": page, "year": 1987,
            "region": "Europe", "keyboard_layout": "(MX 80/00) QWERTY (MX 80/16) QWERTY with ñ"}

    def version(model, **values):
        return {"brand": "Maker", "model": model, "generation": "MSX2", "msxorg_title": page, "year": 1987,
                LOCALISED_FIELD: "MX 80", VERSION_FIELD: True, OWN_FIELDS_FIELD: sorted(values), **values}

    msxorg = [main,
              version("MX 80/00", region="Netherlands", keyboard_layout="QWERTY"),
              version("MX 80/16", region="Spain", keyboard_layout="QWERTY with ñ"),
              version("MX 80(A)", region="Japan"),                                   # openMSX writes "MX 80A"
              {"brand": "Maker", "model": "MX 80/19", "generation": "MSX2", "msxorg_title": page,
               LOCALISED_FIELD: "MX 80"}]                                            # not a version: dropped
    openmsx = [{"brand": "Maker", "model": "MX 80A", "generation": "MSX2", "openmsx_id": "Maker_MX80A", "rtc": "No"},
               {"brand": "Maker", "model": "MX 80", "generation": "MSX2", "openmsx_id": "Maker_MX80", "year": 1986,
                "cpu": "Z80", "rtc": "Yes", "z80_turbo": "No", "himem_addr": "0xF380", "character_set": "International"}]
    data, _ = _build_with_aliases(tmp_path, monkeypatch, {}, openmsx=openmsx, msxorg=msxorg)
    keys = [c["key"] for c in data["columns"]]
    rows = {dict(zip(keys, m["values"]))["model"]: (dict(zip(keys, m["values"])), m) for m in data["models"]}
    assert set(rows) == {"MX 80", "MX 80/16", "MX 80A"}
    assert (rows["MX 80"][0]["region"], rows["MX 80"][0]["keyboard_layout"]) == ("Netherlands", "QWERTY")
    main_id = rows["MX 80"][1]["id"]
    assert rows["MX 80/16"][1]["variant_of"] == main_id
    assert rows["MX 80A"][1]["variant_of"] == main_id
    assert rows["MX 80A"][0]["region"] == "Japan"
    assert "variant_of" not in rows["MX 80"][1]
    # A version msx.org alone describes is its main model's row, except what its page states
    v16, mx80 = rows["MX 80/16"][0], rows["MX 80"][0]
    assert (v16["cpu"], v16["rtc"], v16["z80_turbo"], v16["year"]) == (mx80["cpu"], mx80["rtc"], mx80["z80_turbo"], mx80["year"])
    assert (v16["region"], v16["keyboard_layout"]) == ("Spain", "QWERTY with ñ")
    assert v16["himem_addr"] is None and v16["character_set"] is None and v16["openmsx_id"] is None
    assert rows["MX 80A"][0]["rtc"] == "No"                          # openMSX has it: its own machine's data


# ── Language versions ("available in N versions": International, German, …) ──

def _page_html(body: str) -> bytes:
    return f"<html><body><div id='bodyContent'>{body}</div></body></html>".encode()


_LANG_PAGE_LIST = ("<p>It was available in 4 versions to support different keyboards:</p>"
                   "<ul><li>International</li><li>Arabic</li><li>German</li><li>Danish/Norwegian</li></ul>")


class TestLanguageVersions:
    def test_list_after_a_versions_lead_of_languages(self):
        from scraper.msxorg import language_versions
        page = _page_html(_LANG_PAGE_LIST)
        assert language_versions(page) == ["International", "Arabic", "German", "Danish/Norwegian"]

    @pytest.mark.parametrize("html", [
        "<p>It was available in 2 versions:</p><ul><li>16kB RAM</li><li>64kB RAM</li></ul>",   # not languages
        "<p>Features:</p><ul><li>German</li><li>Polish</li></ul>",                            # no versions lead
    ])
    def test_other_lists_are_not_language_versions(self, html):
        from scraper.msxorg import language_versions
        assert language_versions(_page_html(html)) == []

    @pytest.mark.parametrize("value,language,expected", [
        ("(Non-Arabic) QWERTY with variations - (Arabic) QWERTY/Arabic", "Arabic", "QWERTY/Arabic"),
        ("(Non-Arabic) QWERTY with variations - (Arabic) QWERTY/Arabic", "German", "QWERTY with variations"),
        ("(Non-Arabic) QWERTY + keypad (Arabic) QWERTY/Arabic + keypad", "Arabic", "QWERTY/Arabic + keypad"),
        ("(Non-Arabic) QWERTY + keypad (Arabic) QWERTY/Arabic + keypad", "Spanish", "QWERTY + keypad"),
        ("1985 (Polish version : 1986 - Arabic version : 1987)", "Polish", "1986"),
        ("1985 (Polish version : 1986 - Arabic version : 1987)", "German", None),
        ("256kB (versions V and T) or 64kB (other versions)", "German", None),       # not a language qualifier
    ])
    def test_language_value(self, value, language, expected):
        from scraper.msxorg import language_value
        assert language_value(value, language) == expected

    def test_slot_map_headed_for_the_language_not_one_excluding_it(self):
        from bs4 import BeautifulSoup
        from scraper.msxorg import language_slot_table
        from scraper.msxorg_series import slotmap_sections
        table = ("<table{}><tr><td></td><th>Slot 0</th><th>Slot 1</th><th>Slot 2</th><th>Slot 3</th></tr>"
                 "<tr><th>Page C000h~FFFFh</th><td rowspan='4'>Main-ROM</td><td rowspan='4'>Cartridge Slot 1</td>"
                 "<td rowspan='4'>RAM</td><td rowspan='4'>Disk ROM</td></tr><tr><th>Page 8000h~BFFFh</th></tr>"
                 "<tr><th>Page 4000h~7FFFh</th></tr><tr><th>Page 0000h~3FFFh</th></tr></table>")
        html = ("<h2><span class='mw-headline' id='Slot_Map_for_all_models_except_the_Arabic_model'>"
                "Slot Map for all models except the Arabic model</span></h2>"
                + table.format(" id='all'")
                + "<h2><span class='mw-headline' id='Slot_Map_for_the_Arabic_model'>Slot Map for the Arabic model</span></h2>"
                + table.format(" id='arabic'"))
        soup = BeautifulSoup(_page_html(html), "lxml")
        assert len(slotmap_sections(soup)) == 2
        default = soup.find("table", id="all")
        assert language_slot_table(soup, "Arabic", default).get("id") == "arabic"
        assert language_slot_table(soup, "German", default) is default

    @pytest.mark.parametrize("region,languages,expected", [
        ("Europe, Middle East", ["International", "Arabic", "German"], "Europe"),   # Arabic version: Middle East
        ("Middle East", ["International", "Arabic"], "Middle East"),               # nothing left: unchanged
        ("Europe", ["International", "German"], "Europe"),                         # Germany is not listed
    ])
    def test_main_model_region_drops_what_its_versions_cover(self, region, languages, expected):
        from scraper.msxorg import main_language_region
        assert main_language_region(region, languages) == expected

    def test_versions_are_named_by_country_tags_or_the_language(self):
        from scraper.msxorg import parse_model_page
        from scraper.aliases import LOCALISED_FIELD, VERSION_FIELD
        page = _multi_page("MX 7", "64kB", table=_LANG_PAGE_LIST,
                           extra="<tr><th>Year</th><td>1985 (Arabic version : 1987)</td></tr>")
        records = {r["model"]: r for r in parse_model_page(page, "MSX1", "Maker MX 7")}
        assert set(records) == {"MX 7", "MX 7 (Arabic)", "MX 7 (DE)", "MX 7 (DK/NO)"}
        arabic = records["MX 7 (Arabic)"]
        assert (arabic[LOCALISED_FIELD], arabic[VERSION_FIELD], arabic["year"]) == ("MX 7", True, 1987)
        assert records["MX 7 (DK/NO)"]["region"] == "Denmark, Norway"
        assert VERSION_FIELD not in records["MX 7"]

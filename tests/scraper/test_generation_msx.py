"""Tests for scraper/generation_msx.py (map file, listing parser, matching) — no network."""
from __future__ import annotations

import json

import pytest

from scraper.aliases import AliasLUT, load_aliases
from scraper.generation_msx import (
    MATCH_KINDS,
    GmsxEntry,
    listing_url,
    load_links,
    match_models,
    merge_with_manual,
    parse_listing,
    run,
    write_links,
)

BASE = "https://generation-msx.nl"


def _row(path: str, name: str, maker: str) -> str:
    return (f'<tr><td><a href="{path}"><img></a> <a href="{path}">{name}</a> description</td>'
            f"<td>{maker}</td><td>MSX 1</td></tr>")


def _page(rows: list[str], last_page: int = 1) -> str:
    pager = "".join(f'<a href="{BASE}/hardware/result?product_type%5B0%5D=MSX%201&amp;page={n}">{n}</a>'
                    for n in range(2, last_page + 1))
    return (f"<html><body><table><tr><th>Name</th><th>Manufacturer</th><th>Product type</th></tr>"
            f"{''.join(rows)}</table>{pager}</body></html>")


# ── Listing pages ───────────────────────────────────────────────────────────

def test_parse_listing_reads_rows_and_last_page():
    html = _page([_row("/hardware/sony/hb-75p/1227", "HB-75P", "Sony Corporation")], last_page=3)
    entries, last = parse_listing(html)
    assert entries == [GmsxEntry(url=f"{BASE}/hardware/sony/hb-75p/1227", name="HB-75P", brand="Sony Corporation")]
    assert last == 3


def test_run_crawls_every_page_and_writes_the_map(tmp_path):
    pages = {
        listing_url("MSX 1", 1): _page([_row("/hardware/sony/hb-10/1", "HB-10", "Sony")], last_page=2),
        listing_url("MSX 1", 2): _page([_row("/hardware/sony/hb-75p/2", "HB-75P", "Sony")], last_page=2),
    }
    fetched: list[str] = []

    def fetch(url: str) -> str:
        fetched.append(url)
        return pages.get(url, _page([]))

    data_js = tmp_path / "data.js"
    data_js.write_text("window.MSX_DATA = " + json.dumps({
        "columns": [{"key": "brand"}, {"key": "model"}],
        "models": [{"id": 7, "values": ["Sony", "HB-75P"]}, {"id": 8, "values": ["Maker", "Z-1"]}],
    }) + ";", encoding="utf-8")
    out = tmp_path / "generation-msx.json"
    counts = run(out, data_js, tmp_path / "no-aliases.json", fetch, delay=0)
    assert listing_url("MSX 1", 2) in fetched
    links = load_links(out)
    assert links[7]["url"] == f"{BASE}/hardware/sony/hb-75p/2" and links[7]["match"] == "exact"
    assert 8 not in links
    assert counts["unlinked"] == 1


# ── Matching ──────────────────────────────────────────────────────────────

def _e(name: str, maker: str = "Maker", n: int = 1) -> GmsxEntry:
    return GmsxEntry(url=f"{BASE}/hardware/x/{name.lower()}/{n}", name=name, brand=maker)


def test_exact_variant_and_family():
    entries = [_e("MX-1", n=1), _e("MPC-25F (WAVY25)", "SANYO Electric Co., Ltd.", n=2), _e("VG 8235", "Philips", n=3)]
    got = match_models([(1, "Maker", "MX-1"), (2, "Sanyo", "MPC-25F"), (3, "Philips", "VG 8235/00"), (4, "X", "Nope")],
                       entries, AliasLUT())
    assert {k: v["match"] for k, v in got.items()} == {1: "exact", 2: "variant", 3: "family"}
    assert got[2]["url"].endswith("/2") and got[3]["url"].endswith("/3")


def test_exact_beats_a_longer_name_sharing_the_prefix():
    entries = [_e("FS-A1GT", "Panasonic", 1), _e("FS-A1GT DO&do", "Panasonic", 2)]
    got = match_models([(1, "Panasonic", "FS-A1GT")], entries, AliasLUT())
    assert got[1]["url"].endswith("/1") and got[1]["match"] == "exact"


def test_same_name_is_resolved_by_brand_or_left_unlinked():
    entries = [_e("DPC-200", "Telemática/Talent", 1), _e("DPC-200", "Fenner", 2)]
    got = match_models([(1, "Fenner", "DPC-200"), (2, "Olympia", "DPC-200")], entries, AliasLUT())
    assert got[1]["url"].endswith("/2")
    assert 2 not in got                        # ambiguous: never guessed


def test_country_tags_are_canonicalised_through_the_aliases(tmp_path):
    aliases = tmp_path / "aliases.json"
    aliases.write_text(json.dumps({"variant_tag": {"GB": ["UK"]}}), encoding="utf-8")
    got = match_models([(1, "Panasonic", "CF-2700 (GB)")], [_e("CF-2700(UK)", "Panasonic")], load_aliases(aliases))
    assert got[1]["match"] == "exact"


def test_manual_entries_survive_regeneration():
    generated = {1: {"model": "A", "url": f"{BASE}/a/1", "match": "exact"}}
    existing = {1: {"model": "A", "url": f"{BASE}/a/9", "match": "manual"},
                2: {"model": "B", "url": None, "match": "manual"},
                3: {"model": "C", "url": f"{BASE}/c/3", "match": "exact"}}
    merged = merge_with_manual(generated, existing)
    assert merged[1]["url"].endswith("/9") and merged[2]["url"] is None
    assert 3 not in merged                     # generated entries are replaced, not kept


# ── Map file ──────────────────────────────────────────────────────────────

def test_write_then_load_round_trips(tmp_path):
    path = tmp_path / "m.json"
    links = {12: {"model": "A", "url": f"{BASE}/a/1", "match": "exact"}, 3: {"model": "B", "url": None, "match": "manual"}}
    write_links(path, links)
    assert load_links(path) == links
    assert list(json.loads(path.read_text(encoding="utf-8"))["links"]) == ["3", "12"]


@pytest.mark.parametrize("links", [
    {"x": {"url": f"{BASE}/a", "match": "exact"}},          # not an id
    {"1": {"url": "http://insecure", "match": "exact"}},      # not https
    {"1": {"url": f"{BASE}/a", "match": "guess"}},            # unknown match kind
])
def test_load_rejects_malformed(tmp_path, links):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"links": links}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_links(path)


def test_committed_map_is_valid():
    from scraper.generation_msx import GENERATION_MSX_PATH
    links = load_links(GENERATION_MSX_PATH)
    assert links, "the committed map ships links"
    assert {e["match"] for e in links.values()} <= set(MATCH_KINDS)


# ── Build ─────────────────────────────────────────────────────────────────

def test_build_links_models_from_the_map(tmp_path, monkeypatch):
    import scraper.build as build_module
    from scraper.build import build
    from scraper.columns import active_columns

    raw = [{"brand": "Sony", "model": "HB-75P", "generation": "MSX1"}]
    (tmp_path / "openmsx.json").write_text(json.dumps(raw))
    (tmp_path / "msxorg.json").write_text(json.dumps([]))
    (tmp_path / "registry.json").write_text(json.dumps({"version": 2, "models": {"sony|hb-75p": 5},
                                                        "retired_models": [], "next_model_id": 6}))
    gmsx = tmp_path / "generation-msx.json"
    write_links(gmsx, {5: {"model": "Sony HB-75P", "url": f"{BASE}/hardware/unknown/hb-75p/1227", "match": "exact"}})
    monkeypatch.setattr(build_module, "GENERATION_MSX_PATH", gmsx)
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js")
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    col = next(c for c in active_columns() if c.link_icon)
    [model] = data["models"]
    assert model["links"][col.key] == f"{BASE}/hardware/unknown/hb-75p/1227"
    keys = [c["key"] for c in data["columns"]]
    assert model["values"][keys.index(col.key)] == model["values"][keys.index("model")]   # sorts by model
    assert col.key not in model.get("tooltips", {})          # an exact page: the link tooltip is the URL


def test_build_marks_family_links_in_the_tooltip(tmp_path, monkeypatch):
    import scraper.build as build_module
    from scraper.build import build
    from scraper.columns import active_columns

    raw = [{"brand": "Philips", "model": "VG 8235/00", "generation": "MSX2"}]
    (tmp_path / "openmsx.json").write_text(json.dumps(raw))
    (tmp_path / "msxorg.json").write_text(json.dumps([]))
    (tmp_path / "registry.json").write_text(json.dumps({"version": 2, "models": {"philips|vg 8235/00": 5},
                                                        "retired_models": [], "next_model_id": 6}))
    url = f"{BASE}/hardware/philips/vg-8235/583"
    gmsx = tmp_path / "generation-msx.json"
    write_links(gmsx, {5: {"model": "Philips VG 8235/00", "url": url, "match": "family"}})
    monkeypatch.setattr(build_module, "GENERATION_MSX_PATH", gmsx)
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js")
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    [model] = json.loads(text[text.index("{"):text.rindex(";")])["models"]
    key = next(c for c in active_columns() if c.link_icon).key
    assert model["links"][key] == url
    assert model["tooltips"][key] == f"{url} (family)"

"""Tests for families: msx.org text relations (scraper/msxorg.py) and grouping (scraper/families.py)."""
from __future__ import annotations

import json

import pytest

from scraper.families import (
    FAMILY_LINKS_FIELD,
    SERIES_FIELD,
    VARIANT_NAMES_FIELD,
    base_name,
    compute_families,
    page_url,
    write_families,
)
from scraper.msxorg import family_links, variant_list_names, variant_table_names


def _link(title: str) -> str:
    return f'<a href="/wiki/{title.replace(" ", "_")}">{title}</a>'


def _page(*nodes: str) -> bytes:
    return ("<html><body><div id='bodyContent'>" + "".join(nodes) + "</div></body></html>").encode()


def _titles(nodes: list[str], page: str = "Maker MX-1") -> list[str]:
    return [link["title"] for link in family_links(_page(*nodes), page)]


# ── Text relations ────────────────────────────────────────────────────────

class TestFamilyLinks:
    @pytest.mark.parametrize("sentence,expected", [
        (f"This machine has been localised for the European market - see {_link('Maker MX-1 (GE)')} and {_link('Maker MX-1 (UK)')} .",
         ["Maker MX-1 (GE)", "Maker MX-1 (UK)"]),
        (f"There are also specific versions for Great Britain and Germany - see {_link('Maker MX-1B')} .", ["Maker MX-1B"]),
        (f"There is also a special version of this computer, see {_link('Other SX-1')} .", ["Other SX-1"]),
        (f"Hitachi also released a downgraded version, see {_link('Maker MX-1E')} .", ["Maker MX-1E"]),
        (f"The machine was commercialy released under the Goldstar brand - see {_link('Other MX-1')} .", ["Other MX-1"]),
        (f"It was possible to buy it under another trademark: see {_link('Other CX-5')} .", ["Other CX-5"]),
        (f"This machine was also sold in Italy as the {_link('Phonola MX-1')} .", ["Phonola MX-1"]),
        (f"For other European versions, see {_link('Maker MX-1E')} , {_link('Maker MX-1F')} .", ["Maker MX-1E", "Maker MX-1F"]),
    ])
    def test_qualified_relations(self, sentence, expected):
        assert _titles([f"<p>{sentence}</p>"]) == expected

    @pytest.mark.parametrize("sentence", [
        f"See Disk 2 of {_link('Maker MX-9')}",
        f"The MX-1S has same board as the {_link('Maker MX-1D')} . (See this thread for more info.)",
        f"It fixed some issues of the previous model {_link('Maker MX-0')} (see Specifications section).",
        f"The second version has a keyboard with a Spanish layout, see {_link('Other NMS-1')} for the standard one.",
        f"Like the special version (see below), it was used with a {_link('Maker MX-2')} .",
        f"For the technical details see {_link('Maker MX-2')} .",                       # no relation stated
        f"The {_link('Maker MX-2')} is a different computer, see the manual.",          # link before "see"
    ])
    def test_unqualified_or_unrelated_see_is_ignored(self, sentence):
        assert _titles([f"<p>{sentence}</p>"]) == []

    def test_list_items_under_a_localisation_lead(self):
        nodes = ["<p>This model has been localised for</p>",
                 f"<ul><li>Germany - see {_link('Maker MX-1D')}</li><li>Italy: see {_link('Other MX-1I')}</li></ul>"]
        links = family_links(_page(*nodes), "Maker MX-1")
        assert [link["title"] for link in links] == ["Maker MX-1D", "Other MX-1I"]
        assert all(link["directed"] for link in links)

    def test_list_items_without_such_a_lead_are_ignored(self):
        nodes = ["<p>Notes:</p>", f"<ul><li>Germany - see {_link('Maker MX-1D')}</li></ul>"]
        assert _titles(nodes) == []

    def test_series_category_links_are_not_models(self):
        sentence = ("The MX-1P is the adaptation for the European market of the MX-1 - see "
                    "<a href='/wiki/Category:Maker_MX-1'>MX-1 series</a> for the technical details")
        assert _titles([f"<p>{sentence}</p>"], "Maker MX-1P") == []


def test_variant_table_names_reads_product_and_version_tables():
    page = ("<html><body>"
            "<table><tr><th>Version</th><th>RAM</th></tr><tr><td>HC-90</td><td>64kB</td></tr>"
            "<tr><td>HC-90(A)</td><td>64kB</td></tr></table>"
            "<table><tr><th>Brand</th><td>Victor</td></tr><tr><th>Model</th><td>HC-90</td></tr></table>"
            "</body></html>").encode()
    assert variant_table_names(page) == ["HC-90", "HC-90(A)"]


def test_variant_list_names_reads_a_list_of_versions():
    page = _page(
        "<p>Four models were produced, with the keyboard as difference:</p>",
        "<ul><li>MX 80/00 for the Dutch market, QWERTY</li><li>MX 80/16 for the Spanish market</li>"
        "<li>MX 80/19 for the French market, AZERTY</li></ul>",
        "<ul><li>MXA: Australian market</li><li>MXU: United States market</li><li>Other text</li></ul>",
    )
    assert variant_list_names(page, ["MX 80"]) == ["MX 80/00", "MX 80/16", "MX 80/19"]
    assert variant_list_names(page, ["MX"]) == ["MXA", "MXU"]


@pytest.mark.parametrize("items", [
    ["<li>MX 80/00 Service Manual</li>", "<li>Photos</li>"],     # one version-like item: a download, not a list
    ["<li>MX 800 is the successor</li>", "<li>MX 8000</li>"],    # longer model numbers are other models
])
def test_variant_list_names_ignores_lists_that_are_not_versions(items):
    assert variant_list_names(_page("<ul>" + "".join(items) + "</ul>"), ["MX 80"]) == []


# ── Grouping ──────────────────────────────────────────────────────────────

def _row(i: int, maker: str, model: str, year: int | None = None, **extra) -> dict:
    return {"_id": i, "brand": maker, "model": model, "year": year,
            "msxorg_title": extra.pop("title", f"{maker} {model}"), **extra}


def _directed(title: str) -> dict:
    return {"title": title, "via": "see", "directed": True}


class TestComputeFamilies:
    def test_same_brand_is_series_other_brands_rebrand(self):
        rows = [
            _row(1, "Maker", "MX-1", 1985, **{FAMILY_LINKS_FIELD: [_directed("Maker MX-1D"), _directed("Other OX-1")]}),
            _row(2, "Maker", "MX-1D", 1986),
            _row(3, "Other", "OX-1", 1986),
            _row(4, "Lone", "LX-1"),
        ]
        fam = compute_families(rows, {})
        series, rebrand = fam.value_of("series"), fam.value_of("rebrand")
        assert {series[1].name, series[2].name} == {"MX-1"} and 3 not in series and 4 not in series
        assert {rebrand[i].name for i in (1, 2, 3)} == {"M. MX-1"}              # base included, maker as initial
        assert rebrand[3].url == page_url("Maker MX-1")
        assert 4 not in rebrand

    def test_series_page_names_and_links_the_series(self):
        rows = [_row(1, "Sony", "HB-75", 1985, **{SERIES_FIELD: "Sony_HB-75"}),
                _row(2, "Sony", "HB-75P", 1985, **{SERIES_FIELD: "Sony_HB-75"})]
        [group] = compute_families(rows, {}).series
        assert group.name == "HB-75" and group.url == page_url("Category:Sony_HB-75")

    def test_base_is_the_model_nobody_derives_from_then_earliest(self):
        rows = [_row(1, "Maker", "MX-2", 1990, _adapted_from={"title": "Maker MX-1"}),
                _row(2, "Maker", "MX-1", 1995)]
        [group] = compute_families(rows, {}).series
        assert group.root == 2                       # MX-2 is an adaptation of MX-1, despite the earlier year
        rows = [_row(1, "Maker", "MX-1", 1990, title="Maker MX"), _row(2, "Maker", "MX-1F", 1986, title="Maker MX")]
        assert compute_families(rows, {}).series[0].root == 2   # same page, no direction: earliest year

    def test_series_name_drops_a_regional_tag_or_revision(self):
        assert base_name("V-20 (JP)") == "V-20" and base_name("HB-F500 (v2)") == "HB-F500"
        assert base_name("PX-7(HB)") == "PX-7" and base_name("CX5MII/128") == "CX5MII/128"

    def test_variant_list_names_relate_models(self):
        rows = [_row(1, "Philips", "NMS 80", 1987, **{VARIANT_NAMES_FIELD: ["NMS 80/16"]}),
                _row(2, "Philips", "NMS 80/16", 1987, title=None)]
        assert set(compute_families(rows, {}).value_of("series")) == {1, 2}

    def test_link_shares_and_variant_tables_relate_models(self):
        rows = [_row(1, "Philips", "VG-8020", 1984, **{VARIANT_NAMES_FIELD: ["VG-8020/00"]}),
                _row(2, "Philips", "VG 8020/00", 1984, title=None),
                _row(3, "Philips", "VG 8020/19", 1984, title=None)]
        fam = compute_families(rows, {"philips|vg 8020/19": "philips|vg-8020"})
        assert set(fam.value_of("series")) == {1, 2, 3}


@pytest.mark.parametrize("maker,model,expected", [
    ("Daewoo", "DPC-200", "D. DPC-200"), ("panasonic", "FS-A1", "P. FS-A1"), ("", "MX-1", "MX-1"), (None, "MX-1", "MX-1")])
def test_rebrand_name_uses_the_brand_initial(maker, model, expected):
    from scraper.families import rebrand_name
    assert rebrand_name(maker, model) == expected


def test_write_families_lists_groups_and_relations(tmp_path):
    rows = [_row(1, "Maker", "MX-1", 1985, **{FAMILY_LINKS_FIELD: [_directed("Other OX-1")]}), _row(2, "Other", "OX-1")]
    fam = compute_families(rows, {})
    path = tmp_path / "families.json"
    write_families(path, fam, {r["_id"]: r for r in rows})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["rebrands"][0]["name"] == "M. MX-1"
    assert {m["id"] for m in data["rebrands"][0]["members"]} == {1, 2}
    assert data["relations"] == [{"model": "Other OX-1", "of": "Maker MX-1", "signal": "text: see"}]


def test_build_sets_values_and_links_but_writes_no_file_unless_asked(tmp_path):
    from scraper.build import build
    (tmp_path / "openmsx.json").write_text(json.dumps([]))
    (tmp_path / "msxorg.json").write_text(json.dumps([
        _row(0, "Maker", "MX-1", 1985, generation="MSX1", **{FAMILY_LINKS_FIELD: [_directed("Other OX-1")]}) | {"_id": None},
        {"brand": "Other", "model": "OX-1", "generation": "MSX1", "msxorg_title": "Other OX-1"},
    ]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json", local_path=tmp_path / "l.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js")
    assert not (tmp_path / "families.json").exists()
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    keys = [c["key"] for c in data["columns"]]
    rows = {m["values"][keys.index("model")]: m for m in data["models"]}
    assert rows["OX-1"]["values"][keys.index("family_rebrand")] == "M. MX-1"
    assert rows["OX-1"]["links"]["family_rebrand"] == page_url("Maker MX-1")
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json", local_path=tmp_path / "l.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js",
          families_path=tmp_path / "families.json")
    assert json.loads((tmp_path / "families.json").read_text(encoding="utf-8"))["rebrands"]

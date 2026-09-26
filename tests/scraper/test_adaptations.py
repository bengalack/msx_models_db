"""Tests for adaptations: fill a model's blanks from the model it was adapted from.

Design: .claude/artifacts/planning/2026-09-26-adaptations-design.md
Fixtures are inline and owned by the tests.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from scraper.msxorg import ADAPTED_FROM_FIELD, adapted_from, fill_from_donors, parse_model_page
from scraper.revisions import REVISION_FIELD


def _body(html: str) -> BeautifulSoup:
    return BeautifulSoup(f'<html><body><div id="bodyContent"><p>{html}</p></div></body></html>', "lxml")


def _link(slug: str, text: str | None = None) -> str:
    return f'<a href="/wiki/{slug}">{text or slug.replace("_", " ")}</a>'


# ── Recognising the donor ───────────────────────────────────────────────────

class TestAdaptedFrom:
    @pytest.mark.parametrize("html,model,brand,expected", [
        (f"The Fenner FPC-900 is the adaptation of the {_link('Sanyo_MPC-25FD', 'Sanyo MPC-25FD')} computer, "
         "also known as Wavy 25, for the Italian market.", "FPC-900", "Fenner", ("Sanyo MPC-25FD", 1)),
        (f"The {_link('AVT')} DPC-200 is the adaptation for Europe (mostly The Netherlands) of the "
         f"{_link('Daewoo_DPC-200', 'Daewoo DPC-200')} .", "DPC-200", "AVT", ("Daewoo DPC-200", 1)),
        (f"The HB-F700B is an adaptation of the {_link('Sony_HB-F500', 'HB-F500')} for the British market.",
         "HB-F700B", "Sony", ("Sony HB-F500", 1)),
        (f"It's the adaptation for the French market of the {_link('Yamaha_YIS-503', 'YIS-503')} .",
         "YIS-503F", "Yamaha", ("Yamaha YIS-503", 1)),
        (f"This computer is the adaptation for Thailand of the very popular {_link('Sakhr_AX-170', 'Sakhr AX-170')}.",
         "AX-170 (TH)", "Sakhr", ("Sakhr AX-170", 1)),
        (f"The AX-200 is the {_link('Yamaha_YIS-503II', 'Yamaha YIS-503II')} adapted for Arabic countries.",
         "AX-200", "Sakhr", ("Yamaha YIS-503II", 1)),
        (f"The Sony HB-55P is the adaptation for the European market of the second version of the "
         f"{_link('Sony_HB-55', 'HB-55')} - see {_link('Category:Sony_HB-55', 'HB-55 series')}",
         "HB-55P", "Sony", ("Sony HB-55", 2)),
        (f"The HB-F500F is the adaptation of the first version of {_link('Sony_HB-F500', 'HB-F500')} for France",
         "HB-F500F", "Sony", ("Sony HB-F500", 1)),
        (f"The Sanyo PHC-28P (P for PAL version) is the adaptation of the {_link('Sanyo_MPC-5', 'MPC-5')} for Europe.",
         "PHC-28P (GE)", "Sanyo", ("Sanyo MPC-5", 1)),
        (f"The Olympia DPC-200 is one of the two adaptations for Italy and Spain of the "
         f"{_link('Daewoo_DPC-200', 'Daewoo DPC-200')}.", "DPC-200", "Olympia", ("Daewoo DPC-200", 1)),
    ])
    def test_forward_phrasings(self, html, model, brand, expected):
        found = adapted_from(_body(html), model, brand)
        assert (found["title"], found["revision"]) == expected

    @pytest.mark.parametrize("html,model,brand", [
        # reverse direction: this page is the donor
        (f"This computer has been adapted for the Spanish market - see {_link('Mitsubishi_ML-G1', 'ML-G1')} .",
         "ML-G10", "Mitsubishi"),
        # a prototype of the linked model is what was adapted, not the model itself
        (f"The Sanyo MPC-2300 is the adaptation of the special MSX2 prototype version for the "
         f"{_link('Sanyo_MPC-2', 'MPC-2')} MSX1 computer, for the Soviet Union.", "MPC-2300", "Sanyo"),
        # a series category is not a model
        (f"The X-1 is the adaptation of the {_link('Category:Sony_HB-75', 'HB-75 series')}.", "X-1", "Sony"),
        # someone else's adaptation
        (f"Attacco a New York which is the Italian adaptation of {_link('Objetivo', 'Objetivo:Nueva York')}.",
         "NMS 800", "Philips"),
        # no link
        ("The Wandy DPC-200 is the adaptation for Thailand of the Daewoo DPC-200.", "DPC-200", "Wandy"),
    ])
    def test_not_a_donor(self, html, model, brand):
        assert adapted_from(_body(html), model, brand) is None

    def test_parse_model_page_records_the_donor(self):
        page = (
            '<html><body><div id="bodyContent">'
            '<table class="wikitable"><tr><th>Brand</th><td>Fenner</td></tr>'
            '<tr><th>Model</th><td>FPC-900</td></tr></table>'
            f"<p>The Fenner FPC-900 is the adaptation of the {_link('Sanyo_MPC-25FD', 'Sanyo MPC-25FD')} computer.</p>"
            "</div></body></html>"
        ).encode()
        [record] = parse_model_page(page, "MSX2", "Fenner FPC-900")
        assert record[ADAPTED_FROM_FIELD] == {"title": "Sanyo MPC-25FD", "revision": 1}


# ── Filling the blanks ──────────────────────────────────────────────────────

def _slots(value: str) -> dict:
    return {f"slotmap_{ms}_{ss}_{p}": value for ms in range(4) for ss in range(4) for p in range(4)}


def _rec(title: str, model: str, donor: str | None = None, revision: int = 1, **fields) -> dict:
    record = {"manufacturer": title.split()[0], "model": model, "msxorg_title": title, **fields}
    if donor:
        record[ADAPTED_FROM_FIELD] = {"title": donor, "revision": revision}
    return record


class TestFillFromDonors:
    def test_blanks_filled_own_values_kept(self):
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", vdp="V9938", vram_kb=128, main_ram_kb=64, engine_raw="S3527")
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD", main_ram_kb=128)
        fill_from_donors([donor, adaptation], load=lambda title: None)
        assert adaptation["vdp"] == "V9938"
        assert adaptation["vram_kb"] == 128
        assert adaptation["engine_raw"] == "S3527"
        assert adaptation["main_ram_kb"] == 128        # its own value

    def test_identity_emulator_and_bios_fields_are_never_copied(self):
        """The donor's emulator machine and its BIOS-derived character set / keyboard
        type describe the donor's own ROM, not the adaptation."""
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", generation="MSX2", openmsx_id="Sanyo_MPC-25FD",
                     character_set="Japanese", keyboard_type="Japanese")
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD")
        fill_from_donors([donor, adaptation], load=lambda title: None)
        for field in ("generation", "openmsx_id", "character_set", "keyboard_type"):
            assert field not in adaptation, field

    def test_every_other_missing_field_is_filled(self):
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", region="Japan", year=1985, keyboard_layout="QWERTY/JIS",
                     himem_addr="0xDF94", cpu="Z80")
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD")
        fill_from_donors([donor, adaptation], load=lambda title: None)
        assert (adaptation["region"], adaptation["year"], adaptation["keyboard_layout"],
                adaptation["himem_addr"], adaptation["cpu"]) == ("Japan", 1985, "QWERTY/JIS", "0xDF94", "Z80")

    def test_own_market_values_are_kept(self):
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", region="Japan", year=1985)
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD", region="Italy", year=1986)
        fill_from_donors([donor, adaptation], load=lambda title: None)
        assert (adaptation["region"], adaptation["year"]) == ("Italy", 1986)
        assert (adaptation["manufacturer"], adaptation["model"], adaptation["msxorg_title"]) == (
            "Fenner", "FPC-900", "Fenner FPC-900")

    def test_slot_map_copied_as_a_unit_when_absent(self):
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", mapper="Yes", **_slots("MAIN"))
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD")
        fill_from_donors([donor, adaptation], load=lambda title: None)
        assert {k: v for k, v in adaptation.items() if k.startswith("slotmap_")} == _slots("MAIN")
        assert adaptation["mapper"] == "Yes"

    def test_own_slot_map_is_kept_whole(self):
        donor = _rec("Sanyo MPC-25FD", "MPC-25FD", mapper="Yes", **_slots("MAIN"))
        own = _slots("RAM")
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD", mapper="No", **own)
        fill_from_donors([donor, adaptation], load=lambda title: None)
        assert {k: v for k, v in adaptation.items() if k.startswith("slotmap_")} == own
        assert adaptation["mapper"] == "No"

    def test_nesting(self):
        origin = _rec("Daewoo DPC-200", "DPC-200", vdp="TMS9129", **_slots("MAIN"))
        middle = _rec("Daewoo DPC-200 (FR)", "DPC-200 (FR)", "Daewoo DPC-200")
        outer = _rec("AVT DPC-200", "DPC-200", "Daewoo DPC-200 (FR)")
        fill_from_donors([outer, middle, origin], load=lambda title: None)   # order must not matter
        assert outer["vdp"] == middle["vdp"] == "TMS9129"
        assert outer["slotmap_0_0_0"] == "MAIN"

    def test_donor_revision(self):
        base = _rec("Sony HB-55", "HB-55", vdp="TMS9918A")
        v2 = _rec("Sony HB-55", "HB-55 (v2)", vdp="TMS9929A", **{REVISION_FIELD: 2})
        adaptation = _rec("Sony HB-55P", "HB-55P", "Sony HB-55", revision=2)
        fill_from_donors([base, v2, adaptation], load=lambda title: None)
        assert adaptation["vdp"] == "TMS9929A"

    def test_missing_revision_falls_back_to_the_base(self):
        base = _rec("Sony HB-55", "HB-55", vdp="TMS9918A")
        adaptation = _rec("Sony HB-55P", "HB-55P", "Sony HB-55", revision=2)
        fill_from_donors([base, adaptation], load=lambda title: None)
        assert adaptation["vdp"] == "TMS9918A"

    def test_cycle_is_safe(self):
        a = _rec("Mitsubishi ML-G1", "ML-G1", "Mitsubishi ML-G10", vdp="V9938")
        b = _rec("Mitsubishi ML-G10", "ML-G10", "Mitsubishi ML-G1", vram_kb=128)
        fill_from_donors([a, b], load=lambda title: None)
        assert a["vram_kb"] == 128 and b["vdp"] == "V9938"

    def test_donor_outside_the_scrape_is_loaded(self):
        requested = []

        def load(title):
            requested.append(title)
            return [_rec("Sanyo MPC-25FD", "MPC-25FD", vdp="V9938")]

        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD")
        fill_from_donors([adaptation], load=load)
        assert requested == ["Sanyo MPC-25FD"]
        assert adaptation["vdp"] == "V9938"

    def test_missing_donor_leaves_the_record_alone(self):
        adaptation = _rec("Fenner FPC-900", "FPC-900", "Sanyo MPC-25FD", main_ram_kb=128)
        before = dict(adaptation)
        fill_from_donors([adaptation], load=lambda title: None)
        assert adaptation == before


# ── End to end: filled after the merge, from the donor's final row ──────────

def test_build_fills_from_the_donors_merged_row(tmp_path):
    """Fenner FPC-900 gets exactly the slot map the grid shows for Sanyo MPC-25FD,
    openMSX's cells included (they win the donor's own merge)."""
    import json
    from scraper.build import build

    msxorg_donor = {"manufacturer": "Sanyo", "model": "MPC-25FD", "generation": "MSX2",
                    "msxorg_title": "Sanyo MPC-25FD", **_slots("MAIN"), "slotmap_3_1_0": "DSK*"}
    openmsx_donor = {"manufacturer": "Sanyo", "model": "MPC-25FD", "generation": "MSX2",
                     "openmsx_id": "Sanyo_MPC-25FD", **_slots("MAIN"), "slotmap_3_1_0": "DSK"}
    adaptation = {"manufacturer": "Fenner", "model": "FPC-900", "generation": "MSX2",
                  "msxorg_title": "Fenner FPC-900",
                  ADAPTED_FROM_FIELD: {"title": "Sanyo MPC-25FD", "revision": 1}}
    (tmp_path / "openmsx.json").write_text(json.dumps([openmsx_donor]))
    (tmp_path / "msxorg.json").write_text(json.dumps([msxorg_donor, adaptation]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
          local_path=tmp_path / "local.json", registry_path=tmp_path / "registry.json",
          output_path=tmp_path / "data.js")

    content = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(content[content.index("{"):content.rindex(";")])
    keys = [c["key"] for c in data["columns"]]
    rows = {dict(zip(keys, m["values"]))["model"]: dict(zip(keys, m["values"])) for m in data["models"]}
    slot_keys = [k for k in keys if k.startswith("slotmap_")]
    assert [rows["FPC-900"][k] for k in slot_keys] == [rows["MPC-25FD"][k] for k in slot_keys]
    assert rows["FPC-900"]["slotmap_3_1_0"] == "DSK"

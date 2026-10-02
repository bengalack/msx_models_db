"""Tests for per-cell slot map tooltip details (scraper/slotmap_details.py + msx.org capture + build)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scraper.msxorg_slotmap import _classify_cell_text, parse_slotmap_from_soup
from lxml import etree

from scraper.slotmap import extract_slotmap
from scraper.slotmap_details import SLOT_DEVICES_FIELD, SLOT_TEXT_FIELD, slot_details, text_detail_labels
from scraper.slotmap_lut import compact_lut, load_slotmap_lut

STARTER_LUT = Path("data/slotmap-lut.json")


def _one_cell_page(cell_html: str) -> BeautifulSoup:
    """A page whose non-expanded slot 3 holds *cell_html* on all four pages."""
    return BeautifulSoup(f"""<html><body><h2><span id="Slot_Map" class="mw-headline">Slot Map</span></h2><table>
<tr><td></td><th>Slot 0</th><th>Slot 1</th><th>Slot 2</th><th>Slot 3</th></tr>
<tr><th>Page C000h~FFFFh</th><td rowspan="4">Main-ROM</td>
  <td rowspan="4">Cartridge Slot 1</td><td rowspan="4">Cartridge Slot 2</td>
  <td rowspan="4">{cell_html}</td></tr>
<tr><th>Page 8000h~BFFFh</th></tr>
<tr><th>Page 4000h~7FFFh</th></tr>
<tr><th>Page 0000h~3FFFh</th></tr>
</table></body></html>""", "lxml")


# ── msx.org capture ───────────────────────────────────────────────────────

def test_parser_keeps_each_device_cells_label_and_text():
    texts: dict[str, list[str]] = {}
    result = parse_slotmap_from_soup(_one_cell_page("Painter\n  ROM"), "Maker MX-1", texts)
    label = _classify_cell_text("Painter ROM")
    for p in range(4):
        assert result[f"slotmap_3_0_{p}"] == label
        assert texts[f"slotmap_3_0_{p}"] == [label, "Painter ROM"]     # whitespace collapsed
    assert texts["slotmap_0_0_0"][1] == "Main-ROM"


def test_parser_without_texts_still_works():
    assert parse_slotmap_from_soup(_one_cell_page("Painter ROM"), "Maker MX-1") is not None


@pytest.mark.parametrize("text", ["Disk-ROM", "Disk ROM", "Disk - ROM"])
def test_disk_rom_spellings_classify_alike(text):
    assert _classify_cell_text(text) == _classify_cell_text("Disk ROM")


# ── Rules ─────────────────────────────────────────────────────────────────

def test_text_detail_labels_reads_the_rule_flag():
    rules = [{"abbr": "FW", "detail": "text"}, {"abbr": "DSK"}, {"abbr": "FW", "detail": "text"}]
    assert text_detail_labels(rules) == {"FW"}


def test_lut_rejects_an_unknown_detail_kind(tmp_path):
    lut = tmp_path / "lut.json"
    lut.write_text(json.dumps([{"element": "ROM", "id_pattern": "x", "abbr": "FW", "tooltip": "Firmware",
                                "detail": "bogus"}]))
    with pytest.raises(ValueError, match="detail"):
        load_slotmap_lut(lut)


def test_committed_lut_detail_flags_are_valid():
    rules = load_slotmap_lut(STARTER_LUT)
    assert text_detail_labels(rules) <= set(compact_lut(rules))


def _rule(abbr: str, tooltip: str, element: str = "ROM", id_pattern: str | None = None, detail: str | None = None) -> dict:
    rule = {"element": element, "id_pattern": id_pattern, "abbr": abbr, "tooltip": tooltip}
    return rule | ({"detail": detail} if detail else {})


class TestSlotDetails:
    TIPS = {"FW": "Firmware", "DSK": "Disk ROM"}

    def _rules(self, fw: str | None = None, dsk: str | None = None) -> list[dict]:
        return [_rule("DSK", "Disk ROM", element="WD2793|TC8566AF", detail=dsk),
                _rule("DSK", "Disk ROM", element="ROM", id_pattern="disk"),
                _rule("FW", "Firmware", detail=fw)]

    def _model(self, **cells) -> dict:
        return {SLOT_TEXT_FIELD: {k: list(v) for k, v in cells.items()},
                **{k: v[0] for k, v in cells.items()}}

    def test_text_of_a_flagged_label_becomes_the_detail(self):
        model = self._model(slotmap_3_0_1=("FW", "Painter ROM"))
        assert slot_details(model, self._rules(fw="text"), self.TIPS) == {"slotmap_3_0_1": "Painter ROM"}

    def test_unflagged_labels_get_none(self):
        model = self._model(slotmap_3_0_1=("FW", "Painter ROM"))
        assert slot_details(model, self._rules(), self.TIPS) == {}

    def test_text_repeating_the_tooltip_adds_nothing(self):
        model = self._model(slotmap_3_0_1=("DSK", "Disk-ROM"))
        assert slot_details(model, self._rules(dsk="text"), self.TIPS) == {}

    def test_cell_another_source_relabelled_borrows_no_text(self):
        model = self._model(slotmap_3_0_1=("FW", "Painter ROM"))
        model["slotmap_3_0_1"] = "DSK"            # openMSX put something else there
        assert slot_details(model, self._rules(fw="text", dsk="text"), self.TIPS) == {}

    def test_a_trailing_footnote_mark_is_dropped(self):
        model = self._model(slotmap_3_1_1=("FW", "Network*"))
        assert slot_details(model, self._rules(fw="text"), self.TIPS) == {"slotmap_3_1_1": "Network"}

    def test_model_without_source_cells(self):
        assert slot_details({}, self._rules(fw="text", dsk="element"), self.TIPS) == {}

    # ── "element" ──

    def _devices(self, **cells) -> dict:
        return {SLOT_DEVICES_FIELD: {k: [tag, eid] for k, (_, tag, eid) in cells.items()},
                **{k: v[0] for k, v in cells.items()}}

    def test_element_of_the_flagged_rule_becomes_the_detail(self):
        model = self._devices(slotmap_3_2_1=("DSK", "WD2793", "Memory Mapped FDC"))
        assert slot_details(model, self._rules(dsk="element"), self.TIPS) == {"slotmap_3_2_1": "WD2793"}

    def test_element_flag_is_per_rule_not_per_label(self):
        model = self._devices(slotmap_3_2_1=("DSK", "ROM", "Disk ROM"))      # the other DSK rule matched
        assert slot_details(model, self._rules(dsk="element"), self.TIPS) == {}

    def test_element_needs_the_final_label_to_be_that_rules(self):
        model = self._devices(slotmap_3_2_1=("FW", "WD2793", None))            # e.g. local data overrode the cell
        assert slot_details(model, self._rules(dsk="element"), self.TIPS) == {}

    def test_element_wins_over_text(self):
        model = self._devices(slotmap_3_2_1=("DSK", "TC8566AF", None)) | {
            SLOT_TEXT_FIELD: {"slotmap_3_2_1": ["DSK", "Disk ROM v2"]}}
        rules = self._rules(dsk="element")
        rules[1]["detail"] = "text"
        assert slot_details(model, rules, self.TIPS) == {"slotmap_3_2_1": "TC8566AF"}


def test_lut_accepts_the_element_detail(tmp_path):
    lut = tmp_path / "lut.json"
    lut.write_text(json.dumps([_rule("DSK", "Disk ROM", element="WD2793", detail="element")]))
    assert load_slotmap_lut(lut)[0]["detail"] == "element"


def test_extract_slotmap_reports_each_device_cells_element():
    root = etree.fromstring(b"""<msxconfig><devices>
      <primary slot="3"><secondary slot="2">
        <WD2793 id="Memory Mapped FDC"><mem base="0x4000" size="0x8000"/></WD2793>
      </secondary></primary></devices></msxconfig>""")
    rules = [_rule("DSK", "Disk ROM", element="WD2793")]
    devices: dict[str, list] = {}
    cells = extract_slotmap(root, rules, devices_out=devices)
    assert devices == {"slotmap_3_2_1": ["WD2793", "Memory Mapped FDC"], "slotmap_3_2_2": ["WD2793", "Memory Mapped FDC"]}
    assert cells["slotmap_3_2_1"] == "DSK"


# ── Build ─────────────────────────────────────────────────────────────────

def test_build_ships_sparse_slot_details(tmp_path):
    from scraper.build import build
    rules = load_slotmap_lut(STARTER_LUT)
    fw = _classify_cell_text("Painter ROM")
    for rule in rules:
        rule.pop("detail", None)
        if rule["abbr"] == fw:
            rule["detail"] = "text"
    (tmp_path / "lut.json").write_text(json.dumps(rules), encoding="utf-8")

    texts: dict[str, list[str]] = {}
    slots = parse_slotmap_from_soup(_one_cell_page("Painter ROM"), "Maker MX-1", texts)
    record = {"manufacturer": "Maker", "model": "MX-1", "generation": "MSX1", "msxorg_title": "Maker MX-1",
              **slots, SLOT_TEXT_FIELD: texts}
    plain = {"manufacturer": "Maker", "model": "MX-2", "generation": "MSX1", "msxorg_title": "Maker MX-2", **slots}
    (tmp_path / "openmsx.json").write_text(json.dumps([]))
    (tmp_path / "msxorg.json").write_text(json.dumps([record, plain]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json", local_path=tmp_path / "l.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js",
          slotmap_lut_path=tmp_path / "lut.json")
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    keys = [c["key"] for c in data["columns"]]
    rows = {m["values"][keys.index("model")]: m for m in data["models"]}
    assert rows["MX-1"]["slot_details"] == {f"slotmap_3_0_{p}": "Painter ROM" for p in range(4)}
    assert "slot_details" not in rows["MX-2"]
    assert all(not k.startswith("_") for m in data["models"] for k in m)

"""Unit tests for scraper/link_shares.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.link_shares import apply_link_shares, load_link_shares


# ---------------------------------------------------------------------------
# load_link_shares — happy path
# ---------------------------------------------------------------------------

def test_load_link_shares_returns_mapping(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": "victor|hc-90"}), encoding="utf-8")
    shares = load_link_shares(f)
    assert shares == {"victor|hc-90a": "victor|hc-90"}


def test_load_link_shares_multiple_entries(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({
        "mfra|modela": "mfra|modelb",
        "mfrc|modelc": "mfrc|modeld",
    }), encoding="utf-8")
    shares = load_link_shares(f)
    assert shares["mfra|modela"] == "mfra|modelb"
    assert shares["mfrc|modelc"] == "mfrc|modeld"


def test_load_link_shares_empty_file(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text("{}", encoding="utf-8")
    shares = load_link_shares(f)
    assert shares == {}


# ---------------------------------------------------------------------------
# load_link_shares — error handling
# ---------------------------------------------------------------------------

def test_load_link_shares_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_link_shares(Path("nonexistent/link-shares.json"))


def test_load_link_shares_invalid_json(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_link_shares(f)


def test_load_link_shares_top_level_not_object(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON object"):
        load_link_shares(f)


def test_load_link_shares_self_reference_rejected(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": "victor|hc-90a"}), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot share links with itself"):
        load_link_shares(f)


def test_load_link_shares_non_string_value_rejected(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="all keys and values must be strings"):
        load_link_shares(f)


# ---------------------------------------------------------------------------
# apply_link_shares
# ---------------------------------------------------------------------------

def _make_records(data: list[tuple[str, dict | None]]) -> tuple[list[dict], list[str]]:
    """Build parallel (records, natural_keys) lists from (natural_key, links) pairs."""
    records = [{"id": i, **({"links": lnk} if lnk is not None else {})}
               for i, (_, lnk) in enumerate(data)]
    natural_keys = [nk for nk, _ in data]
    return records, natural_keys


def test_apply_link_shares_copies_donor_links():
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == donor_links


def test_apply_link_shares_does_not_overwrite_existing_model_link():
    existing_links = {"model": "https://www.msx.org/wiki/Victor_HC-90A"}
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", existing_links),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == existing_links  # unchanged


def test_apply_link_shares_copies_model_link_when_recipient_has_only_openmsx_link():
    """Recipient with only openmsx_id (no model link) should inherit the donor's model link."""
    donor_links = {"model": "https://www.msx.org/wiki/Philips_NMS_8250", "openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Philips_NMS_8250.xml"}
    recipient_links = {"openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Philips_NMS_8250-16.xml"}
    records, natural_keys = _make_records([
        ("philips|nms 8250", donor_links),
        ("philips|nms 8250/16", recipient_links),
    ])
    shares = {"philips|nms 8250/16": "philips|nms 8250"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"]["model"] == donor_links["model"]
    assert records[1]["links"]["openmsx_id"] == recipient_links["openmsx_id"]  # preserved


def test_apply_link_shares_skips_donor_with_no_model_link():
    """Donor with only openmsx_id (no model link) should not trigger link inheritance."""
    donor_links = {"openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Victor_HC-90.xml"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[1]


def test_apply_link_shares_skips_missing_donor():
    records, natural_keys = _make_records([
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}  # donor not in dataset
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[0]


def test_apply_link_shares_skips_donor_with_no_links():
    records, natural_keys = _make_records([
        ("victor|hc-90", None),   # donor exists but has no links
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[1]


def test_apply_link_shares_model_not_in_shares_is_noop():
    records, natural_keys = _make_records([
        ("some_mfr|some model", None),
    ])
    apply_link_shares(records, natural_keys, {})
    assert "links" not in records[0]


def test_apply_link_shares_multiple_recipients_share_same_donor():
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
        ("victor|hc-90b", None),
    ])
    shares = {
        "victor|hc-90a": "victor|hc-90",
        "victor|hc-90b": "victor|hc-90",
    }
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == donor_links
    assert records[2]["links"] == donor_links


# ---------------------------------------------------------------------------
# Data from the donor: a link-share recipient fills its blanks from the donor row
# ---------------------------------------------------------------------------

from scraper.link_shares import fill_from_link_shares  # noqa: E402


def _row(key: str, **fields) -> dict:
    manufacturer, model = key.split("|")
    return {"manufacturer": manufacturer.title(), "model": model.upper(), **fields}


def _slots(value: str) -> dict:
    return {f"slotmap_{ms}_{ss}_{p}": value for ms in range(4) for ss in range(4) for p in range(4)}


class TestFillFromLinkShares:
    SHARES = {"philips|vg 8000/00": "philips|vg-8000"}

    @staticmethod
    def _key(model: dict) -> str:
        return f"{model['manufacturer'].lower()}|{model['model'].lower()}"

    def test_missing_fields_filled_from_the_donor(self):
        donor = _row("philips|vg-8000", vram_kb=16, msxorg_title="Philips VG-8000")
        recipient = _row("philips|vg 8000/00", openmsx_id="Philips_VG_8000", main_ram_kb=16)
        filled = fill_from_link_shares([donor, recipient], self.SHARES, self._key)
        assert filled == 1
        assert recipient["vram_kb"] == 16
        assert recipient["main_ram_kb"] == 16
        assert recipient["openmsx_id"] == "Philips_VG_8000"

    def test_own_values_identity_and_bios_fields_are_kept(self):
        donor = _row("philips|vg-8000", vram_kb=16, main_ram_kb=32, msxorg_title="Philips VG-8000",
                     openmsx_id="X", character_set="International", keyboard_type="International")
        recipient = _row("philips|vg 8000/00", main_ram_kb=16)
        fill_from_link_shares([donor, recipient], self.SHARES, self._key)
        assert recipient["main_ram_kb"] == 16
        for field in ("msxorg_title", "openmsx_id", "character_set", "keyboard_type"):
            assert field not in recipient, field
        assert (recipient["manufacturer"], recipient["model"]) == ("Philips", "VG 8000/00")

    def test_slot_map_only_when_the_recipient_has_none(self):
        donor = _row("philips|vg-8000", mapper="No", **_slots("MAIN"))
        own = _row("philips|vg 8000/00", mapper="Yes", **_slots("RAM"))
        fill_from_link_shares([donor, own], self.SHARES, self._key)
        assert own["slotmap_0_0_0"] == "RAM" and own["mapper"] == "Yes"
        empty = _row("philips|vg 8000/00")
        fill_from_link_shares([donor, empty], self.SHARES, self._key)
        assert empty["slotmap_0_0_0"] == "MAIN" and empty["mapper"] == "No"

    def test_missing_donor_or_recipient_is_ignored(self):
        recipient = _row("philips|vg 8000/00", main_ram_kb=16)
        before = dict(recipient)
        assert fill_from_link_shares([recipient], self.SHARES, self._key) == 0
        assert recipient == before

    def test_chains_resolve_regardless_of_order(self):
        shares = {"a|x3": "a|x2", "a|x2": "a|x1"}
        x1, x2, x3 = _row("a|x1", vram_kb=16), _row("a|x2"), _row("a|x3")
        fill_from_link_shares([x3, x2, x1], shares, self._key)
        assert x3["vram_kb"] == x2["vram_kb"] == 16


def test_build_fills_link_share_recipients(tmp_path, monkeypatch):
    """End to end: the openMSX row sharing msx.org's VG-8000 page gets its VRAM."""
    from scraper import build as build_module

    shares = tmp_path / "link-shares.json"
    shares.write_text(json.dumps({"philips|vg 8000/00": "philips|vg-8000"}), encoding="utf-8")
    monkeypatch.setattr(build_module, "LINK_SHARES_PATH", shares)
    (tmp_path / "openmsx.json").write_text(json.dumps([
        {"manufacturer": "Philips", "model": "VG 8000/00", "generation": "MSX1", "openmsx_id": "Philips_VG_8000"}]))
    (tmp_path / "msxorg.json").write_text(json.dumps([
        {"manufacturer": "Philips", "model": "VG-8000", "generation": "MSX1", "vram_kb": 16,
         "msxorg_title": "Philips VG-8000"}]))
    build_module.build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json",
                       local_path=tmp_path / "local.json", registry_path=tmp_path / "registry.json",
                       output_path=tmp_path / "data.js")
    content = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(content[content.index("{"):content.rindex(";")])
    keys = [c["key"] for c in data["columns"]]
    rows = {dict(zip(keys, m["values"]))["model"]: (dict(zip(keys, m["values"])), m) for m in data["models"]}
    row, record = rows["VG 8000/00"]
    assert row["vram_kb"] == 16
    assert row["openmsx_id"] == "Philips_VG_8000"                                  # its own
    assert record["links"]["model"] == "https://www.msx.org/wiki/Philips_VG-8000"  # link still shared

"""Tests for scraper/regions.py — Region names and flags (data/regions.json)."""
from __future__ import annotations

import json

import pytest

from scraper.regions import REGIONS_PATH, Region, RegionTable, flag_emoji, load_regions

TABLE = RegionTable([
    Region("Japan", ["JP"]),
    Region("Japan (probably)", ["JP"], ["Probably Japan"]),
    Region("Netherlands", ["NL"]),
    Region("Belgium", ["BE"]),
    Region("Sweden", ["SE"]),
    Region("Finland", ["FI"]),
    Region("Scandinavia", ["SE", "NO", "DK"]),
    Region("United Kingdom", ["GB"], ["UK"]),
    Region("Korea", ["KR"], ["South Korea (original version)"]),
])


def test_flag_emoji_is_two_regional_indicators():
    assert flag_emoji("JP") == "\U0001F1EF\U0001F1F5"
    assert flag_emoji("eu") == flag_emoji("EU")


@pytest.mark.parametrize("value,names,flags", [
    ("Belgium and the Netherlands", ["Belgium", "Netherlands"], ["BE", "NL"]),
    ("Belgium, The Netherlands", ["Belgium", "Netherlands"], ["BE", "NL"]),
    ("se/fi", ["Sweden", "Finland"], ["SE", "FI"]),                         # ISO codes
    ("uk", ["United Kingdom"], ["GB"]),                                     # alias, any case
    ("Probably Japan", ["Japan (probably)"], ["JP"]),
    ("South Korea (original version)", ["Korea"], ["KR"]),                  # whole value first
    ("Scandinavia, Sweden", ["Scandinavia", "Sweden"], ["SE", "NO", "DK"]),  # a flag shown once
])
def test_parse_names_and_flags(value, names, flags):
    parsed = TABLE.parse(value)
    assert parsed.names == names
    assert parsed.display == "".join(flag_emoji(c) for c in flags)
    assert parsed.unknown == []


def test_unknown_part_is_kept_as_text_and_reported():
    parsed = TABLE.parse("Japan, Atlantis")
    assert parsed.names == ["Japan", "Atlantis"]
    assert parsed.display == f"{flag_emoji('JP')} Atlantis"
    assert parsed.unknown == ["Atlantis"]


def test_iso_code_never_overrides_a_name_or_alias():
    table = RegionTable([Region("Uruguay", ["UY"]), Region("Ukraine", ["UA"], ["UY"])])
    assert table.parse("uy").names == ["Ukraine"]


def test_a_name_claimed_by_two_regions_is_an_error():
    with pytest.raises(ValueError, match="names both"):
        RegionTable([Region("Japan", ["JP"]), Region("Nippon", ["JP"], ["Japan"])])


def test_load_rejects_bad_flags(tmp_path):
    path = tmp_path / "regions.json"
    path.write_text(json.dumps({"regions": [{"name": "Japan", "flags": ["jpn"]}]}))
    with pytest.raises(ValueError, match="two capital letters"):
        load_regions(path)


def test_committed_regions_file_loads():
    table = load_regions(REGIONS_PATH)
    for region in table.regions:
        assert table.parse(region.name).names == [region.name]


def test_build_ships_names_as_value_and_flags_as_display(tmp_path):
    from scraper.build import build
    from scraper.columns import COLUMNS
    regions = tmp_path / "regions.json"
    regions.write_text(json.dumps({"regions": [{"name": "Netherlands", "flags": ["NL"]},
                                               {"name": "Belgium", "flags": ["BE"]}]}))
    (tmp_path / "openmsx.json").write_text(json.dumps([]))
    (tmp_path / "msxorg.json").write_text(json.dumps([
        {"manufacturer": "Maker", "model": "MX-1", "generation": "MSX1", "region": "Belgium and the Netherlands"},
        {"manufacturer": "Maker", "model": "MX-2", "generation": "MSX1", "region": "Atlantis"},
    ]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json", local_path=tmp_path / "l.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js", regions_path=regions)
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    flag_cols = [c.key for c in COLUMNS if c.flags == "region"]
    assert flag_cols
    keys = [c["key"] for c in data["columns"]]
    for key in flag_cols:
        col = data["columns"][keys.index(key)]
        values = {m["values"][keys.index("model")]: m["values"][keys.index(key)] for m in data["models"]}
        assert values["MX-1"] == "Belgium, Netherlands"
        assert col["displayValues"]["Belgium, Netherlands"] == flag_emoji("BE") + flag_emoji("NL")
        assert col["displayValues"]["Atlantis"] == "Atlantis"


# ── Language columns ──────────────────────────────────────────────────────

LANG_TABLE = RegionTable(
    [Region("France", ["FR"]), Region("United Kingdom", ["GB"], ["UK"]), Region("International", ["UN"])],
    {"French": "France"},
)


@pytest.mark.parametrize("value,flags", [
    ("French (AZERTY)", ["FR"]),       # a closing note is ignored
    ("French", ["FR"]),
    ("french", ["FR"]),
    ("UK", ["GB"]),                    # a region alias needs no language entry
    ("International", ["UN"]),
])
def test_language_display(value, flags):
    assert LANG_TABLE.language_display(value) == "".join(flag_emoji(c) for c in flags)


def test_language_without_a_flag_is_none():
    assert LANG_TABLE.language_display("Code 8") is None


def test_language_naming_an_unknown_region_is_an_error():
    with pytest.raises(ValueError, match="unknown region"):
        RegionTable([Region("France", ["FR"])], {"German": "Germany"})


def test_build_keeps_language_values_and_ships_their_flags(tmp_path):
    from scraper.build import build
    from scraper.columns import COLUMNS
    regions = tmp_path / "regions.json"
    regions.write_text(json.dumps({"regions": [{"name": "France", "flags": ["FR"]}],
                                   "languages": {"_comment": "x", "French": "France"}}))
    lang_cols = [c.key for c in COLUMNS if c.flags == "language"]
    assert lang_cols
    (tmp_path / "openmsx.json").write_text(json.dumps([]))
    (tmp_path / "msxorg.json").write_text(json.dumps([
        {"manufacturer": "Maker", "model": "MX-1", "generation": "MSX1", **{k: "French (AZERTY)" for k in lang_cols}},
        {"manufacturer": "Maker", "model": "MX-2", "generation": "MSX1", **{k: "Code 8" for k in lang_cols}},
    ]))
    build(openmsx_path=tmp_path / "openmsx.json", msxorg_path=tmp_path / "msxorg.json", local_path=tmp_path / "l.json",
          registry_path=tmp_path / "registry.json", output_path=tmp_path / "data.js", regions_path=regions)
    text = (tmp_path / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    keys = [c["key"] for c in data["columns"]]
    for key in lang_cols:
        col = data["columns"][keys.index(key)]
        values = {m["values"][keys.index("model")]: m["values"][keys.index(key)] for m in data["models"]}
        assert values["MX-1"] == "French (AZERTY)"                 # the value is kept
        assert col["displayValues"] == {"French (AZERTY)": flag_emoji("FR")}

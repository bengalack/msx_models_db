"""Unit tests for scraper/aliases.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scraper.aliases import AliasLUT, apply_aliases, load_aliases


# ---------------------------------------------------------------------------
# load_aliases — happy path
# ---------------------------------------------------------------------------

def test_load_aliases_returns_inverted_lut(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
        "model": {"Expert Turbo": ["Expert 2+ Turbo"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut.single["brand"]["al alamiah"] == "Sakhr"
    assert lut.single["model"]["expert 2+ turbo"] == "Expert Turbo"
    assert lut.composite == []


def test_load_aliases_multiple_aliases(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"CIEL": ["CIEL (Ademir Carchano)", "ciel computers"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut.single["brand"]["ciel (ademir carchano)"] == "CIEL"
    assert lut.single["brand"]["ciel computers"] == "CIEL"


# ---------------------------------------------------------------------------
# apply_aliases
# ---------------------------------------------------------------------------

def test_apply_aliases_replaces_canonical(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Al Alamiah", "model": "AX-350"}
    apply_aliases(record, lut)
    assert record["brand"] == "Sakhr"
    assert record["model"] == "AX-350"  # untouched


def test_apply_aliases_case_insensitive(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "al alamiah"}
    apply_aliases(record, lut)
    assert record["brand"] == "Sakhr"


def test_apply_aliases_canonical_unchanged(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Sakhr"}
    apply_aliases(record, lut)
    assert record["brand"] == "Sakhr"


def test_apply_aliases_unknown_field_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"model": "AX-350"}  # no 'brand' key
    apply_aliases(record, lut)
    assert record == {"model": "AX-350"}


def test_apply_aliases_none_value_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": None}
    apply_aliases(record, lut)
    assert record["brand"] is None


# ---------------------------------------------------------------------------
# load_aliases — error cases
# ---------------------------------------------------------------------------

def test_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        load_aliases(missing)


def test_not_a_dict_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_aliases(lut_file)


def test_column_value_not_dict_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({"brand": ["Al Alamiah"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="brand"):
        load_aliases(lut_file)


def test_invalid_json_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_aliases(lut_file)


def test_alias_not_a_list_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": "Al Alamiah"},  # string, not list
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a list"):
        load_aliases(lut_file)


def test_duplicate_alias_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {
            "Sakhr":    ["Al Alamiah"],
            "Al Sakhr": ["Al Alamiah"],  # same alias, different canonical
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate alias.*Al Alamiah"):
        load_aliases(lut_file)


# ---------------------------------------------------------------------------
# load_aliases — composite rules
# ---------------------------------------------------------------------------

def test_load_aliases_composite_happy_path(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [
            {
                "match":     {"brand": "Sakhr",  "model": "AX-350IIF"},
                "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
            }
        ]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert len(lut.composite) == 1
    match_lower, canonical = lut.composite[0]
    assert match_lower == {"brand": "sakhr", "model": "ax-350iif"}
    assert canonical   == {"brand": "Yamaha", "model": "AX350IIF"}


def test_load_aliases_composite_not_a_list_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({"composite": {"bad": "value"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="'composite' must be a list"):
        load_aliases(lut_file)


def test_load_aliases_composite_missing_match_key_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{"canonical": {"brand": "Yamaha"}}]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="composite rule #0"):
        load_aliases(lut_file)


def test_load_aliases_composite_non_string_value_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"brand": "Sakhr", "model": 123},
            "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a string"):
        load_aliases(lut_file)


def test_load_aliases_composite_empty_match_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{"match": {}, "canonical": {"brand": "Yamaha"}}]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        load_aliases(lut_file)


# ---------------------------------------------------------------------------
# apply_aliases — composite rules
# ---------------------------------------------------------------------------

def test_apply_aliases_composite_all_columns_match(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"brand": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Sakhr", "model": "AX-350IIF", "generation": "MSX2"}
    apply_aliases(record, lut)
    assert record["brand"] == "Yamaha"
    assert record["model"]        == "AX350IIF"
    assert record["generation"]   == "MSX2"  # untouched


def test_apply_aliases_composite_partial_match_noop(tmp_path):
    """Only one of the required columns matches — record must be unchanged."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"brand": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Sakhr", "model": "AX-350II"}  # model differs
    apply_aliases(record, lut)
    assert record == {"brand": "Sakhr", "model": "AX-350II"}


def test_apply_aliases_composite_case_insensitive(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"brand": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "SAKHR", "model": "ax-350iif"}
    apply_aliases(record, lut)
    assert record["brand"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


def test_apply_aliases_composite_fires_after_single(tmp_path):
    """Single-column pass normalizes Al Alamiah → Sakhr; composite then fires."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
        "composite": [{
            "match":     {"brand": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Al Alamiah", "model": "AX-350IIF"}
    apply_aliases(record, lut)
    assert record["brand"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


def test_apply_aliases_composite_first_match_wins(tmp_path):
    """When two composite rules could match, only the first is applied."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [
            {
                "match":     {"brand": "Sakhr", "model": "AX-350IIF"},
                "canonical": {"brand": "Yamaha", "model": "AX350IIF"},
            },
            {
                "match":     {"brand": "Sakhr", "model": "AX-350IIF"},
                "canonical": {"brand": "Sony",  "model": "SHOULD_NOT"},
            },
        ]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"brand": "Sakhr", "model": "AX-350IIF"}
    apply_aliases(record, lut)
    assert record["brand"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


# ---------------------------------------------------------------------------
# Integration — alias application in merge_models
# ---------------------------------------------------------------------------

def test_merge_uses_aliases(tmp_path):
    """Two records with alias brand names merge into one after alias application."""
    import json
    from scraper.merge import merge_models

    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({
        "brand": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")

    openmsx_records = [{"brand": "Sakhr",      "model": "AX-350", "generation": "MSX2"}]
    msxorg_records  = [{"brand": "Al Alamiah", "model": "AX-350", "generation": "MSX2"}]

    merged = merge_models(openmsx_records, msxorg_records, alias_path=alias_file)
    assert len(merged) == 1
    assert merged[0]["brand"] == "Sakhr"


# ---------------------------------------------------------------------------
# Former keys — the pre-alias natural keys a merged model descends from
# ---------------------------------------------------------------------------

def _alias_file(tmp_path, content):
    import json
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_merge_records_former_keys_from_every_source(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models

    alias_file = _alias_file(tmp_path, {
        "model": {"AX-230": ["AX230", "AX-230 (Manufacturer: Sanyo)"]},
    })
    openmsx = [{"brand": "Sakhr", "model": "AX230"}]
    msxorg  = [{"brand": "Sakhr", "model": "AX-230 (Manufacturer: Sanyo)"}]
    local   = [{"brand": "Sakhr", "model": "AX230", "himem_addr": "0xF380"}]

    merged = merge_models(openmsx, msxorg, local=local, alias_path=alias_file)

    assert len(merged) == 1
    assert merged[0]["model"] == "AX-230"
    assert merged[0][FORMER_KEYS_FIELD] == ["sakhr|ax-230 (manufacturer: sanyo)", "sakhr|ax230"]


def test_merge_composite_alias_records_former_key(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models

    alias_file = _alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"brand": "Sakhr", "model": "AX-150"},
                       "canonical": {"brand": "Yamaha", "model": "AX-150"}}],
    })
    merged = merge_models(
        [{"brand": "Yamaha", "model": "AX150"}],
        [{"brand": "Sakhr", "model": "AX-150"}],
        alias_path=alias_file,
    )
    assert len(merged) == 1
    assert (merged[0]["brand"], merged[0]["model"]) == ("Yamaha", "AX-150")
    assert merged[0][FORMER_KEYS_FIELD] == ["sakhr|ax-150", "yamaha|ax150"]


def test_unaliased_model_has_no_former_keys(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models

    alias_file = _alias_file(tmp_path, {"model": {"AX-150": ["AX150"]}})
    merged = merge_models([{"brand": "Sony", "model": "HB-75P"}], [], alias_path=alias_file)
    assert FORMER_KEYS_FIELD not in merged[0]


def test_build_keeps_lowest_former_id_when_alias_renames_a_model(tmp_path, monkeypatch):
    """End to end: an alias that merges two known models keeps the lower id and spends none."""
    import json
    from scraper import build as build_module
    from scraper.registry import IDRegistry

    alias_file = _alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"brand": "Sakhr", "model": "AX-150"},
                       "canonical": {"brand": "Yamaha", "model": "AX-150"}}],
    })
    monkeypatch.setattr(build_module, "ALIASES_PATH", alias_file)

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({
        "version": 2,
        "models": {"sakhr|ax-150": 275, "yamaha|ax150": 384},
        "retired_models": [],
        "next_model_id": 400,
    }))
    openmsx = tmp_path / "openmsx.json"
    msxorg = tmp_path / "msxorg.json"
    openmsx.write_text(json.dumps([{"brand": "Yamaha", "model": "AX150", "generation": "MSX1"}]))
    msxorg.write_text(json.dumps([{"brand": "Sakhr", "model": "AX-150", "generation": "MSX1"}]))
    output = tmp_path / "data.js"

    build_module.build(openmsx_path=openmsx, msxorg_path=msxorg, local_path=tmp_path / "local.json",
                       registry_path=registry_path, output_path=output)

    content = output.read_text(encoding="utf-8")
    data = json.loads(content[content.index("{"):content.rindex(";")])
    assert [m["id"] for m in data["models"]] == [275]
    reg = IDRegistry.load(registry_path)
    assert reg.models["yamaha|ax-150"] == 275
    assert reg.next_model_id == 400


# ---------------------------------------------------------------------------
# variant_tag — country tag closing a model name
# ---------------------------------------------------------------------------

def _tag_lut(tmp_path, tags, **extra):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({"variant_tag": tags, **extra}), encoding="utf-8")
    return load_aliases(lut_file)


def test_variant_tag_canonicalises_closing_tag(tmp_path):
    lut = _tag_lut(tmp_path, {"DE": ["GE"], "GB": ["UK"]})
    record = {"brand": "Maker", "model": "M-1 (GE)"}
    apply_aliases(record, lut)
    assert record["model"] == "M-1 (DE)"


def test_variant_tag_keeps_spacing_and_ignores_case(tmp_path):
    lut = _tag_lut(tmp_path, {"GB": ["UK"]})
    record = {"brand": "Maker", "model": "M-7(uk)"}
    apply_aliases(record, lut)
    assert record["model"] == "M-7(GB)"


def test_variant_tag_leaves_other_tags_and_inner_text(tmp_path):
    lut = _tag_lut(tmp_path, {"DE": ["GE"]})
    for model in ["M-1 (FR)", "GE-100", "M-1 (GE) mk2", "M-1"]:
        record = {"brand": "Maker", "model": model}
        apply_aliases(record, lut)
        assert record["model"] == model


def test_variant_tag_applies_before_model_rules(tmp_path):
    lut = _tag_lut(tmp_path, {"DE": ["GE"]}, model={"M-2 (DE)": ["M-1 (DE)"]})
    record = {"brand": "Maker", "model": "M-1 (GE)"}
    apply_aliases(record, lut)
    assert record["model"] == "M-2 (DE)"


@pytest.mark.parametrize("tags", [
    ["GE"],                      # not an object
    {"DE": "GE"},                # aliases not a list
    {"GERMANY": ["GE"]},         # canonical not a 2-3 letter tag
    {"DE": ["GE"], "GB": ["GE"]},  # one alias, two tags
])
def test_variant_tag_rejects_malformed(tmp_path, tags):
    with pytest.raises(ValueError):
        _tag_lut(tmp_path, tags)


def test_committed_variant_tags_map_to_distinct_canonicals():
    lut = load_aliases(Path("data/aliases.json"))
    for alias, canonical in lut.variant_tag.items():
        assert alias != canonical.lower()
        assert canonical.lower() not in lut.variant_tag


# ---------------------------------------------------------------------------
# Composite rules: "*" wildcards and partial canonicals
# (openMSX names the maker in <manufacturer>, e.g. Yamaha for Sakhr's AX range)
# ---------------------------------------------------------------------------

def _wildcard_lut(tmp_path):
    return load_aliases(_alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"brand": "Yamaha", "model": "AX-*"}, "canonical": {"brand": "Sakhr"}}],
    }))


@pytest.mark.parametrize("record,expected", [
    ({"brand": "Yamaha", "model": "AX-500"}, {"brand": "Sakhr", "model": "AX-500"}),
    ({"brand": "yamaha", "model": "ax-200"}, {"brand": "Sakhr", "model": "ax-200"}),    # any case
    ({"brand": "Yamaha", "model": "AX150"}, {"brand": "Sakhr", "model": "AX-150"}),     # after the model alias
    ({"brand": "Yamaha", "model": "CX5M"}, {"brand": "Yamaha", "model": "CX5M"}),       # other models untouched
    ({"brand": "Sony", "model": "AX-500"}, {"brand": "Sony", "model": "AX-500"}),       # other brands untouched
    ({"brand": "Yamaha", "model": "MAX-1"}, {"brand": "Yamaha", "model": "MAX-1"}),     # the whole value must match
])
def test_composite_wildcard_with_partial_canonical(tmp_path, record, expected):
    apply_aliases(record, _wildcard_lut(tmp_path))
    assert record == expected


def test_composite_wildcard_treats_other_characters_literally(tmp_path):
    lut = load_aliases(_alias_file(tmp_path, {
        "composite": [{"match": {"model": "A.(1)*"}, "canonical": {"brand": "X"}}],
    }))
    hit, miss = {"brand": "B", "model": "A.(1) v2"}, {"brand": "B", "model": "AB(1) v2"}
    apply_aliases(hit, lut)
    apply_aliases(miss, lut)
    assert hit["brand"] == "X" and miss["brand"] == "B"


def test_wildcard_rule_joins_openmsx_maker_with_msxorg_brand(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models
    openmsx = [{"brand": "Yamaha", "model": "AX150", "year": 1986}]
    msxorg = [{"brand": "Sakhr", "model": "AX-150", "region": "Middle East"}]
    merged = merge_models(openmsx, msxorg, alias_path=_alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"brand": "Yamaha", "model": "AX-*"}, "canonical": {"brand": "Sakhr"}}],
    }))
    assert len(merged) == 1
    assert (merged[0]["brand"], merged[0]["model"]) == ("Sakhr", "AX-150")
    assert "yamaha|ax150" in merged[0][FORMER_KEYS_FIELD]

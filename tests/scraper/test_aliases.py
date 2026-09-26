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
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
        "model": {"Expert Turbo": ["Expert 2+ Turbo"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut.single["manufacturer"]["al alamiah"] == "Sakhr"
    assert lut.single["model"]["expert 2+ turbo"] == "Expert Turbo"
    assert lut.composite == []


def test_load_aliases_multiple_aliases(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"CIEL": ["CIEL (Ademir Carchano)", "ciel computers"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut.single["manufacturer"]["ciel (ademir carchano)"] == "CIEL"
    assert lut.single["manufacturer"]["ciel computers"] == "CIEL"


# ---------------------------------------------------------------------------
# apply_aliases
# ---------------------------------------------------------------------------

def test_apply_aliases_replaces_canonical(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Al Alamiah", "model": "AX-350"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"
    assert record["model"] == "AX-350"  # untouched


def test_apply_aliases_case_insensitive(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "al alamiah"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"


def test_apply_aliases_canonical_unchanged(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Sakhr"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Sakhr"


def test_apply_aliases_unknown_field_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"model": "AX-350"}  # no 'manufacturer' key
    apply_aliases(record, lut)
    assert record == {"model": "AX-350"}


def test_apply_aliases_none_value_noop(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": None}
    apply_aliases(record, lut)
    assert record["manufacturer"] is None


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
    lut_file.write_text(json.dumps({"manufacturer": ["Al Alamiah"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="manufacturer"):
        load_aliases(lut_file)


def test_invalid_json_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_aliases(lut_file)


def test_alias_not_a_list_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": "Al Alamiah"},  # string, not list
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a list"):
        load_aliases(lut_file)


def test_duplicate_alias_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {
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
                "match":     {"manufacturer": "Sakhr",  "model": "AX-350IIF"},
                "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
            }
        ]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert len(lut.composite) == 1
    match_lower, canonical = lut.composite[0]
    assert match_lower == {"manufacturer": "sakhr", "model": "ax-350iif"}
    assert canonical   == {"manufacturer": "Yamaha", "model": "AX350IIF"}


def test_load_aliases_composite_not_a_list_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({"composite": {"bad": "value"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="'composite' must be a list"):
        load_aliases(lut_file)


def test_load_aliases_composite_missing_match_key_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{"canonical": {"manufacturer": "Yamaha"}}]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="composite rule #0"):
        load_aliases(lut_file)


def test_load_aliases_composite_non_string_value_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"manufacturer": "Sakhr", "model": 123},
            "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a string"):
        load_aliases(lut_file)


def test_load_aliases_composite_empty_match_raises(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{"match": {}, "canonical": {"manufacturer": "Yamaha"}}]
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
            "match":     {"manufacturer": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Sakhr", "model": "AX-350IIF", "generation": "MSX2"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Yamaha"
    assert record["model"]        == "AX350IIF"
    assert record["generation"]   == "MSX2"  # untouched


def test_apply_aliases_composite_partial_match_noop(tmp_path):
    """Only one of the required columns matches — record must be unchanged."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"manufacturer": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Sakhr", "model": "AX-350II"}  # model differs
    apply_aliases(record, lut)
    assert record == {"manufacturer": "Sakhr", "model": "AX-350II"}


def test_apply_aliases_composite_case_insensitive(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [{
            "match":     {"manufacturer": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "SAKHR", "model": "ax-350iif"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


def test_apply_aliases_composite_fires_after_single(tmp_path):
    """Single-column pass normalizes Al Alamiah → Sakhr; composite then fires."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
        "composite": [{
            "match":     {"manufacturer": "Sakhr",  "model": "AX-350IIF"},
            "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
        }]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Al Alamiah", "model": "AX-350IIF"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


def test_apply_aliases_composite_first_match_wins(tmp_path):
    """When two composite rules could match, only the first is applied."""
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "composite": [
            {
                "match":     {"manufacturer": "Sakhr", "model": "AX-350IIF"},
                "canonical": {"manufacturer": "Yamaha", "model": "AX350IIF"},
            },
            {
                "match":     {"manufacturer": "Sakhr", "model": "AX-350IIF"},
                "canonical": {"manufacturer": "Sony",  "model": "SHOULD_NOT"},
            },
        ]
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    record = {"manufacturer": "Sakhr", "model": "AX-350IIF"}
    apply_aliases(record, lut)
    assert record["manufacturer"] == "Yamaha"
    assert record["model"]        == "AX350IIF"


# ---------------------------------------------------------------------------
# Integration — alias application in merge_models
# ---------------------------------------------------------------------------

def test_merge_uses_aliases(tmp_path):
    """Two records with alias manufacturer names merge into one after alias application."""
    import json
    from scraper.merge import merge_models

    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({
        "manufacturer": {"Sakhr": ["Al Alamiah"]},
    }), encoding="utf-8")

    openmsx_records = [{"manufacturer": "Sakhr",      "model": "AX-350", "generation": "MSX2"}]
    msxorg_records  = [{"manufacturer": "Al Alamiah", "model": "AX-350", "generation": "MSX2"}]

    merged = merge_models(openmsx_records, msxorg_records, alias_path=alias_file)
    assert len(merged) == 1
    assert merged[0]["manufacturer"] == "Sakhr"


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
    openmsx = [{"manufacturer": "Sakhr", "model": "AX230"}]
    msxorg  = [{"manufacturer": "Sakhr", "model": "AX-230 (Manufacturer: Sanyo)"}]
    local   = [{"manufacturer": "Sakhr", "model": "AX230", "himem_addr": "0xF380"}]

    merged = merge_models(openmsx, msxorg, local=local, alias_path=alias_file)

    assert len(merged) == 1
    assert merged[0]["model"] == "AX-230"
    assert merged[0][FORMER_KEYS_FIELD] == ["sakhr|ax-230 (manufacturer: sanyo)", "sakhr|ax230"]


def test_merge_composite_alias_records_former_key(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models

    alias_file = _alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"manufacturer": "Sakhr", "model": "AX-150"},
                       "canonical": {"manufacturer": "Yamaha", "model": "AX-150"}}],
    })
    merged = merge_models(
        [{"manufacturer": "Yamaha", "model": "AX150"}],
        [{"manufacturer": "Sakhr", "model": "AX-150"}],
        alias_path=alias_file,
    )
    assert len(merged) == 1
    assert (merged[0]["manufacturer"], merged[0]["model"]) == ("Yamaha", "AX-150")
    assert merged[0][FORMER_KEYS_FIELD] == ["sakhr|ax-150", "yamaha|ax150"]


def test_unaliased_model_has_no_former_keys(tmp_path):
    from scraper.merge import FORMER_KEYS_FIELD, merge_models

    alias_file = _alias_file(tmp_path, {"model": {"AX-150": ["AX150"]}})
    merged = merge_models([{"manufacturer": "Sony", "model": "HB-75P"}], [], alias_path=alias_file)
    assert FORMER_KEYS_FIELD not in merged[0]


def test_build_keeps_lowest_former_id_when_alias_renames_a_model(tmp_path, monkeypatch):
    """End to end: an alias that merges two known models keeps the lower id and spends none."""
    import json
    from scraper import build as build_module
    from scraper.registry import IDRegistry

    alias_file = _alias_file(tmp_path, {
        "model": {"AX-150": ["AX150"]},
        "composite": [{"match": {"manufacturer": "Sakhr", "model": "AX-150"},
                       "canonical": {"manufacturer": "Yamaha", "model": "AX-150"}}],
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
    openmsx.write_text(json.dumps([{"manufacturer": "Yamaha", "model": "AX150", "generation": "MSX1"}]))
    msxorg.write_text(json.dumps([{"manufacturer": "Sakhr", "model": "AX-150", "generation": "MSX1"}]))
    output = tmp_path / "data.js"

    build_module.build(openmsx_path=openmsx, msxorg_path=msxorg, local_path=tmp_path / "local.json",
                       registry_path=registry_path, output_path=output)

    content = output.read_text(encoding="utf-8")
    data = json.loads(content[content.index("{"):content.rindex(";")])
    assert [m["id"] for m in data["models"]] == [275]
    reg = IDRegistry.load(registry_path)
    assert reg.models["yamaha|ax-150"] == 275
    assert reg.next_model_id == 400

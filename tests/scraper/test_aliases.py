"""Unit tests for scraper/aliases.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scraper.aliases import apply_aliases, load_aliases


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
    # Inverted: {column: {alias_lower: canonical}}
    assert lut["manufacturer"]["al alamiah"] == "Sakhr"
    assert lut["model"]["expert 2+ turbo"] == "Expert Turbo"


def test_load_aliases_multiple_aliases(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {"CIEL": ["CIEL (Ademir Carchano)", "ciel computers"]},
    }), encoding="utf-8")
    lut = load_aliases(lut_file)
    assert lut["manufacturer"]["ciel (ademir carchano)"] == "CIEL"
    assert lut["manufacturer"]["ciel computers"] == "CIEL"


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


def test_duplicate_alias_raises_value_error(tmp_path):
    lut_file = tmp_path / "aliases.json"
    lut_file.write_text(json.dumps({
        "manufacturer": {
            "Sakhr":    ["Al Alamiah"],
            "Al Sakhr": ["Al Alamiah"],  # same alias, different canonical
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate alias"):
        load_aliases(lut_file)

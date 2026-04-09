"""Tests for scraper/slotmap_lut.py — load, validate, and compact the LUT."""

import json
import re
from pathlib import Path

import pytest

from scraper.slotmap_lut import compact_lut, load_slotmap_lut

# Path to the committed starter LUT
STARTER_LUT = Path("data/slotmap-lut.json")

EXPECTED_ABBRS = {
    "MAIN", "SUB", "KAN", "HAN", "JE", "MOD", "DOS2", "CP/M",
    "FW", "DSK", "MUS", "RS", "RSFW", "MM", "PM",
    "RAM", "BUN", "SFG5", "SFG1", "EXP", "\u2327", "\u2022",
    "CS1", "CS2", "CS3", "CS4",
    "CS1!", "CS2!", "CS3!", "CS4!",
}


# ---------------------------------------------------------------------------
# Happy path — starter LUT
# ---------------------------------------------------------------------------

def test_load_starter_lut_returns_list():
    rules = load_slotmap_lut(STARTER_LUT)
    assert isinstance(rules, list)


def test_load_starter_lut_count():
    rules = load_slotmap_lut(STARTER_LUT)
    assert len(rules) == 33


def test_load_starter_lut_rule_keys():
    rules = load_slotmap_lut(STARTER_LUT)
    for rule in rules:
        assert "element" in rule
        assert "id_pattern" in rule
        assert "abbr" in rule
        assert "tooltip" in rule


def test_load_starter_lut_abbrs():
    rules = load_slotmap_lut(STARTER_LUT)
    abbrs = {rule["abbr"] for rule in rules}
    assert abbrs == EXPECTED_ABBRS


# ---------------------------------------------------------------------------
# compact_lut
# ---------------------------------------------------------------------------

def test_compact_lut_returns_abbr_to_tooltip():
    rules = load_slotmap_lut(STARTER_LUT)
    lut = compact_lut(rules)
    assert isinstance(lut, dict)
    assert set(lut.keys()) == EXPECTED_ABBRS


def test_compact_lut_values_are_strings():
    rules = load_slotmap_lut(STARTER_LUT)
    lut = compact_lut(rules)
    for abbr, tooltip in lut.items():
        assert isinstance(tooltip, str), f"Tooltip for {abbr!r} is not a string"


def test_compact_lut_omits_rule_metadata():
    rules = load_slotmap_lut(STARTER_LUT)
    lut = compact_lut(rules)
    for value in lut.values():
        assert not isinstance(value, dict), "compact_lut should not contain nested dicts"


def test_compact_lut_known_entries():
    rules = load_slotmap_lut(STARTER_LUT)
    lut = compact_lut(rules)
    assert lut["MAIN"] == "MSX BIOS with BASIC ROM"
    assert lut["\u2327"] == "Sub-slot absent (not expanded)"
    assert lut["\u2022"] == "Empty page \u2014 no device mapped"
    assert lut["DSK"] == "Disk ROM"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        load_slotmap_lut(missing)


def test_duplicate_abbr_with_same_tooltip_is_valid(tmp_path):
    """Same abbr allowed when tooltip is identical (different element types → same abbr)."""
    lut_file = tmp_path / "lut.json"
    lut_file.write_text(json.dumps([
        {"element": "MSX-RS232", "id_pattern": None,    "abbr": "RS2", "tooltip": "RS-232C Interface"},
        {"element": "ROM",       "id_pattern": "rs232", "abbr": "RS2", "tooltip": "RS-232C Interface"},
    ]))
    rules = load_slotmap_lut(lut_file)
    assert len(rules) == 2


def test_duplicate_abbr_with_conflicting_tooltip_raises(tmp_path):
    """Same abbr with a different tooltip is an error (conflicting definitions)."""
    lut_file = tmp_path / "lut.json"
    lut_file.write_text(json.dumps([
        {"element": "ROM", "id_pattern": "Main ROM", "abbr": "MAIN", "tooltip": "Main ROM"},
        {"element": "ROM", "id_pattern": "Sub ROM",  "abbr": "MAIN", "tooltip": "Sub ROM"},
    ]))
    with pytest.raises(ValueError, match="duplicate abbr.*MAIN"):
        load_slotmap_lut(lut_file)


def test_malformed_regex_raises_value_error(tmp_path):
    lut_file = tmp_path / "lut.json"
    lut_file.write_text(json.dumps([
        {"element": "ROM", "id_pattern": "[invalid(", "abbr": "BAD", "tooltip": "Bad"},
    ]))
    with pytest.raises(ValueError, match="invalid id_pattern"):
        load_slotmap_lut(lut_file)


def test_not_a_list_raises_value_error(tmp_path):
    lut_file = tmp_path / "lut.json"
    lut_file.write_text(json.dumps({"abbr": "MAIN"}))
    with pytest.raises(ValueError, match="JSON array"):
        load_slotmap_lut(lut_file)


def test_invalid_json_raises_value_error(tmp_path):
    lut_file = tmp_path / "lut.json"
    lut_file.write_text("not json {{{")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_slotmap_lut(lut_file)


def test_null_id_pattern_is_valid(tmp_path):
    """id_pattern: null should be accepted (match-all)."""
    lut_file = tmp_path / "lut.json"
    lut_file.write_text(json.dumps([
        {"element": "MemoryMapper", "id_pattern": None, "abbr": "MM", "tooltip": "Memory Mapper"},
    ]))
    rules = load_slotmap_lut(lut_file)
    assert len(rules) == 1
    assert rules[0]["abbr"] == "MM"

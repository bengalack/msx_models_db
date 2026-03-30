"""Tests for slot map column and group definitions in scraper/columns.py."""

import re

import pytest

from scraper.columns import COLUMNS, GROUPS, validate_config


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------

def test_group_count():
    assert len(GROUPS) == 12


def test_column_count():
    assert len(COLUMNS) == 93


# ---------------------------------------------------------------------------
# No duplicates
# ---------------------------------------------------------------------------

def test_no_duplicate_group_ids():
    ids = [g.id for g in GROUPS]
    assert len(ids) == len(set(ids))


def test_no_duplicate_group_keys():
    keys = [g.key for g in GROUPS]
    assert len(keys) == len(set(keys))


def test_no_duplicate_column_ids():
    ids = [c.id for c in COLUMNS]
    assert len(ids) == len(set(ids))


def test_no_duplicate_column_keys():
    keys = [c.key for c in COLUMNS]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Slotmap groups
# ---------------------------------------------------------------------------

SLOTMAP_GROUPS = [g for g in GROUPS if g.key.startswith("slotmap_")]


def test_slotmap_group_count():
    assert len(SLOTMAP_GROUPS) == 4


def test_slotmap_group_ids():
    ids = sorted(g.id for g in SLOTMAP_GROUPS)
    assert ids == [8, 9, 10, 11]


def test_slotmap_group_labels():
    label_map = {g.id: g.label for g in SLOTMAP_GROUPS}
    assert label_map[8]  == "Slotmap, slot 0"
    assert label_map[9]  == "Slotmap, slot 1"
    assert label_map[10] == "Slotmap, slot 2"
    assert label_map[11] == "Slotmap, slot 3"


def test_slotmap_group_order_matches_id():
    for g in SLOTMAP_GROUPS:
        assert g.order == g.id, f"Group {g.key}: order {g.order} != id {g.id}"


# ---------------------------------------------------------------------------
# Slotmap columns
# ---------------------------------------------------------------------------

SLOTMAP_COLS = [c for c in COLUMNS if c.key.startswith("slotmap_")]
KEY_PATTERN   = re.compile(r"^slotmap_([0-3])_([0-3])_([0-3])$")
LABEL_PATTERN = re.compile("^([0-3])\u00a0/\u00a0P([0-3])$")


def test_slotmap_column_count():
    assert len(SLOTMAP_COLS) == 64


def test_slotmap_column_ids_range():
    ids = sorted(c.id for c in SLOTMAP_COLS)
    assert ids == list(range(30, 94))


def test_slotmap_column_keys_pattern():
    for col in SLOTMAP_COLS:
        assert KEY_PATTERN.match(col.key), f"Bad key: {col.key!r}"


def test_slotmap_column_labels_pattern():
    for col in SLOTMAP_COLS:
        assert LABEL_PATTERN.match(col.label), f"Bad label: {col.label!r} for key {col.key!r}"


def test_slotmap_column_key_label_consistency():
    """Key slotmap_{ms}_{ss}_{p} must match label {ss}\u00a0/\u00a0P{p}."""
    for col in SLOTMAP_COLS:
        km = KEY_PATTERN.match(col.key)
        lm = LABEL_PATTERN.match(col.label)
        assert km and lm
        _ms, ss, p = km.groups()
        assert (ss, p) == lm.groups(), (
            f"Key/label mismatch for column id={col.id}: "
            f"key={col.key!r} label={col.label!r}"
        )


def test_slotmap_columns_type_string():
    for col in SLOTMAP_COLS:
        assert col.type == "string", f"Column {col.key} has type {col.type!r}, expected 'string'"


def test_slotmap_columns_group_refs_valid():
    group_keys = {g.key for g in GROUPS}
    for col in SLOTMAP_COLS:
        assert col.group in group_keys, f"Column {col.key} references unknown group {col.group!r}"


def test_slotmap_columns_belong_to_slotmap_groups():
    for col in SLOTMAP_COLS:
        assert col.group.startswith("slotmap_"), (
            f"Column {col.key} has group {col.group!r}, expected slotmap_{{n}}"
        )


# ---------------------------------------------------------------------------
# validate_config passes
# ---------------------------------------------------------------------------

def test_validate_config_passes():
    """validate_config should not raise with the full GROUPS + COLUMNS."""
    validate_config(GROUPS, COLUMNS)

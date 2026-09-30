"""Tests for slot map column and group definitions in scraper/columns.py."""

import re

import pytest

from scraper.columns import COLUMNS, GROUPS, validate_config


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
# No hardcoded totals: asserting len(COLUMNS)/len(GROUPS) against a literal
# only restates the config and breaks on every legitimate content change.
# The slot map's own 4x4x4 shape is fixed by MSX hardware and is checked below.

def test_every_group_has_at_least_one_column():
    used = {c.group for c in COLUMNS}
    assert {g.key for g in GROUPS} <= used


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


def test_slotmap_group_labels_name_their_primary_slot():
    # Each group's key is slotmap_<ms>; its label names that primary slot (wording is config).
    for g in SLOTMAP_GROUPS:
        ms = g.key.rsplit("_", 1)[1]
        assert g.label.split()[-1] == ms, f"{g.key}: label {g.label!r} does not end with slot {ms}"
    assert len({g.label for g in SLOTMAP_GROUPS}) == len(SLOTMAP_GROUPS)


def test_slotmap_groups_are_consecutive_in_slot_order():
    by_slot = sorted(SLOTMAP_GROUPS, key=lambda g: int(g.key.rsplit("_", 1)[1]))
    orders = [g.order for g in by_slot]
    assert orders == list(range(orders[0], orders[0] + len(orders)))


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


# ---------------------------------------------------------------------------
# Shaded columns
# ---------------------------------------------------------------------------

SHADED_SLOTMAP_COLS = [c for c in SLOTMAP_COLS if c.shaded]
_SHADED_SUBSLOT_PATTERN = re.compile(r"^slotmap_[0-3]_[13]_[0-3]$")
_UNSHADED_SUBSLOT_PATTERN = re.compile(r"^slotmap_[0-3]_[02]_[0-3]$")


def test_shaded_slotmap_columns_exist():
    """At least one slotmap column must have shaded=True."""
    assert SHADED_SLOTMAP_COLS, "No shaded slotmap columns found"


def test_shaded_slotmap_columns_are_only_subslots_1_and_3():
    """Every shaded slotmap column key must match slotmap_*_1_* or slotmap_*_3_*."""
    for col in SHADED_SLOTMAP_COLS:
        assert _SHADED_SUBSLOT_PATTERN.match(col.key), (
            f"Shaded column {col.key!r} does not match slotmap_*_[13]_* pattern"
        )


def test_subslots_0_and_2_are_not_shaded():
    """Columns with sub-slot 0 or 2 must not have shaded=True."""
    for col in SLOTMAP_COLS:
        if _UNSHADED_SUBSLOT_PATTERN.match(col.key):
            assert not col.shaded, f"Column {col.key!r} has shaded=True but must not"


def test_non_slotmap_columns_are_not_shaded():
    """No column outside the slotmap groups must have shaded=True."""
    non_slotmap = [c for c in COLUMNS if not c.key.startswith("slotmap_")]
    for col in non_slotmap:
        assert not col.shaded, f"Non-slotmap column {col.key!r} has shaded=True"


# ---------------------------------------------------------------------------
# Slotmap Overview — sort key (1 bit per page; [slot0][slot1][slot2][slot3])
# ---------------------------------------------------------------------------

from scraper.columns import slotmap_sort_key
from scraper.symbols import ABSENT, EMPTY_PAGE


def _model(occupied: set[tuple[int, int, int]], empty: set[tuple[int, int, int]] = frozenset()) -> dict:
    model = {}
    for ms in range(4):
        for ss in range(4):
            for p in range(4):
                cell = (ms, ss, p)
                model[f"slotmap_{ms}_{ss}_{p}"] = "X" if cell in occupied else EMPTY_PAGE if cell in empty else ABSENT
    return model


def _bit(ms: int, ss: int, p: int) -> int:
    return 1 << (63 - (ms * 16 + ss * 4 + (3 - p)))


def test_sort_key_sets_one_bit_per_occupied_page():
    cells = {(0, 0, 0), (0, 0, 1), (1, 0, 3), (3, 2, 2)}
    expected = sum(_bit(*c) for c in cells)
    assert int(slotmap_sort_key(_model(cells)), 16) == expected


def test_sort_key_ignores_absent_and_empty_pages():
    assert slotmap_sort_key(_model({(0, 0, 0)}, empty={(0, 0, 1), (2, 0, 0)})) == slotmap_sort_key(_model({(0, 0, 0)}))


def test_sort_key_orders_slot0_then_subslot0_first():
    # A page in slot 0 outweighs any combination in slots 1-3; sub-slot 0 outweighs sub-slots 1-3.
    slot0 = slotmap_sort_key(_model({(0, 3, 0)}))
    rest = slotmap_sort_key(_model({(ms, ss, p) for ms in (1, 2, 3) for ss in range(4) for p in range(4)}))
    assert slot0 > rest
    assert slotmap_sort_key(_model({(1, 0, 0)})) > slotmap_sort_key(_model({(1, 1, 3), (1, 2, 3), (1, 3, 3)}))


def test_sort_key_is_fixed_width_hex_and_none_without_slot_map():
    key = slotmap_sort_key(_model({(3, 3, 0)}))
    assert len(key) == 16 and int(key, 16) == 1          # the lowest bit: slot 3-3, page 0
    assert int(slotmap_sort_key(_model({(3, 3, 3)})), 16) == _bit(3, 3, 3)
    assert slotmap_sort_key({}) is None


def test_overview_column_is_drawn_unfilterable_and_sits_in_its_own_group():
    col = next(c for c in COLUMNS if c.renderer == "slotmap")
    assert not col.filterable
    assert [c.key for c in COLUMNS if c.group == col.group] == [col.key]
    order = {g.key: g.order for g in GROUPS}
    assert order[col.group] < min(g.order for g in SLOTMAP_GROUPS)

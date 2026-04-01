"""Unit tests for scraper.columns configuration and helpers."""

from __future__ import annotations

import pytest

from scraper.columns import (
    COLUMNS,
    GROUPS,
    Column,
    Group,
    active_columns,
    derive_columns,
    group_by_key,
    validate_config,
)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateConfig:
    """Tests for validate_config()."""

    @staticmethod
    def _groups() -> list[Group]:
        """Minimal group list for isolated tests."""
        return [Group(id=0, key="g1", label="G1", order=0)]

    def test_valid_config_passes(self) -> None:
        groups = self._groups()
        cols = [Column(id=1, key="c1", label="C1", group="g1", type="string")]
        validate_config(groups, cols)  # should not raise

    def test_duplicate_column_ids_rejected(self) -> None:
        groups = self._groups()
        cols = [
            Column(id=1, key="c1", label="C1", group="g1", type="string"),
            Column(id=1, key="c2", label="C2", group="g1", type="string"),
        ]
        with pytest.raises(ValueError, match="Duplicate column id"):
            validate_config(groups, cols)

    def test_duplicate_column_keys_rejected(self) -> None:
        groups = self._groups()
        cols = [
            Column(id=1, key="c1", label="C1", group="g1", type="string"),
            Column(id=2, key="c1", label="C2", group="g1", type="string"),
        ]
        with pytest.raises(ValueError, match="Duplicate column key"):
            validate_config(groups, cols)

    def test_id_zero_rejected(self) -> None:
        groups = self._groups()
        cols = [Column(id=0, key="c0", label="C0", group="g1", type="string")]
        with pytest.raises(ValueError, match="Column id 0 is reserved"):
            validate_config(groups, cols)

    def test_unknown_group_rejected(self) -> None:
        groups = self._groups()
        cols = [Column(id=1, key="c1", label="C1", group="nope", type="string")]
        with pytest.raises(ValueError, match="unknown group"):
            validate_config(groups, cols)

    def test_hidden_and_retired_rejected(self) -> None:
        groups = self._groups()
        cols = [
            Column(id=1, key="c1", label="C1", group="g1", type="string",
                   hidden=True, retired=True),
        ]
        with pytest.raises(ValueError, match="both hidden and retired"):
            validate_config(groups, cols)

    def test_retired_with_derive_rejected(self) -> None:
        groups = self._groups()
        cols = [
            Column(id=1, key="c1", label="C1", group="g1", type="string",
                   retired=True, derive=lambda row: row),
        ]
        with pytest.raises(ValueError, match="Retired column.*must not have derive"):
            validate_config(groups, cols)

    def test_hidden_with_derive_rejected(self) -> None:
        groups = self._groups()
        cols = [
            Column(id=1, key="c1", label="C1", group="g1", type="string",
                   hidden=True, derive=lambda row: row),
        ]
        with pytest.raises(ValueError, match="Hidden column.*must not have derive"):
            validate_config(groups, cols)

    def test_duplicate_group_keys_rejected(self) -> None:
        groups = [
            Group(id=0, key="g1", label="G1", order=0),
            Group(id=1, key="g1", label="G2", order=1),
        ]
        cols: list[Column] = []
        with pytest.raises(ValueError, match="Duplicate group key"):
            validate_config(groups, cols)

    def test_duplicate_group_ids_rejected(self) -> None:
        groups = [
            Group(id=0, key="g1", label="G1", order=0),
            Group(id=0, key="g2", label="G2", order=1),
        ]
        cols: list[Column] = []
        with pytest.raises(ValueError, match="Duplicate group id"):
            validate_config(groups, cols)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestHelpers:
    """Tests for active_columns, derive_columns, group_by_key."""

    def test_active_columns_excludes_hidden_and_retired(self) -> None:
        active = active_columns()
        for c in active:
            assert not c.hidden, f"{c.key} should not be hidden"
            assert not c.retired, f"{c.key} should not be retired"

    def test_derive_columns_all_have_callable(self) -> None:
        for c in derive_columns():
            assert callable(c.derive), f"{c.key} derive is not callable"

    def test_group_by_key_found(self) -> None:
        g = group_by_key("identity")
        assert isinstance(g, Group)
        assert g.key == "identity"

    def test_group_by_key_not_found_raises(self) -> None:
        with pytest.raises(KeyError):
            group_by_key("nonexistent_group")


# ---------------------------------------------------------------------------
# Production config sanity
# ---------------------------------------------------------------------------

class TestProductionConfig:
    """Sanity checks on the live COLUMNS / GROUPS lists."""

    def test_no_id_zero_in_columns(self) -> None:
        for c in COLUMNS:
            assert c.id != 0, f"Column {c.key!r} uses reserved id 0"

    def test_all_column_ids_unique(self) -> None:
        ids = [c.id for c in COLUMNS]
        assert len(ids) == len(set(ids)), "Column IDs are not unique"

    def test_all_column_keys_unique(self) -> None:
        keys = [c.key for c in COLUMNS]
        assert len(keys) == len(set(keys)), "Column keys are not unique"

    def test_all_groups_referenced_exist(self) -> None:
        group_keys = {g.key for g in GROUPS}
        for c in COLUMNS:
            assert c.group in group_keys, (
                f"Column {c.key!r} references unknown group {c.group!r}"
            )

    def test_at_least_29_columns(self) -> None:
        assert len(COLUMNS) >= 29, f"Expected >= 29 columns, got {len(COLUMNS)}"

    def test_truncate_limit_default_is_zero(self) -> None:
        """Columns without an explicit truncate_limit default to 0 (no truncation)."""
        # Pick a column that should not have truncation set
        year_col = next(c for c in COLUMNS if c.key == "year")
        assert year_col.truncate_limit == 0

    def test_manufacturer_has_truncate_limit_10(self) -> None:
        mfr = next(c for c in COLUMNS if c.key == "manufacturer")
        assert mfr.truncate_limit == 10

    def test_model_has_truncate_limit_10(self) -> None:
        model = next(c for c in COLUMNS if c.key == "model")
        assert model.truncate_limit == 10

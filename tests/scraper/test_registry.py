"""Tests for scraper.registry.IDRegistry."""

from __future__ import annotations

import json

import pytest
from scraper.registry import IDRegistry


class TestLoadSave:
    """Load/save round-trip tests."""

    def test_load_missing_file_creates_fresh(self, tmp_path):
        reg = IDRegistry.load(tmp_path / "missing.json")
        assert reg.models == {}
        assert reg.next_model_id == 1

    def test_load_existing_file(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text(json.dumps({
            "version": 2,
            "models": {"sony|hb-75p": 1},
            "retired_models": [],
            "next_model_id": 2,
        }))
        reg = IDRegistry.load(path)
        assert reg.models == {"sony|hb-75p": 1}
        assert reg.next_model_id == 2

    def test_load_v1_format_ignores_columns(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text(json.dumps({
            "version": 1,
            "columns": {"manufacturer": 1},
            "next_column_id": 30,
            "models": {"sony|hb-75p": 1},
            "retired_models": [],
            "next_model_id": 2,
        }))
        reg = IDRegistry.load(path)
        assert reg.models == {"sony|hb-75p": 1}
        assert reg.next_model_id == 2

    def test_load_corrupt_json_raises(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text("{bad json")
        with pytest.raises(ValueError, match="Failed to load"):
            IDRegistry.load(path)

    def test_save_then_load_roundtrip(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = IDRegistry(models={"a|b": 5, "c|d": 10}, next_model_id=11)
        reg.save(path)
        loaded = IDRegistry.load(path)
        assert loaded.models == reg.models
        assert loaded.next_model_id == reg.next_model_id

    def test_save_writes_version_2(self, tmp_path):
        path = tmp_path / "reg.json"
        IDRegistry().save(path)
        data = json.loads(path.read_text())
        assert data["version"] == 2
        assert "columns" not in data
        assert "next_column_id" not in data


class TestAssignModelId:
    """ID assignment tests."""

    def test_new_model_gets_next_id(self):
        reg = IDRegistry(next_model_id=1)
        assert reg.assign_model_id("sony|hb-75p") == 1
        assert reg.next_model_id == 2

    def test_existing_model_reuses_id(self):
        reg = IDRegistry(models={"sony|hb-75p": 1}, next_model_id=2)
        assert reg.assign_model_id("sony|hb-75p") == 1
        assert reg.next_model_id == 2  # unchanged

    def test_monotonic_increment(self):
        reg = IDRegistry(next_model_id=1)
        ids = [reg.assign_model_id(f"m|model{i}") for i in range(5)]
        assert ids == [1, 2, 3, 4, 5]
        assert reg.next_model_id == 6

    def test_idempotent_across_calls(self):
        reg = IDRegistry(next_model_id=1)
        id1 = reg.assign_model_id("sony|hb-75p")
        id2 = reg.assign_model_id("sony|hb-75p")
        assert id1 == id2 == 1
        assert reg.next_model_id == 2

    def test_id_zero_skipped(self):
        reg = IDRegistry(next_model_id=0)
        model_id = reg.assign_model_id("test|model")
        assert model_id == 1

    def test_uint16_overflow_raises(self):
        reg = IDRegistry(next_model_id=65536)
        with pytest.raises(OverflowError, match="uint16"):
            reg.assign_model_id("overflow|model")


class TestAssignModelIdFormerKeys:
    """An alias renames a model: its canonical key adopts an id from its former (pre-alias) keys."""

    def test_canonical_key_known_wins_over_former_keys(self):
        reg = IDRegistry(models={"sakhr|ax-170": 276, "sakhr|ax170": 5}, next_model_id=300)
        assert reg.assign_model_id("sakhr|ax-170", former_keys=["sakhr|ax170"]) == 276

    def test_former_key_id_is_adopted(self):
        reg = IDRegistry(models={"sakhr|ax230": 346}, next_model_id=400)
        assert reg.assign_model_id("sakhr|ax-230", former_keys=["sakhr|ax230"]) == 346
        assert reg.models["sakhr|ax-230"] == 346
        assert reg.next_model_id == 400  # no id spent

    def test_lowest_former_id_wins(self):
        reg = IDRegistry(models={"a|x1": 346, "a|x-1 (note)": 281}, next_model_id=400)
        assert reg.assign_model_id("a|x-1", former_keys=["a|x1", "a|x-1 (note)"]) == 281

    def test_former_keys_stay_in_registry(self):
        """Removing the alias later gives the model its old id back instead of a new one."""
        reg = IDRegistry(models={"a|x1": 7}, next_model_id=10)
        reg.assign_model_id("a|x-1", former_keys=["a|x1"])
        assert reg.models["a|x1"] == 7
        assert reg.assign_model_id("a|x1") == 7

    def test_unknown_former_keys_fall_back_to_new_id(self):
        reg = IDRegistry(next_model_id=10)
        assert reg.assign_model_id("a|x-1", former_keys=["a|x1"]) == 10
        assert reg.next_model_id == 11

    def test_taken_id_is_not_adopted_twice(self):
        """Two live models must never share an id, even if both descend from one former key."""
        reg = IDRegistry(models={"a|x1": 7, "a|x2": 8}, next_model_id=10)
        assert reg.assign_model_id("a|x-1", former_keys=["a|x1", "a|x2"], taken={7}) == 8
        assert reg.assign_model_id("a|x-9", former_keys=["a|x1"], taken={7, 8}) == 10

    def test_retired_former_id_is_not_adopted(self):
        reg = IDRegistry(models={"a|x1": 7}, retired_models=[7], next_model_id=10)
        assert reg.assign_model_id("a|x-1", former_keys=["a|x1"]) == 10


class TestRetireModel:
    """Retirement tests."""

    def test_retire_existing_model(self):
        reg = IDRegistry(models={"a|b": 5}, next_model_id=6)
        retired_id = reg.retire_model("a|b")
        assert retired_id == 5
        assert 5 in reg.retired_models

    def test_retire_unknown_model_returns_none(self):
        reg = IDRegistry()
        assert reg.retire_model("unknown|model") is None

    def test_retire_idempotent(self):
        reg = IDRegistry(models={"a|b": 5}, next_model_id=6)
        reg.retire_model("a|b")
        reg.retire_model("a|b")
        assert reg.retired_models.count(5) == 1

    def test_retired_id_not_reused(self):
        reg = IDRegistry(models={"old|model": 3}, next_model_id=4)
        reg.retire_model("old|model")
        new_id = reg.assign_model_id("new|model")
        assert new_id == 4  # not 3


class TestGetModelId:
    """Lookup without assignment."""

    def test_known_model(self):
        reg = IDRegistry(models={"a|b": 5})
        assert reg.get_model_id("a|b") == 5

    def test_unknown_model(self):
        reg = IDRegistry()
        assert reg.get_model_id("unknown|x") is None

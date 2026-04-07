"""Integration test for the build pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scraper.build import build, load_scraper_config
from scraper.registry import IDRegistry


class TestBuildPipeline:
    """End-to-end build from cached raw data."""

    def test_build_produces_data_js(self, tmp_path):
        """Build from fixture data produces a valid data.js."""
        # Create minimal cached raw data
        openmsx = [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
             "year": 1985, "region": "Europe", "vdp": "V9938", "vram_kb": 128,
             "main_ram_kb": 64, "openmsx_id": "Sony_HB-75P"},
        ]
        msxorg = [
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2",
             "year": 1985, "region": "Europe", "msxorg_title": "Sony HB-75P"},
        ]

        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        registry_path = tmp_path / "registry.json"
        output_path = tmp_path / "data.js"

        openmsx_path.write_text(json.dumps(openmsx))
        msxorg_path.write_text(json.dumps(msxorg))

        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=registry_path,
            output_path=output_path,
        )

        # data.js exists and contains window.MSX_DATA
        content = output_path.read_text()
        assert "window.MSX_DATA" in content

        # Registry was created with at least one model
        reg = IDRegistry.load(registry_path)
        assert len(reg.models) >= 1
        assert reg.next_model_id > 1

    def test_build_is_idempotent(self, tmp_path):
        """Running build twice produces identical output."""
        raw = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]

        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        registry_path = tmp_path / "registry.json"
        output_path = tmp_path / "data.js"

        openmsx_path.write_text(json.dumps(raw))
        msxorg_path.write_text(json.dumps([]))

        build(openmsx_path=openmsx_path, msxorg_path=msxorg_path,
              registry_path=registry_path, output_path=output_path)
        content1 = output_path.read_text()
        reg1 = registry_path.read_text()

        build(openmsx_path=openmsx_path, msxorg_path=msxorg_path,
              registry_path=registry_path, output_path=output_path)
        content2 = output_path.read_text()
        reg2 = registry_path.read_text()

        assert content1 == content2
        assert reg1 == reg2

    def test_build_missing_cache_without_fetch_errors(self, tmp_path):
        """Build without cached data and without --fetch raises FileNotFoundError."""
        import pytest
        with pytest.raises(FileNotFoundError, match="Cached openMSX"):
            build(
                openmsx_path=tmp_path / "missing.json",
                msxorg_path=tmp_path / "also_missing.json",
                registry_path=tmp_path / "reg.json",
                output_path=tmp_path / "data.js",
            )

    def test_seed_model_ids_preserved(self, tmp_path):
        """Existing registry IDs are preserved across builds."""
        # Pre-seed registry with known model
        reg_path = tmp_path / "registry.json"
        reg_path.write_text(json.dumps({
            "version": 2,
            "models": {"sony|hb-75p": 42},
            "retired_models": [],
            "next_model_id": 43,
        }))

        raw = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        output_path = tmp_path / "data.js"

        openmsx_path.write_text(json.dumps(raw))
        msxorg_path.write_text(json.dumps([]))

        build(openmsx_path=openmsx_path, msxorg_path=msxorg_path,
              registry_path=reg_path, output_path=output_path)

        reg = IDRegistry.load(reg_path)
        assert reg.models["sony|hb-75p"] == 42  # preserved


class TestBuildSlotmapLUT:
    """Integration tests for slotmap LUT wired into build pipeline."""

    STARTER_ABBRS = {
        "MAIN", "SUB", "KAN", "HAN", "JE", "MOD", "DOS2", "CP/M",
        "FW", "DSK", "MUS", "RS", "RSFW", "MM", "PM",
        "RAM", "BUN", "SFG5", "SFG1", "EXP", "\u2327", "\u2022",
        "CS1", "CS2", "CS3", "CS4",
    }

    def _run_build(self, tmp_path):
        raw = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        output_path = tmp_path / "data.js"
        openmsx_path.write_text(json.dumps(raw))
        msxorg_path.write_text(json.dumps([]))
        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=tmp_path / "registry.json",
            output_path=output_path,
        )
        return output_path

    def test_data_js_contains_slotmap_lut_key(self, tmp_path):
        output_path = self._run_build(tmp_path)
        content = output_path.read_text(encoding="utf-8")
        assert '"slotmap_lut"' in content

    def test_slotmap_lut_has_all_starter_abbrs(self, tmp_path):
        output_path = self._run_build(tmp_path)
        # Extract the JSON payload from window.MSX_DATA = {...};
        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        data = json.loads(content[json_start:json_end])
        lut = data.get("slotmap_lut", {})
        assert isinstance(lut, dict)
        assert set(lut.keys()) == self.STARTER_ABBRS

    def test_slotmap_lut_values_are_strings(self, tmp_path):
        output_path = self._run_build(tmp_path)
        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        data = json.loads(content[json_start:json_end])
        for abbr, tooltip in data["slotmap_lut"].items():
            assert isinstance(tooltip, str), f"Tooltip for {abbr!r} is not a string"

    def test_data_js_has_13_groups(self, tmp_path):
        output_path = self._run_build(tmp_path)
        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        data = json.loads(content[json_start:json_end])
        assert len(data["groups"]) == 13

    def test_data_js_has_93_columns(self, tmp_path):
        output_path = self._run_build(tmp_path)
        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        data = json.loads(content[json_start:json_end])
        assert len(data["columns"]) == 93

    def test_missing_lut_file_aborts_build(self, tmp_path):
        import pytest
        raw = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        openmsx_path.write_text(json.dumps(raw))
        msxorg_path.write_text(json.dumps([]))
        with pytest.raises(FileNotFoundError, match="(?i)slot.?map"):
            build(
                openmsx_path=openmsx_path,
                msxorg_path=msxorg_path,
                registry_path=tmp_path / "registry.json",
                output_path=tmp_path / "data.js",
                slotmap_lut_path=tmp_path / "nonexistent-lut.json",
            )


class TestBuildExcludeList:
    """Integration tests for exclude list wired into build pipeline."""

    def _fixture(self, tmp_path):
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        registry_path = tmp_path / "registry.json"
        output_path = tmp_path / "data.js"
        openmsx_path.write_text(json.dumps([
            {"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"},
            {"manufacturer": "Philips", "model": "NMS 8250", "standard": "MSX2"},
        ]))
        msxorg_path.write_text(json.dumps([]))
        return openmsx_path, msxorg_path, registry_path, output_path

    def test_excluded_model_absent_from_output(self, tmp_path):
        """A model matching an exclude rule does not appear in data.js."""
        import re
        openmsx_path, msxorg_path, registry_path, output_path = self._fixture(tmp_path)
        exclude_path = tmp_path / "exclude.json"
        exclude_path.write_text(json.dumps([
            {"manufacturer": "Sony", "model": "HB-75P"},
        ]))

        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=registry_path,
            exclude_path=exclude_path,
            output_path=output_path,
        )

        content = output_path.read_text()
        # Philips present, Sony absent
        assert "NMS 8250" in content or "Philips" in content
        assert "HB-75P" not in content

    def test_empty_excludelist_is_noop(self, tmp_path):
        """An empty exclude.json leaves output identical to no-exclude baseline."""
        openmsx_path, msxorg_path, registry_path, output_path = self._fixture(tmp_path)
        exclude_path = tmp_path / "exclude.json"
        exclude_path.write_text("[]")

        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=registry_path,
            exclude_path=exclude_path,
            output_path=output_path,
        )

        content = output_path.read_text()
        assert "HB-75P" in content
        assert "NMS 8250" in content or "Philips" in content


class TestBuildSlotmapExtractor:
    """Integration: slotmap keys appear in data.js when model has slotmap data."""

    def test_slotmap_keys_present_in_model_values(self, tmp_path):
        """A model dict with slotmap keys produces correct positional values in data.js."""
        # Build a model that already has slotmap keys (as if extracted by the scraper)
        # Empty/absent pages are None; ☒ only appears on SS0 empty pages of non-expanded primaries
        slotmap_data = {f"slotmap_{ms}_{ss}_{p}": None
                        for ms in range(4) for ss in range(4) for p in range(4)}
        # Override a few known cells
        slotmap_data["slotmap_0_0_0"] = "MAIN"
        slotmap_data["slotmap_0_0_1"] = "MAIN"
        slotmap_data["slotmap_1_0_0"] = "CS1"

        openmsx = [{"manufacturer": "Sony", "model": "HB-F1XV",
                    "standard": "MSX2+", **slotmap_data}]
        msxorg = []

        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        output_path = tmp_path / "data.js"

        openmsx_path.write_text(json.dumps(openmsx))
        msxorg_path.write_text(json.dumps(msxorg))

        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=tmp_path / "registry.json",
            output_path=output_path,
        )

        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        data = json.loads(content[json_start:json_end])

        # Find the slotmap_0_0_0 column position
        col_keys = [c["key"] for c in data["columns"]]
        assert "slotmap_0_0_0" in col_keys
        assert "slotmap_1_0_0" in col_keys

        model = data["models"][0]
        idx_main = col_keys.index("slotmap_0_0_0")
        idx_cs1 = col_keys.index("slotmap_1_0_0")

        assert model["values"][idx_main] == "MAIN"
        assert model["values"][idx_cs1] == "CS1"


class TestBuildTruncateLimit:
    """Tests for truncateLimit serialisation in ColumnDef output."""

    def _build_and_parse(self, tmp_path) -> dict:
        raw = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]
        openmsx_path = tmp_path / "openmsx.json"
        msxorg_path = tmp_path / "msxorg.json"
        output_path = tmp_path / "data.js"
        openmsx_path.write_text(json.dumps(raw))
        msxorg_path.write_text(json.dumps([]))
        from scraper.build import build
        build(
            openmsx_path=openmsx_path,
            msxorg_path=msxorg_path,
            registry_path=tmp_path / "registry.json",
            output_path=output_path,
        )
        content = output_path.read_text(encoding="utf-8")
        json_start = content.index("window.MSX_DATA = ") + len("window.MSX_DATA = ")
        json_end = content.rindex(";")
        return json.loads(content[json_start:json_end])

    def test_manufacturer_column_has_truncate_limit(self, tmp_path):
        data = self._build_and_parse(tmp_path)
        col = next(c for c in data["columns"] if c["key"] == "manufacturer")
        assert col.get("truncateLimit") == 12

    def test_model_column_has_truncate_limit(self, tmp_path):
        data = self._build_and_parse(tmp_path)
        col = next(c for c in data["columns"] if c["key"] == "model")
        assert col.get("truncateLimit") == 16

    def test_other_column_omits_truncate_limit(self, tmp_path):
        """Columns with truncate_limit=0 must NOT emit truncateLimit."""
        data = self._build_and_parse(tmp_path)
        year_col = next(c for c in data["columns"] if c["key"] == "year")
        assert "truncateLimit" not in year_col


# ---------------------------------------------------------------------------
# load_scraper_config
# ---------------------------------------------------------------------------

class TestLoadScraperConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_scraper_config(tmp_path / "no-such-file.json")
        assert result == {}

    def test_empty_object_returns_empty(self, tmp_path):
        cfg = tmp_path / "scraper-config.json"
        cfg.write_text("{}")
        assert load_scraper_config(cfg) == {}

    def test_mirror_path_key_returned(self, tmp_path):
        cfg = tmp_path / "scraper-config.json"
        cfg.write_text('{"msxorg_mirror_path": "/some/path"}')
        result = load_scraper_config(cfg)
        assert result["msxorg_mirror_path"] == "/some/path"

    def test_malformed_json_returns_empty(self, tmp_path):
        cfg = tmp_path / "scraper-config.json"
        cfg.write_text("not json {{{")
        result = load_scraper_config(cfg)
        assert result == {}


# ---------------------------------------------------------------------------
# Mirror path wiring through build()
# ---------------------------------------------------------------------------

class TestBuildMirrorWiring:
    """mirror_path reaches msxorg.fetch_all as a MirrorPageSource."""

    _OPENMSX = [{"manufacturer": "Sony", "model": "HB-75P", "standard": "MSX2"}]
    _MSXORG: list = []

    def _write_cache(self, tmp_path: Path) -> tuple[Path, Path]:
        op = tmp_path / "openmsx.json"
        mx = tmp_path / "msxorg.json"
        op.write_text(json.dumps(self._OPENMSX))
        mx.write_text(json.dumps(self._MSXORG))
        return op, mx

    def test_explicit_mirror_path_passed_to_fetch_sources(self, tmp_path):
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        op, mx = self._write_cache(tmp_path)

        captured = {}

        import scraper.build as build_mod
        original_fetch = build_mod.fetch_sources

        def fake_fetch(**kwargs):
            captured["mirror_path"] = kwargs.get("mirror_path")

        with patch.object(build_mod, "fetch_sources", side_effect=fake_fetch):
            build(
                do_fetch=True,
                openmsx_path=op,
                msxorg_path=mx,
                output_path=tmp_path / "data.js",
                mirror_path=mirror_dir,
            )

        assert captured["mirror_path"] == mirror_dir

    def test_config_mirror_path_used_when_no_flag(self, tmp_path):
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        cfg = tmp_path / "scraper-config.json"
        cfg.write_text(json.dumps({"msxorg_mirror_path": str(mirror_dir)}))
        op, mx = self._write_cache(tmp_path)

        captured = {}

        import scraper.build as build_mod
        original_load = build_mod.load_scraper_config

        def fake_load(path=None):
            return {"msxorg_mirror_path": str(mirror_dir)}

        def fake_fetch(**kwargs):
            captured["mirror_path"] = kwargs.get("mirror_path")

        with patch.object(build_mod, "load_scraper_config", side_effect=fake_load), \
             patch.object(build_mod, "fetch_sources", side_effect=fake_fetch):
            build(
                do_fetch=True,
                openmsx_path=op,
                msxorg_path=mx,
                output_path=tmp_path / "data.js",
            )

        assert captured["mirror_path"] == Path(str(mirror_dir))

    def test_explicit_flag_overrides_config(self, tmp_path):
        flag_dir = tmp_path / "flag_mirror"
        config_dir = tmp_path / "config_mirror"
        flag_dir.mkdir()
        config_dir.mkdir()
        op, mx = self._write_cache(tmp_path)

        captured = {}

        import scraper.build as build_mod

        def fake_load(path=None):
            return {"msxorg_mirror_path": str(config_dir)}

        def fake_fetch(**kwargs):
            captured["mirror_path"] = kwargs.get("mirror_path")

        with patch.object(build_mod, "load_scraper_config", side_effect=fake_load), \
             patch.object(build_mod, "fetch_sources", side_effect=fake_fetch):
            build(
                do_fetch=True,
                openmsx_path=op,
                msxorg_path=mx,
                output_path=tmp_path / "data.js",
                mirror_path=flag_dir,
            )

        assert captured["mirror_path"] == flag_dir

    def test_no_mirror_configured_uses_none(self, tmp_path):
        op, mx = self._write_cache(tmp_path)
        captured = {}

        import scraper.build as build_mod

        def fake_load(path=None):
            return {}

        def fake_fetch(**kwargs):
            captured["mirror_path"] = kwargs.get("mirror_path")

        with patch.object(build_mod, "load_scraper_config", side_effect=fake_load), \
             patch.object(build_mod, "fetch_sources", side_effect=fake_fetch):
            build(
                do_fetch=True,
                openmsx_path=op,
                msxorg_path=mx,
                output_path=tmp_path / "data.js",
            )

        assert captured["mirror_path"] is None

"""Integration test for the build pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from scraper.build import build
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

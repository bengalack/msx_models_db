# Column Config + ID Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a single-source column configuration (`scraper/columns.py`) that drives all column/group definitions, derived columns, and data.js generation — plus a model ID registry — so the maintainer edits one file to add/remove/retire columns.

**Architecture:** `scraper/columns.py` defines Groups, Columns (with metadata, derive functions, hidden/retired flags). A new `scraper/registry.py` manages model ID assignment. A new `scraper/build.py` orchestrates the pipeline: merge cached data → derive → assign IDs → write `data.js`. The web page is unchanged — it already reads everything from `window.MSX_DATA`.

**Tech Stack:** Python 3.11+, pytest, dataclasses. No new dependencies beyond adding pytest to dev requirements.

---

## Prerequisites

Install pytest (not yet in the project):
```bash
pip install pytest
```

---

### Task 1: Column and Group dataclasses

**Files:**
- Create: `scraper/columns.py`

**Step 1: Write the Group and Column dataclasses**

```python
"""Column and group definitions — single source of truth for the entire project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Group:
    """A collapsible group of columns."""
    id: int
    key: str
    label: str
    order: int


@dataclass
class Column:
    """A single grid column definition."""
    id: int
    key: str
    label: str
    group: str                # group key — resolved to groupId at build time
    type: str                 # "string" | "number" | "boolean"
    short_label: str | None = None
    tooltip: str | None = None
    linkable: bool = False
    hidden: bool = False      # scraped, available to derive, not shipped to browser
    retired: bool = False     # permanently removed, ID preserved, excluded entirely
    derive: Callable[[dict[str, Any]], Any] | None = None
```

**Step 2: Add validation function**

Append to `scraper/columns.py`:

```python
def validate_config(groups: list[Group], columns: list[Column]) -> None:
    """Validate column/group configuration. Raises ValueError on problems."""
    # Group keys must be unique
    group_keys = [g.key for g in groups]
    if len(group_keys) != len(set(group_keys)):
        raise ValueError("Duplicate group keys")

    # Group IDs must be unique
    group_ids = [g.id for g in groups]
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("Duplicate group IDs")

    group_key_set = set(group_keys)

    col_ids: list[int] = []
    col_keys: list[str] = []
    for col in columns:
        # ID 0 reserved
        if col.id == 0:
            raise ValueError(f"Column ID 0 is reserved (column: {col.key!r})")

        # Group must exist
        if col.group not in group_key_set:
            raise ValueError(f"Column {col.key!r} references unknown group {col.group!r}")

        # Cannot be both hidden and retired
        if col.hidden and col.retired:
            raise ValueError(f"Column {col.key!r} cannot be both hidden and retired")

        # Derive rules
        if col.derive is not None and col.retired:
            raise ValueError(f"Retired column {col.key!r} must not have a derive function")
        if col.derive is not None and col.hidden:
            raise ValueError(f"Hidden column {col.key!r} must not have a derive function (hidden columns are scraped, not derived)")

        col_ids.append(col.id)
        col_keys.append(col.key)

    # Unique IDs and keys
    if len(col_ids) != len(set(col_ids)):
        raise ValueError("Duplicate column IDs")
    if len(col_keys) != len(set(col_keys)):
        raise ValueError("Duplicate column keys")
```

**Step 3: Add the GROUPS and COLUMNS definitions**

Append to `scraper/columns.py` — migrating from `src/columns.ts`:

```python
# ── Group definitions ─────────────────────────────────────────────────────

GROUPS: list[Group] = [
    Group(id=0, key="identity",  label="Identity",     order=0),
    Group(id=1, key="memory",    label="Memory",        order=1),
    Group(id=2, key="video",     label="Video",         order=2),
    Group(id=3, key="audio",     label="Audio",         order=3),
    Group(id=4, key="media",     label="Media",         order=4),
    Group(id=5, key="cpu",       label="CPU/Chipsets",  order=5),
    Group(id=6, key="other",     label="Other",         order=6),
    Group(id=7, key="emulation", label="Emulation",     order=7),
]


# ── Column definitions ────────────────────────────────────────────────────
# Display order = list order. IDs are stable and permanent.

COLUMNS: list[Column] = [
    # Identity
    Column(id=1,  key="manufacturer",     label="Manufacturer",         group="identity", type="string"),
    Column(id=2,  key="model",            label="Model",                group="identity", type="string", linkable=True),
    Column(id=3,  key="year",             label="Year",                 group="identity", type="number"),
    Column(id=4,  key="region",           label="Region",               group="identity", type="string"),
    Column(id=5,  key="standard",         label="MSX Standard",         group="identity", type="string"),
    Column(id=6,  key="form_factor",      label="Form Factor",          group="identity", type="string"),
    # Memory
    Column(id=7,  key="main_ram_kb",      label="Main RAM (KB)",        group="memory", type="number",  short_label="Main RAM",    tooltip="Main RAM (KB)"),
    Column(id=8,  key="vram_kb",          label="VRAM (KB)",            group="memory", type="number",  short_label="VRAM",        tooltip="VRAM (KB)"),
    Column(id=9,  key="rom_kb",           label="ROM/BIOS (KB)",        group="memory", type="number",  short_label="ROM/ BIOS",   tooltip="ROM/BIOS (KB)"),
    Column(id=10, key="mapper",           label="Mapper",               group="memory", type="string"),
    # Video
    Column(id=11, key="vdp",              label="VDP",                  group="video",  type="string"),
    Column(id=12, key="max_resolution",   label="Max Resolution",       group="video",  type="string",  short_label="Max Res",     tooltip="Max Resolution"),
    Column(id=13, key="max_colors",       label="Max Colors",           group="video",  type="number",  short_label="Max Clrs",    tooltip="Max Colors"),
    Column(id=14, key="max_sprites",      label="Max Sprites",          group="video",  type="number",  short_label="Max Sprt",    tooltip="Max Sprites"),
    # Audio
    Column(id=15, key="psg",              label="PSG",                  group="audio",  type="string"),
    Column(id=16, key="fm_chip",          label="FM Chip",              group="audio",  type="string"),
    Column(id=17, key="audio_channels",   label="Audio Channels",       group="audio",  type="number",  short_label="PSG Chnls",   tooltip="PSG Channels"),
    # Media
    Column(id=18, key="floppy_drives",    label="Floppy Drive(s)",      group="media",  type="string",  short_label="Floppy Drv",  tooltip="Floppy Drive(s)"),
    Column(id=19, key="cartridge_slots",  label="Cartridge Slots",      group="media",  type="number",  short_label="Cart Slots",  tooltip="Cartridge Slots"),
    Column(id=20, key="tape_interface",   label="Tape Interface",       group="media",  type="string",  short_label="Tape I/F",    tooltip="Tape Interface"),
    Column(id=21, key="other_storage",    label="Other Storage",        group="media",  type="string",  short_label="Other Stor",  tooltip="Other Storage"),
    # CPU/Chipsets
    Column(id=22, key="cpu",              label="CPU",                  group="cpu",    type="string"),
    Column(id=23, key="cpu_speed_mhz",    label="CPU Speed (MHz)",      group="cpu",    type="number",  short_label="CPU MHz",     tooltip="CPU Speed (MHz)"),
    Column(id=24, key="sub_cpu",          label="Sub-CPU",              group="cpu",    type="string"),
    # Other
    Column(id=25, key="keyboard_layout",  label="Keyboard Layout",      group="other",  type="string",  short_label="KB Layout",   tooltip="Keyboard Layout"),
    Column(id=26, key="built_in_software",label="Built-in Software",    group="other",  type="string",  short_label="Built-in SW", tooltip="Built-in Software"),
    Column(id=27, key="connectivity",     label="Connectivity/Ports",   group="other",  type="string",  short_label="Conn/ Ports", tooltip="Connectivity/Ports"),
    # Emulation
    Column(id=28, key="openmsx_id",       label="openMSX Machine ID",   group="emulation", type="string", short_label="openMSX ID",   tooltip="openMSX Machine ID"),
    Column(id=29, key="fpga_support",     label="FPGA/MiSTer Support",  group="emulation", type="string", short_label="FPGA/ MiSTer", tooltip="FPGA/MiSTer Support"),
]


# ── Validate at import time ───────────────────────────────────────────────
validate_config(GROUPS, COLUMNS)
```

**Step 4: Add helper functions for consumers**

Append to `scraper/columns.py`:

```python
def active_columns() -> list[Column]:
    """Columns that appear in data.js (not hidden, not retired)."""
    return [c for c in COLUMNS if not c.hidden and not c.retired]


def derive_columns() -> list[Column]:
    """Columns that have a derive function."""
    return [c for c in COLUMNS if c.derive is not None]


def group_by_key(key: str) -> Group:
    """Look up a group by key. Raises KeyError if not found."""
    for g in GROUPS:
        if g.key == key:
            return g
    raise KeyError(f"Unknown group key: {key!r}")
```

**Step 5: Commit**

```bash
git add scraper/columns.py
git commit -m "feat: add single-source column configuration with groups, columns, and validation"
```

---

### Task 2: Column config unit tests

**Files:**
- Create: `tests/scraper/__init__.py`
- Create: `tests/scraper/test_columns.py`

**Step 1: Create test package init**

```python
# tests/scraper/__init__.py — empty
```

**Step 2: Write tests for validation**

```python
"""Tests for scraper.columns validation and helpers."""

from __future__ import annotations

import pytest
from scraper.columns import (
    Column, Group, COLUMNS, GROUPS,
    validate_config, active_columns, derive_columns, group_by_key,
)


# ── Validation tests ──────────────────────────────────────────────────────


class TestValidateConfig:
    """Tests for validate_config()."""

    def _groups(self) -> list[Group]:
        return [Group(id=0, key="g1", label="G1", order=0)]

    def test_valid_config_passes(self):
        cols = [Column(id=1, key="c1", label="C1", group="g1", type="string")]
        validate_config(self._groups(), cols)  # no exception

    def test_duplicate_column_ids_rejected(self):
        cols = [
            Column(id=1, key="a", label="A", group="g1", type="string"),
            Column(id=1, key="b", label="B", group="g1", type="string"),
        ]
        with pytest.raises(ValueError, match="Duplicate column IDs"):
            validate_config(self._groups(), cols)

    def test_duplicate_column_keys_rejected(self):
        cols = [
            Column(id=1, key="a", label="A", group="g1", type="string"),
            Column(id=2, key="a", label="A2", group="g1", type="string"),
        ]
        with pytest.raises(ValueError, match="Duplicate column keys"):
            validate_config(self._groups(), cols)

    def test_id_zero_rejected(self):
        cols = [Column(id=0, key="bad", label="Bad", group="g1", type="string")]
        with pytest.raises(ValueError, match="ID 0 is reserved"):
            validate_config(self._groups(), cols)

    def test_unknown_group_rejected(self):
        cols = [Column(id=1, key="c1", label="C1", group="nope", type="string")]
        with pytest.raises(ValueError, match="unknown group"):
            validate_config(self._groups(), cols)

    def test_hidden_and_retired_rejected(self):
        cols = [Column(id=1, key="c1", label="C1", group="g1", type="string",
                       hidden=True, retired=True)]
        with pytest.raises(ValueError, match="both hidden and retired"):
            validate_config(self._groups(), cols)

    def test_retired_with_derive_rejected(self):
        cols = [Column(id=1, key="c1", label="C1", group="g1", type="string",
                       retired=True, derive=lambda r: "x")]
        with pytest.raises(ValueError, match="Retired column.*derive"):
            validate_config(self._groups(), cols)

    def test_hidden_with_derive_rejected(self):
        cols = [Column(id=1, key="c1", label="C1", group="g1", type="string",
                       hidden=True, derive=lambda r: "x")]
        with pytest.raises(ValueError, match="Hidden column.*derive"):
            validate_config(self._groups(), cols)

    def test_duplicate_group_keys_rejected(self):
        groups = [
            Group(id=0, key="g1", label="G1", order=0),
            Group(id=1, key="g1", label="G2", order=1),
        ]
        with pytest.raises(ValueError, match="Duplicate group keys"):
            validate_config(groups, [])

    def test_duplicate_group_ids_rejected(self):
        groups = [
            Group(id=0, key="g1", label="G1", order=0),
            Group(id=0, key="g2", label="G2", order=1),
        ]
        with pytest.raises(ValueError, match="Duplicate group IDs"):
            validate_config(groups, [])


# ── Helper tests ──────────────────────────────────────────────────────────


class TestHelpers:
    """Tests for active_columns, derive_columns, group_by_key."""

    def test_active_columns_excludes_hidden_and_retired(self):
        active = active_columns()
        for col in active:
            assert not col.hidden
            assert not col.retired

    def test_derive_columns_all_have_callable(self):
        for col in derive_columns():
            assert col.derive is not None
            assert callable(col.derive)

    def test_group_by_key_found(self):
        g = group_by_key("identity")
        assert g.key == "identity"
        assert g.id == 0

    def test_group_by_key_not_found(self):
        with pytest.raises(KeyError):
            group_by_key("nonexistent")


# ── Production config sanity ──────────────────────────────────────────────


class TestProductionConfig:
    """Sanity checks on the actual GROUPS and COLUMNS."""

    def test_no_id_zero_in_columns(self):
        for col in COLUMNS:
            assert col.id != 0, f"Column {col.key!r} has reserved ID 0"

    def test_all_column_ids_unique(self):
        ids = [c.id for c in COLUMNS]
        assert len(ids) == len(set(ids))

    def test_all_column_keys_unique(self):
        keys = [c.key for c in COLUMNS]
        assert len(keys) == len(set(keys))

    def test_all_groups_referenced(self):
        used = {c.group for c in COLUMNS if not c.retired}
        defined = {g.key for g in GROUPS}
        assert used <= defined

    def test_columns_count_matches_seed(self):
        """There should be at least 29 columns (matching the seed data)."""
        assert len(COLUMNS) >= 29
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/scraper/test_columns.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/scraper/__init__.py tests/scraper/test_columns.py
git commit -m "test: add column config validation and helper tests"
```

---

### Task 3: ID Registry module (model IDs only)

**Files:**
- Create: `scraper/registry.py`

**Step 1: Write the IDRegistry class**

```python
"""Model ID registry — assigns and preserves stable integer IDs for models."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class IDRegistry:
    """Manages stable model ID assignment across scraper runs.

    Column IDs are defined in scraper/columns.py and not tracked here.
    """

    def __init__(
        self,
        models: dict[str, int] | None = None,
        retired_models: list[int] | None = None,
        next_model_id: int = 1,
    ) -> None:
        self.models: dict[str, int] = dict(models) if models else {}
        self.retired_models: list[int] = list(retired_models) if retired_models else []
        self.next_model_id: int = next_model_id
        self._retired_set: set[int] = set(self.retired_models)

    # ── Load / Save ────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> IDRegistry:
        """Load registry from JSON file. Creates fresh registry if file not found."""
        if not path.exists():
            log.warning("[registry:load] File not found, starting fresh | path=%s", path)
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to load registry from {path}: {e}") from e

        version = data.get("version", 1)
        models = data.get("models", {})
        retired = data.get("retired_models", [])

        # Handle v1 format (has columns section — ignore it)
        if version == 1:
            next_id = data.get("next_model_id", 1)
        else:
            next_id = data.get("next_model_id", 1)

        reg = cls(models=models, retired_models=retired, next_model_id=next_id)
        log.info(
            "[registry:load] Loaded | path=%s model_count=%d next_model_id=%d retired=%d",
            path, len(reg.models), reg.next_model_id, len(reg.retired_models),
        )
        return reg

    def save(self, path: Path) -> None:
        """Atomic write registry to JSON file."""
        data = {
            "version": 2,
            "models": self.models,
            "retired_models": sorted(self.retired_models),
            "next_model_id": self.next_model_id,
        }
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        # Write to temp file then atomic rename
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=path.stem,
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp, str(path))
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

        log.info(
            "[registry:save] Written | path=%s model_count=%d next_model_id=%d",
            path, len(self.models), self.next_model_id,
        )

    # ── ID assignment ──────────────────────────────────────────────────

    def assign_model_id(self, natural_key: str) -> int:
        """Return the stable ID for a model, assigning a new one if needed.

        Natural key format: "manufacturer|model" (lowercased, stripped).
        """
        existing = self.models.get(natural_key)
        if existing is not None:
            return existing

        new_id = self.next_model_id
        if new_id == 0:
            new_id = 1  # ID 0 is reserved
        if new_id > 65535:
            raise OverflowError(
                f"Model ID overflow: next_model_id={new_id} exceeds uint16 max (65535)"
            )

        self.models[natural_key] = new_id
        self.next_model_id = new_id + 1
        log.debug("[registry:assign] New model | key=%s id=%d", natural_key, new_id)
        return new_id

    def get_model_id(self, natural_key: str) -> int | None:
        """Look up a model ID without assigning. Returns None if not found."""
        return self.models.get(natural_key)

    def retire_model(self, natural_key: str) -> int | None:
        """Mark a model as retired. Returns the retired ID, or None if not found."""
        model_id = self.models.get(natural_key)
        if model_id is None:
            return None
        if model_id not in self._retired_set:
            self.retired_models.append(model_id)
            self._retired_set.add(model_id)
            log.info("[registry:retire] Model retired | key=%s id=%d", natural_key, model_id)
        return model_id
```

**Step 2: Commit**

```bash
git add scraper/registry.py
git commit -m "feat: add IDRegistry module for stable model ID assignment"
```

---

### Task 4: Registry unit tests

**Files:**
- Create: `tests/scraper/test_registry.py`

**Step 1: Write registry tests**

```python
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
```

**Step 2: Run tests**

Run: `pytest tests/scraper/test_registry.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/scraper/test_registry.py
git commit -m "test: add IDRegistry unit tests for load, save, assign, retire"
```

---

### Task 5: Build pipeline

**Files:**
- Create: `scraper/build.py`

**Step 1: Write the build module**

```python
"""Build pipeline: merge → derive → assign IDs → write data.js."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from . import merge, msxorg, openmsx
from .columns import (
    COLUMNS, GROUPS, Column,
    active_columns, group_by_key,
)
from .registry import IDRegistry

log = logging.getLogger(__name__)

# Default file paths
RAW_OPENMSX = Path("data/openmsx-raw.json")
RAW_MSXORG = Path("data/msxorg-raw.json")
REGISTRY_PATH = Path("data/id-registry.json")
DATA_JS_PATH = Path("docs/data.js")


def fetch_sources(
    *,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    delay: float = 0.3,
) -> None:
    """Fetch fresh data from external sources and cache to disk."""
    log.info("Fetching openMSX data…")
    openmsx_models = openmsx.fetch_all(delay=delay)
    _write_json(openmsx_models, openmsx_path)
    log.info("Wrote %d openMSX models to %s", len(openmsx_models), openmsx_path)

    log.info("Fetching msx.org data…")
    msxorg_models = msxorg.fetch_all(delay=delay)
    _write_json(msxorg_models, msxorg_path)
    log.info("Wrote %d msx.org models to %s", len(msxorg_models), msxorg_path)


def build(
    *,
    do_fetch: bool = False,
    openmsx_path: Path = RAW_OPENMSX,
    msxorg_path: Path = RAW_MSXORG,
    registry_path: Path = REGISTRY_PATH,
    output_path: Path = DATA_JS_PATH,
    resolutions_path: Path | None = None,
) -> None:
    """Run the full build pipeline."""
    # Step 0: Fetch if requested
    if do_fetch:
        fetch_sources(openmsx_path=openmsx_path, msxorg_path=msxorg_path)

    # Step 1: Load cached raw data
    if not openmsx_path.exists():
        raise FileNotFoundError(
            f"Cached openMSX data not found: {openmsx_path}\n"
            "Run with --fetch to download fresh data."
        )
    if not msxorg_path.exists():
        raise FileNotFoundError(
            f"Cached msx.org data not found: {msxorg_path}\n"
            "Run with --fetch to download fresh data."
        )

    with open(openmsx_path, encoding="utf-8") as f:
        openmsx_data = json.load(f)
    with open(msxorg_path, encoding="utf-8") as f:
        msxorg_data = json.load(f)

    log.info("Loaded %d openMSX + %d msx.org models from cache",
             len(openmsx_data), len(msxorg_data))

    # Step 2: Merge
    resolutions = {}
    if resolutions_path:
        resolutions = merge.load_resolutions(resolutions_path)

    merged, conflicts = merge.merge_models(openmsx_data, msxorg_data, resolutions=resolutions)
    merge.print_conflict_summary(conflicts)

    # Step 3: Derive computed columns
    derive_cols = [c for c in COLUMNS if c.derive is not None]
    for model in merged:
        for col in derive_cols:
            model[col.key] = col.derive(model)

    # Step 4: Assign model IDs
    registry = IDRegistry.load(registry_path)
    for model in merged:
        nk = merge.natural_key(model)
        model["_id"] = registry.assign_model_id(nk)

    # Step 5: Build data.js payload
    active_cols = active_columns()
    group_id_map = {g.key: g.id for g in GROUPS}

    js_groups = [
        {"id": g.id, "key": g.key, "label": g.label, "order": g.order}
        for g in GROUPS
    ]

    js_columns = []
    for col in active_cols:
        entry: dict[str, Any] = {
            "id": col.id,
            "key": col.key,
            "label": col.label,
            "groupId": group_id_map[col.group],
            "type": col.type,
        }
        if col.short_label:
            entry["shortLabel"] = col.short_label
        if col.tooltip:
            entry["tooltip"] = col.tooltip
        if col.linkable:
            entry["linkable"] = True
        js_columns.append(entry)

    js_models = []
    for model in merged:
        values = []
        for col in active_cols:
            val = model.get(col.key)
            values.append(val)

        record: dict[str, Any] = {
            "id": model["_id"],
            "values": values,
        }

        # Add links for linkable columns
        links: dict[str, str] = {}
        for col in active_cols:
            if col.linkable and col.key == "model":
                msxorg_title = model.get("msxorg_title")
                if msxorg_title:
                    links[col.key] = f"https://www.msx.org/wiki/{msxorg_title.replace(' ', '_')}"
        if links:
            record["links"] = links

        js_models.append(record)

    # Sort models by ID for stable output
    js_models.sort(key=lambda m: m["id"])

    payload = {
        "version": 1,
        "generated": date.today().isoformat(),
        "groups": js_groups,
        "columns": js_columns,
        "models": js_models,
    }

    # Step 6: Write output
    _write_data_js(payload, output_path)
    registry.save(registry_path)

    log.info(
        "Build complete: %d models, %d columns, %d groups → %s",
        len(js_models), len(js_columns), len(js_groups), output_path,
    )


def _write_json(data: Any, path: Path) -> None:
    """Write JSON with atomic rename."""
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _write_data_js(payload: dict[str, Any], path: Path) -> None:
    """Write docs/data.js in the window.MSX_DATA format."""
    json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    content = f"// MSX Models DB — generated by scraper build\n// Generated: {payload['generated']}\nwindow.MSX_DATA = {json_str};\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
```

**Step 2: Commit**

```bash
git add scraper/build.py
git commit -m "feat: add build pipeline — merge, derive, assign IDs, write data.js"
```

---

### Task 6: Wire build command into CLI

**Files:**
- Modify: `scraper/__main__.py`

**Step 1: Add `build` subcommand**

Add import at the top of `scraper/__main__.py`:

```python
from . import build as build_module
```

Add `cmd_build` function and wire it up:

```python
def cmd_build(args: argparse.Namespace) -> None:
    """Run the full build pipeline."""
    resolutions_path = Path(args.resolutions) if args.resolutions else None
    build_module.build(
        do_fetch=args.fetch,
        resolutions_path=resolutions_path,
    )
```

Add parser under the subparsers block:

```python
    # ── build ────────────────────────────────────────────────────────
    p_build = sub.add_parser(
        "build",
        help="Build data.js from cached data (or --fetch fresh data first)",
    )
    p_build.add_argument(
        "--fetch", action="store_true",
        help="Fetch fresh data from msx.org and openMSX GitHub before building",
    )
    p_build.add_argument(
        "--resolutions", default=None,
        help="Path to conflict resolution file",
    )
    p_build.set_defaults(func=cmd_build)
```

**Step 2: Verify CLI help**

Run: `python -m scraper build --help`
Expected: Shows build subcommand with `--fetch` and `--resolutions` flags.

**Step 3: Commit**

```bash
git add scraper/__main__.py
git commit -m "feat: add 'build' CLI command for single-step data.js generation"
```

---

### Task 7: Build pipeline integration test

**Files:**
- Create: `tests/scraper/test_build.py`

**Step 1: Write integration test**

```python
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
```

**Step 2: Run tests**

Run: `pytest tests/scraper/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/scraper/test_build.py
git commit -m "test: add build pipeline integration tests"
```

---

### Task 8: Delete src/columns.ts and verify web page unchanged

**Files:**
- Delete: `src/columns.ts`

**Step 1: Verify no runtime imports**

Run: `grep -r "from.*columns\|import.*columns" src/ --include="*.ts"`
Expected: No matches (already verified during design)

**Step 2: Delete the file**

```bash
rm src/columns.ts
```

**Step 3: Verify TypeScript build still works**

Run: `npm run typecheck`
Expected: PASS (no runtime code references columns.ts)

Run: `npm run build`
Expected: PASS

**Step 4: Commit**

```bash
git add -u src/columns.ts
git commit -m "chore: remove src/columns.ts — column config now in scraper/columns.py"
```

---

### Task 9: Run full build and verify end-to-end

**Step 1: Install pytest if not already installed**

```bash
pip install pytest
```

**Step 2: Run all Python tests**

Run: `pytest tests/scraper/ -v`
Expected: All PASS

**Step 3: Run the build pipeline with cached data**

```bash
python -m scraper build
```

Expected: Writes `docs/data.js` and updates `data/id-registry.json`

**Step 4: Verify data.js contents**

Check that `docs/data.js`:
- Contains `window.MSX_DATA`
- Has groups, columns, and models arrays
- Model count matches merged data (~158 models)
- No column has ID 0

**Step 5: Verify web page still works**

Run: `npm run build`
Expected: PASS — Vite bundles the TypeScript; data.js is separate

**Step 6: Run all web tests**

Run: `npm test -- --run`
Expected: All PASS

**Step 7: Commit generated files**

```bash
git add docs/data.js data/id-registry.json
git commit -m "chore: regenerate data.js and registry via scraper build"
```

---

### Task 10: Update backlog

**Files:**
- Modify: `.claude/artifacts/planning/product-backlog.md`

Move "ID registry (Python)" from Later to "In product (shipped)". Add "Column configuration (single source)" to "In product (shipped)". Update scraper items to reflect completed state.

```bash
git add .claude/artifacts/planning/product-backlog.md
git commit -m "chore: update backlog — column config and ID registry shipped"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Column/Group dataclasses + validation + COLUMNS/GROUPS config | — |
| 2 | Column config unit tests | 15 tests |
| 3 | IDRegistry module (model IDs only) | — |
| 4 | Registry unit tests | 14 tests |
| 5 | Build pipeline (merge → derive → IDs → data.js) | — |
| 6 | Wire `build` CLI command | — |
| 7 | Build integration tests | 4 tests |
| 8 | Delete `src/columns.ts` | typecheck + build verify |
| 9 | Full end-to-end verification | all tests + manual check |
| 10 | Update backlog | — |

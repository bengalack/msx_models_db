"""Single source of truth for column and group definitions.

Every column/group in the MSX Models DB is defined here.  The scraper,
the data-export step, and (via code-gen) the front-end all consume
these definitions so they can never drift out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Group:
    id: int
    key: str
    label: str
    order: int


@dataclass
class Column:
    id: int
    key: str
    label: str
    group: str                            # group key — resolved to groupId at build time
    type: str                             # "string" | "number" | "boolean"
    short_label: str | None = None
    tooltip: str | None = None
    linkable: bool = False
    hidden: bool = False                  # scraped, available to derive, not shipped to browser
    retired: bool = False                 # permanently removed, ID preserved, excluded entirely
    derive: Callable[[dict[str, Any]], Any] | None = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_config(groups: list[Group], columns: list[Column]) -> None:
    """Raise ``ValueError`` if the configuration is inconsistent."""

    # --- Groups ---
    group_ids: set[int] = set()
    group_keys: set[str] = set()
    for g in groups:
        if g.id in group_ids:
            raise ValueError(f"Duplicate group id: {g.id}")
        if g.key in group_keys:
            raise ValueError(f"Duplicate group key: {g.key!r}")
        group_ids.add(g.id)
        group_keys.add(g.key)

    # --- Columns ---
    col_ids: set[int] = set()
    col_keys: set[str] = set()
    for c in columns:
        if c.id == 0:
            raise ValueError("Column id 0 is reserved (sentinel)")
        if c.id in col_ids:
            raise ValueError(f"Duplicate column id: {c.id}")
        if c.key in col_keys:
            raise ValueError(f"Duplicate column key: {c.key!r}")
        if c.group not in group_keys:
            raise ValueError(
                f"Column {c.key!r} references unknown group {c.group!r}"
            )
        if c.hidden and c.retired:
            raise ValueError(
                f"Column {c.key!r} cannot be both hidden and retired"
            )
        if c.hidden and c.derive is not None:
            raise ValueError(
                f"Hidden column {c.key!r} must not have derive "
                "(hidden columns are scraped, not derived)"
            )
        if c.retired and c.derive is not None:
            raise ValueError(
                f"Retired column {c.key!r} must not have derive"
            )
        if c.derive is not None and not callable(c.derive):
            raise ValueError(
                f"Column {c.key!r} derive must be callable"
            )
        col_ids.add(c.id)
        col_keys.add(c.key)


# ---------------------------------------------------------------------------
# GROUPS  (migrated from src/columns.ts)
# ---------------------------------------------------------------------------

GROUPS: list[Group] = [
    Group(id=0, key="identity",  label="Identity",      order=0),
    Group(id=1, key="memory",    label="Memory",         order=1),
    Group(id=2, key="video",     label="Video",          order=2),
    Group(id=3, key="audio",     label="Audio",          order=3),
    Group(id=4, key="media",     label="Media",          order=4),
    Group(id=5, key="cpu",       label="CPU/Chipsets",   order=5),
    Group(id=6, key="other",     label="Other",          order=6),
    Group(id=7, key="emulation", label="Emulation",      order=7),
]


# ---------------------------------------------------------------------------
# COLUMNS  (migrated from src/columns.ts — 29 columns, IDs 1-29)
# ---------------------------------------------------------------------------

COLUMNS: list[Column] = [
    # Identity
    Column(id=1,  key="manufacturer",      label="Manufacturer",        group="identity", type="string"),
    Column(id=2,  key="model",             label="Model",               group="identity", type="string", linkable=True),
    Column(id=3,  key="year",              label="Year",                group="identity", type="number"),
    Column(id=4,  key="region",            label="Region",              group="identity", type="string"),
    Column(id=5,  key="standard",          label="MSX Standard",        group="identity", type="string"),
    Column(id=6,  key="form_factor",       label="Form Factor",         group="identity", type="string"),
    # Memory
    Column(id=7,  key="main_ram_kb",       label="Main RAM (KB)",       group="memory",   type="number", short_label="Main RAM",    tooltip="Main RAM (KB)"),
    Column(id=8,  key="vram_kb",           label="VRAM (KB)",           group="memory",   type="number", short_label="VRAM",         tooltip="VRAM (KB)"),
    Column(id=9,  key="rom_kb",            label="ROM/BIOS (KB)",       group="memory",   type="number", short_label="ROM/ BIOS",    tooltip="ROM/BIOS (KB)"),
    Column(id=10, key="mapper",            label="Mapper",              group="memory",   type="string"),
    # Video
    Column(id=11, key="vdp",              label="VDP",                  group="video",    type="string"),
    Column(id=12, key="max_resolution",   label="Max Resolution",       group="video",    type="string", short_label="Max Res",      tooltip="Max Resolution"),
    Column(id=13, key="max_colors",       label="Max Colors",           group="video",    type="number", short_label="Max Clrs",     tooltip="Max Colors"),
    Column(id=14, key="max_sprites",      label="Max Sprites",          group="video",    type="number", short_label="Max Sprt",     tooltip="Max Sprites"),
    # Audio
    Column(id=15, key="psg",              label="PSG",                  group="audio",    type="string"),
    Column(id=16, key="fm_chip",          label="FM Chip",              group="audio",    type="string"),
    Column(id=17, key="audio_channels",   label="Audio Channels",       group="audio",    type="number", short_label="PSG Chnls",    tooltip="PSG Channels"),
    # Media
    Column(id=18, key="floppy_drives",    label="Floppy Drive(s)",      group="media",    type="string", short_label="Floppy Drv",   tooltip="Floppy Drive(s)"),
    Column(id=19, key="cartridge_slots",  label="Cartridge Slots",      group="media",    type="number", short_label="Cart Slots",   tooltip="Cartridge Slots"),
    Column(id=20, key="tape_interface",   label="Tape Interface",       group="media",    type="string", short_label="Tape I/F",     tooltip="Tape Interface"),
    Column(id=21, key="other_storage",    label="Other Storage",        group="media",    type="string", short_label="Other Stor",   tooltip="Other Storage"),
    # CPU/Chipsets
    Column(id=22, key="cpu",              label="CPU",                  group="cpu",      type="string"),
    Column(id=23, key="cpu_speed_mhz",    label="CPU Speed (MHz)",      group="cpu",      type="number", short_label="CPU MHz",      tooltip="CPU Speed (MHz)"),
    Column(id=24, key="sub_cpu",          label="Sub-CPU",              group="cpu",      type="string"),
    # Other
    Column(id=25, key="keyboard_layout",  label="Keyboard Layout",      group="other",    type="string", short_label="KB Layout",    tooltip="Keyboard Layout"),
    Column(id=26, key="built_in_software", label="Built-in Software",   group="other",    type="string", short_label="Built-in SW",  tooltip="Built-in Software"),
    Column(id=27, key="connectivity",     label="Connectivity/Ports",   group="other",    type="string", short_label="Conn/ Ports",  tooltip="Connectivity/Ports"),
    # Emulation
    Column(id=28, key="openmsx_id",       label="openMSX Machine ID",   group="emulation", type="string", short_label="openMSX ID",  tooltip="openMSX Machine ID"),
    Column(id=29, key="fpga_support",     label="FPGA/MiSTer Support",  group="emulation", type="string", short_label="FPGA/ MiSTer", tooltip="FPGA/MiSTer Support"),
]


# ---------------------------------------------------------------------------
# Import-time validation
# ---------------------------------------------------------------------------

validate_config(GROUPS, COLUMNS)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_GROUP_BY_KEY: dict[str, Group] = {g.key: g for g in GROUPS}


def active_columns() -> list[Column]:
    """Return columns that are neither hidden nor retired."""
    return [c for c in COLUMNS if not c.hidden and not c.retired]


def derive_columns() -> list[Column]:
    """Return columns that have a derive callable."""
    return [c for c in COLUMNS if c.derive is not None]


def group_by_key(key: str) -> Group:
    """Look up a group by its key. Raises ``KeyError`` if not found."""
    return _GROUP_BY_KEY[key]

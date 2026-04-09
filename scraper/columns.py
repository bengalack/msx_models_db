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
    truncate_limit: int = 0               # 0 = no truncation; positive = clip to (limit-1) chars + ellipsis
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
    Group(id=0,  key="identity",   label="Identity",        order=0),
    Group(id=12, key="release",    label="Release",         order=1),
    Group(id=1,  key="memory",     label="Memory",           order=2),
    Group(id=2,  key="video",      label="Video",            order=3),
    Group(id=3,  key="audio",      label="Audio",            order=4),
    Group(id=4,  key="media",      label="Media",            order=5),
    Group(id=5,  key="cpu",        label="CPU/Chipsets",     order=6),
    Group(id=6,  key="other",      label="Other",            order=7),
    Group(id=7,  key="emulation",  label="Emulation",        order=8),
    Group(id=8,  key="slotmap_0",  label="Slotmap, slot 0",  order=9),
    Group(id=9,  key="slotmap_1",  label="Slotmap, slot 1",  order=10),
    Group(id=10, key="slotmap_2", label="Slotmap, slot 2",  order=11),
    Group(id=11, key="slotmap_3", label="Slotmap, slot 3",  order=12),
]


# ---------------------------------------------------------------------------
# COLUMNS  (migrated from src/columns.ts — 29 columns, IDs 1-29)
# ---------------------------------------------------------------------------

COLUMNS: list[Column] = [
    # Identity
    Column(id=1,  key="manufacturer",      label="Manufacturer",        group="identity", type="string", truncate_limit=12),
    Column(id=2,  key="model",             label="Model",               group="identity", type="string", linkable=True, truncate_limit=16),
    # Release
    Column(id=3,  key="year",              label="Year",                group="release",  type="number"),
    Column(id=4,  key="region",            label="Region",              group="release",  type="string"),
    Column(id=5,  key="generation",        label="Generation",          group="release",  type="string", short_label="Gen"),
    # Memory
    Column(id=7,  key="main_ram_kb",       label="Main RAM (KB)",       group="memory",   type="number", short_label="Main RAM",    tooltip="Main RAM (KB)"),
    Column(id=10, key="mapper",            label="Memory Mapper",       group="memory",   type="string"),
    Column(id=94, key="sram_kb",           label="SRAM",                group="memory",   type="string"),
    Column(id=95, key="himem_addr",        label="HIMEM Addr",          group="memory",   type="string"),
    # Video
    Column(id=11, key="vdp",              label="VDP",                  group="video",    type="string"),
    Column(id=8,  key="vram_kb",           label="VRAM (KB)",           group="video",    type="number", short_label="VRAM",         tooltip="VRAM (KB)"),
    Column(id=96, key="wait_cycles",       label="Wait Cycles",         group="video",    type="string"),
    # Audio
    Column(id=15, key="psg",              label="PSG",                  group="audio",    type="string"),
    Column(id=16, key="fm_chip",          label="MSX-MUSIC",            group="audio",    type="string"),
    # Media
    Column(id=18, key="floppy_drives",    label="Floppy Drive(s)",      group="media",    type="string", short_label="Floppy Drv",   tooltip="Floppy Drive(s)"),
    Column(id=19, key="cartridge_slots",  label="Cartridge Slots",      group="media",    type="number", short_label="Cart Slots",   tooltip="Cartridge Slots"),
    Column(id=20, key="tape_interface",   label="Tape Interface",       group="media",    type="string", short_label="Tape I/F",     tooltip="Tape Interface"),
    # CPU/Chipsets
    Column(id=22, key="cpu",              label="CPU",                  group="cpu",      type="string"),
    Column(id=23, key="cpu_speed_mhz",    label="CPU Speed (MHz)",      group="cpu",      type="number", short_label="CPU MHz",      tooltip="CPU Speed (MHz)"),
    Column(id=24, key="sub_cpu",          label="Sub-CPU",              group="cpu",      type="string"),
    Column(id=97, key="nmos_cmos",        label="NMOS/CMOS",            group="cpu",      type="string", short_label="NMOS/\u200bCMOS"),
    Column(id=98, key="rtc",              label="RTC",                  group="cpu",      type="string"),
    Column(id=99, key="engine",           label="Engine",               group="cpu",      type="string"),
    # Other
    Column(id=25, key="keyboard_layout",  label="Keyboard Layout",      group="other",    type="string", short_label="KB Layout",    tooltip="Keyboard Layout"),
    Column(id=27, key="connectivity",     label="Connectivity/Ports",   group="other",    type="string", short_label="Conn/ Ports",  tooltip="Connectivity/Ports"),
    # Emulation
    Column(id=28, key="openmsx_id",       label="openMSX Machine ID",   group="emulation", type="string", short_label="openMSX ID",  tooltip="openMSX Machine ID"),
    Column(id=29, key="fpga_support",     label="FPGA/MiSTer Support",  group="emulation", type="string", short_label="FPGA/ MiSTer", tooltip="FPGA/MiSTer Support"),

    # Slotmap, slot 0  (IDs 30–45)  — ms=0, ss=0..3, p=0..3
    Column(id=30, key="slotmap_0_0_0", label="0 / P0", group="slotmap_0", type="string"),
    Column(id=31, key="slotmap_0_0_1", label="0 / P1", group="slotmap_0", type="string"),
    Column(id=32, key="slotmap_0_0_2", label="0 / P2", group="slotmap_0", type="string"),
    Column(id=33, key="slotmap_0_0_3", label="0 / P3", group="slotmap_0", type="string"),
    Column(id=34, key="slotmap_0_1_0", label="1 / P0", group="slotmap_0", type="string"),
    Column(id=35, key="slotmap_0_1_1", label="1 / P1", group="slotmap_0", type="string"),
    Column(id=36, key="slotmap_0_1_2", label="1 / P2", group="slotmap_0", type="string"),
    Column(id=37, key="slotmap_0_1_3", label="1 / P3", group="slotmap_0", type="string"),
    Column(id=38, key="slotmap_0_2_0", label="2 / P0", group="slotmap_0", type="string"),
    Column(id=39, key="slotmap_0_2_1", label="2 / P1", group="slotmap_0", type="string"),
    Column(id=40, key="slotmap_0_2_2", label="2 / P2", group="slotmap_0", type="string"),
    Column(id=41, key="slotmap_0_2_3", label="2 / P3", group="slotmap_0", type="string"),
    Column(id=42, key="slotmap_0_3_0", label="3 / P0", group="slotmap_0", type="string"),
    Column(id=43, key="slotmap_0_3_1", label="3 / P1", group="slotmap_0", type="string"),
    Column(id=44, key="slotmap_0_3_2", label="3 / P2", group="slotmap_0", type="string"),
    Column(id=45, key="slotmap_0_3_3", label="3 / P3", group="slotmap_0", type="string"),

    # Slotmap, slot 1  (IDs 46–61)  — ms=1, ss=0..3, p=0..3
    Column(id=46, key="slotmap_1_0_0", label="0 / P0", group="slotmap_1", type="string"),
    Column(id=47, key="slotmap_1_0_1", label="0 / P1", group="slotmap_1", type="string"),
    Column(id=48, key="slotmap_1_0_2", label="0 / P2", group="slotmap_1", type="string"),
    Column(id=49, key="slotmap_1_0_3", label="0 / P3", group="slotmap_1", type="string"),
    Column(id=50, key="slotmap_1_1_0", label="1 / P0", group="slotmap_1", type="string"),
    Column(id=51, key="slotmap_1_1_1", label="1 / P1", group="slotmap_1", type="string"),
    Column(id=52, key="slotmap_1_1_2", label="1 / P2", group="slotmap_1", type="string"),
    Column(id=53, key="slotmap_1_1_3", label="1 / P3", group="slotmap_1", type="string"),
    Column(id=54, key="slotmap_1_2_0", label="2 / P0", group="slotmap_1", type="string"),
    Column(id=55, key="slotmap_1_2_1", label="2 / P1", group="slotmap_1", type="string"),
    Column(id=56, key="slotmap_1_2_2", label="2 / P2", group="slotmap_1", type="string"),
    Column(id=57, key="slotmap_1_2_3", label="2 / P3", group="slotmap_1", type="string"),
    Column(id=58, key="slotmap_1_3_0", label="3 / P0", group="slotmap_1", type="string"),
    Column(id=59, key="slotmap_1_3_1", label="3 / P1", group="slotmap_1", type="string"),
    Column(id=60, key="slotmap_1_3_2", label="3 / P2", group="slotmap_1", type="string"),
    Column(id=61, key="slotmap_1_3_3", label="3 / P3", group="slotmap_1", type="string"),

    # Slotmap, slot 2  (IDs 62–77)  — ms=2, ss=0..3, p=0..3
    Column(id=62, key="slotmap_2_0_0", label="0 / P0", group="slotmap_2", type="string"),
    Column(id=63, key="slotmap_2_0_1", label="0 / P1", group="slotmap_2", type="string"),
    Column(id=64, key="slotmap_2_0_2", label="0 / P2", group="slotmap_2", type="string"),
    Column(id=65, key="slotmap_2_0_3", label="0 / P3", group="slotmap_2", type="string"),
    Column(id=66, key="slotmap_2_1_0", label="1 / P0", group="slotmap_2", type="string"),
    Column(id=67, key="slotmap_2_1_1", label="1 / P1", group="slotmap_2", type="string"),
    Column(id=68, key="slotmap_2_1_2", label="1 / P2", group="slotmap_2", type="string"),
    Column(id=69, key="slotmap_2_1_3", label="1 / P3", group="slotmap_2", type="string"),
    Column(id=70, key="slotmap_2_2_0", label="2 / P0", group="slotmap_2", type="string"),
    Column(id=71, key="slotmap_2_2_1", label="2 / P1", group="slotmap_2", type="string"),
    Column(id=72, key="slotmap_2_2_2", label="2 / P2", group="slotmap_2", type="string"),
    Column(id=73, key="slotmap_2_2_3", label="2 / P3", group="slotmap_2", type="string"),
    Column(id=74, key="slotmap_2_3_0", label="3 / P0", group="slotmap_2", type="string"),
    Column(id=75, key="slotmap_2_3_1", label="3 / P1", group="slotmap_2", type="string"),
    Column(id=76, key="slotmap_2_3_2", label="3 / P2", group="slotmap_2", type="string"),
    Column(id=77, key="slotmap_2_3_3", label="3 / P3", group="slotmap_2", type="string"),

    # Slotmap, slot 3  (IDs 78–93)  — ms=3, ss=0..3, p=0..3
    Column(id=78, key="slotmap_3_0_0", label="0 / P0", group="slotmap_3", type="string"),
    Column(id=79, key="slotmap_3_0_1", label="0 / P1", group="slotmap_3", type="string"),
    Column(id=80, key="slotmap_3_0_2", label="0 / P2", group="slotmap_3", type="string"),
    Column(id=81, key="slotmap_3_0_3", label="0 / P3", group="slotmap_3", type="string"),
    Column(id=82, key="slotmap_3_1_0", label="1 / P0", group="slotmap_3", type="string"),
    Column(id=83, key="slotmap_3_1_1", label="1 / P1", group="slotmap_3", type="string"),
    Column(id=84, key="slotmap_3_1_2", label="1 / P2", group="slotmap_3", type="string"),
    Column(id=85, key="slotmap_3_1_3", label="1 / P3", group="slotmap_3", type="string"),
    Column(id=86, key="slotmap_3_2_0", label="2 / P0", group="slotmap_3", type="string"),
    Column(id=87, key="slotmap_3_2_1", label="2 / P1", group="slotmap_3", type="string"),
    Column(id=88, key="slotmap_3_2_2", label="2 / P2", group="slotmap_3", type="string"),
    Column(id=89, key="slotmap_3_2_3", label="2 / P3", group="slotmap_3", type="string"),
    Column(id=90, key="slotmap_3_3_0", label="3 / P0", group="slotmap_3", type="string"),
    Column(id=91, key="slotmap_3_3_1", label="3 / P1", group="slotmap_3", type="string"),
    Column(id=92, key="slotmap_3_3_2", label="3 / P2", group="slotmap_3", type="string"),
    Column(id=93, key="slotmap_3_3_3", label="3 / P3", group="slotmap_3", type="string"),
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

"""Fold a HIMEM dump into ``data/local-raw.json``.

``helpers/dump_himem.tcl`` runs inside openMSX, boots every known machine and
prints one line per machine::

    Sony HB-75P - 0xF380

This module folds those readings into the maintainer-curated
``data/local-raw.json``: existing entries get their ``himem_addr`` refreshed
(every other field is left untouched), and machines that are in the database
but not yet in the file are appended.

Machines the dump names but the database does not have — openMSX test
configurations, C-BIOS, ColecoVision and everything else filtered by
``data/exclude.json`` — are reported and skipped, never added, because a
local-only entry would create a new row in the grid.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import local_source
from .aliases import AliasLUT, apply_aliases, load_aliases

ModelKey = tuple[str, str]
"""Canonical, case-folded ``(manufacturer, model)`` identity of a model."""

# "<display name> - 0xF380". openMSX pads with a single " - ".
_LINE_RE = re.compile(r"^(?P<name>.*?)\s+-\s+(?P<value>0[xX][0-9A-Fa-f]+)$")


@dataclass
class DumpParseResult:
    """Outcome of parsing a HIMEM dump file."""

    values: dict[str, str] = field(default_factory=dict)
    """Display name → chosen value (the lowest, when a name repeats)."""
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    """Display name → every distinct value seen, for names read more than once."""
    no_reading: list[str] = field(default_factory=list)
    """Names printed without a value (machine failed to boot, e.g. missing ROMs)."""
    malformed: list[str] = field(default_factory=list)
    """Lines that look like a reading but whose value could not be parsed."""


def parse_dump(text: str) -> DumpParseResult:
    """Parse the text of a ``dump_himem.tcl`` run.

    A name read several times with different values keeps the numerically
    lowest one; every value seen is recorded in ``conflicts``.  A name printed
    without a value means the machine did not boot — it is reported, never
    treated as a reading or as a deletion.
    """
    result = DumpParseResult()
    seen: dict[str, list[str]] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if match:
            seen.setdefault(match["name"].strip(), []).append(match["value"])
        elif " - " in line:
            result.malformed.append(line)
        else:
            result.no_reading.append(line)

    for name, values in seen.items():
        result.values[name] = min(values, key=lambda v: int(v, 16))
        if len(set(values)) > 1:
            result.conflicts[name] = values

    # A name that also produced a reading is not a failed boot.
    result.no_reading = [n for n in result.no_reading if n not in result.values]

    return result


def canonical_key(manufacturer: str | None, model: str | None, lut: AliasLUT) -> ModelKey:
    """Alias-canonicalised, case-folded ``(manufacturer, model)`` lookup key."""
    record = {"manufacturer": manufacturer or "", "model": model or ""}
    apply_aliases(record, lut)
    return (record["manufacturer"].strip().lower(), record["model"].strip().lower())


def load_db_index(path: Path, lut: AliasLUT) -> dict[ModelKey, tuple[str, str]]:
    """Index the models in a ``data.js`` file by canonical key.

    The value is the manufacturer/model spelling as the database has it, which
    is what new ``local-raw.json`` entries are written with.
    """
    text = path.read_text(encoding="utf-8")
    start = text.index("{")
    end = text.rindex("}") + 1
    payload = json.loads(text[start:end])

    keys = [column["key"] for column in payload["columns"]]
    i_manufacturer = keys.index("manufacturer")
    i_model = keys.index("model")

    index: dict[ModelKey, tuple[str, str]] = {}
    for model in payload["models"]:
        values = model["values"]
        manufacturer, name = values[i_manufacturer], values[i_model]
        if not manufacturer or not name:
            continue
        index[canonical_key(manufacturer, name, lut)] = (manufacturer, name)
    return index


def candidate_keys(
    display_name: str, db_index: dict[ModelKey, tuple[str, str]], lut: AliasLUT
) -> list[ModelKey]:
    """Every database key *display_name* could split into.

    openMSX prints one string ("Sony HB-75P"), so the manufacturer/model
    boundary has to be recovered: every space is tried as the split point and
    the resulting pair is canonicalised and looked up.  Callers treat a single
    hit as resolved, none as unknown, and several as ambiguous.
    """
    words = display_name.split(" ")
    hits: list[ModelKey] = []
    for i in range(1, len(words)):
        key = canonical_key(" ".join(words[:i]), " ".join(words[i:]), lut)
        if key in db_index and key not in hits:
            hits.append(key)
    return hits


@dataclass
class UpdatePlan:
    """What folding a dump into ``local-raw.json`` would do."""

    entries: list[dict] = field(default_factory=list)
    """The resulting file content."""
    added: list[tuple[str, str, str]] = field(default_factory=list)
    """``(manufacturer, model, value)`` for entries appended to the file."""
    updated: list[tuple[str, str, str | None, str]] = field(default_factory=list)
    """``(manufacturer, model, old, new)`` for entries whose value moved."""
    unchanged: list[tuple[str, str]] = field(default_factory=list)
    """Entries the dump confirmed without changing."""
    skipped: list[tuple[str, str]] = field(default_factory=list)
    """``(display name, reason)`` for readings that were not applied."""

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated)


def plan_update(
    entries: list[dict],
    dump: DumpParseResult,
    db_index: dict[ModelKey, tuple[str, str]],
    lut: AliasLUT,
) -> UpdatePlan:
    """Fold *dump* into *entries*, without mutating the originals.

    Existing entries keep their position, their key order and every field but
    ``himem_addr``; entries the dump does not mention are copied through
    untouched.  Readings for models the database does not have are skipped, as
    are names that could split into more than one known model.
    """
    plan = UpdatePlan(entries=[dict(entry) for entry in entries])

    by_key: dict[ModelKey, list[int]] = {}
    for i, entry in enumerate(plan.entries):
        key = canonical_key(entry.get("manufacturer"), entry.get("model"), lut)
        by_key.setdefault(key, []).append(i)

    new_entries: list[dict] = []
    for display_name, value in dump.values.items():
        keys = candidate_keys(display_name, db_index, lut)
        if not keys:
            plan.skipped.append((display_name, "no such model in the database"))
            continue
        if len(keys) > 1:
            plan.skipped.append(
                (display_name, f"ambiguous — matches {len(keys)} models in the database")
            )
            continue

        key = keys[0]
        positions = by_key.get(key, [])
        if len(positions) > 1:
            plan.skipped.append(
                (display_name, f"{len(positions)} entries in the file share this model")
            )
            continue

        manufacturer, model = db_index[key]
        if positions:
            entry = plan.entries[positions[0]]
            old = entry.get("himem_addr")
            if old == value:
                plan.unchanged.append((manufacturer, model))
            else:
                entry["himem_addr"] = value
                plan.updated.append((manufacturer, model, old, value))
        else:
            new_entries.append(
                {"manufacturer": manufacturer, "model": model, "himem_addr": value}
            )
            plan.added.append((manufacturer, model, value))

    new_entries.sort(key=lambda e: (e["manufacturer"].lower(), e["model"].lower()))
    plan.added.sort(key=lambda a: (a[0].lower(), a[1].lower()))
    plan.entries.extend(new_entries)
    return plan


def _detect_newline(path: Path) -> str:
    """The newline style *path* already uses, so rewriting it stays a small diff."""
    if not path.exists():
        return "\n"
    return "\r\n" if b"\r\n" in path.read_bytes() else "\n"


def _write_entries(entries: list[dict], path: Path, newline: str) -> None:
    """Write the entry list with an atomic rename, preserving newline style."""
    content = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    if newline != "\n":
        content = content.replace("\n", newline)
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


def run(
    dump_path: Path,
    json_path: Path,
    db_path: Path,
    aliases_path: Path,
    dry_run: bool = False,
) -> UpdatePlan:
    """Fold the HIMEM dump at *dump_path* into the local data at *json_path*.

    Writes only when something actually changed, so a no-op run leaves the
    file byte-identical.  Returns the plan either way.
    """
    lut = load_aliases(aliases_path)
    dump = parse_dump(dump_path.read_text(encoding="utf-8"))
    db_index = load_db_index(db_path, lut)
    entries = local_source.load_local(json_path)

    plan = plan_update(entries, dump, db_index, lut)

    if plan.has_changes and not dry_run:
        _write_entries(plan.entries, json_path, _detect_newline(json_path))

    return plan


def format_report(plan: UpdatePlan, dump: DumpParseResult) -> str:
    """A human-readable summary of *plan*, for the CLI to print."""
    lines: list[str] = []

    if plan.updated:
        lines.append(f"Updated ({len(plan.updated)}):")
        for manufacturer, model, old, new in plan.updated:
            lines.append(f"  {manufacturer} {model}: {old or '(none)'} -> {new}")
    if plan.added:
        lines.append(f"Added ({len(plan.added)}):")
        for manufacturer, model, value in plan.added:
            lines.append(f"  {manufacturer} {model}: {value}")
    if dump.conflicts:
        lines.append(f"Read more than once, kept the lowest ({len(dump.conflicts)}):")
        for name, values in sorted(dump.conflicts.items()):
            lines.append(f"  {name}: {', '.join(values)}")
    if plan.skipped:
        lines.append(f"Skipped ({len(plan.skipped)}):")
        for name, reason in sorted(plan.skipped):
            lines.append(f"  {name}: {reason}")
    if dump.no_reading:
        lines.append(f"No reading — machine did not boot ({len(dump.no_reading)}):")
        for name in sorted(dump.no_reading):
            lines.append(f"  {name}")
    if dump.malformed:
        lines.append(f"Unparsable lines ({len(dump.malformed)}):")
        for line in dump.malformed:
            lines.append(f"  {line}")

    lines.append(
        f"{len(plan.added)} added, {len(plan.updated)} updated, "
        f"{len(plan.unchanged)} unchanged, {len(plan.skipped)} skipped, "
        f"{len(dump.no_reading)} without a reading."
    )
    return "\n".join(lines)

"""PSG Chip column — which PSG (or PSG-compatible engine) a model has.

Every MSX has a PSG, so the column names the chip instead of saying "Yes":

* msx.org's Audio text first, when it says more than "PSG": a plain chip
  ("PSG (AY-3-8910)" → ``AY-3-8910``), a chip in an engine ("YM2149 integrated in
  MSX-Engine S3527" → ``YM2149 in S3527``), alternatives ("AY-3-8910 or T7766A"),
  the versions a page lists ("1st version: OY-2-8910AC, 2nd version: File KC89C72"
  → ``OY-2-8910AC or KC89C72``; "YM2149 in /00 version, … S3527 for /19, /29 …
  versions" → each version row its own part). Uncertainty ("?AY-3-8910",
  "probably …", "MSX-Engine?") puts a "?" after the name in question.
* An engine whose PSG ``data/psg-chips.json`` knows names the chip from its
  msx.org page ("AY-3-8910 in MSX Engine" on the HD62003 → ``AY-3-8910 comp. in
  HD62003``). The engine is the one the text names, else the model's Engine
  column; an engine without a sound chip (T7775) is ignored.
* A page saying there is no PSG ("The sound is not provided by the classical PSG,
  but by an OPN chip."), with an Audio text naming none → ``None``.
* An FPGA machine (Audio "… by FPGA", or Engine FPGA) → ``FPGA``.
* Otherwise openMSX's ``<PSG><type>`` (YM2149, else AY8910 — openMSX's default),
  with the model's engine as above. Nothing from either source → blank.

Design: .claude/artifacts/planning/technical-design.md, *Feature Design: PSG Chip*.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PSG_CHIPS_PATH = Path("data/psg-chips.json")

_ENGINE_WORD = r"MSX[- ]?(?:Engine|SYSTEM(?:II)?)"
_ENGINE_ID = r"[A-Z]{1,2}\d{3,5}[A-Za-z]?"
_PSG_WORDS = re.compile(r"\bPSG\b|\bSSG\b|integrated|compatible|" + _ENGINE_WORD, re.I)

_table: dict[str, Any] | None = None


def load_psg_chips(path: Path = PSG_CHIPS_PATH) -> dict[str, Any]:
    """``{"engines": {id: {"psg", "note"}}, "chips": {regex: name}}`` from *path* (cached for the default path)."""
    global _table
    if path == PSG_CHIPS_PATH and _table is not None:
        return _table
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    table = {"engines": raw.get("engines", {}), "chips": raw.get("chips", {})}
    for engine, entry in table["engines"].items():
        if not isinstance(entry, dict) or "psg" not in entry:
            raise ValueError(f"{path}: engine {engine!r} needs a 'psg' (name or null)")
    if path == PSG_CHIPS_PATH:
        _table = table
    return table


@dataclass
class _Chip:
    name: str
    uncertain: bool
    compatible: bool

    def text(self) -> str:
        return self.name + ("?" if self.uncertain else "") + (" comp." if self.compatible else "")


def _top_level_items(text: str) -> list[str]:
    """Split at commas outside parentheses."""
    items, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
    items.append(text[start:].strip())
    return [item for item in items if item]


def psg_segment(audio: str, chips: dict[str, str]) -> str | None:
    """The part of an Audio text about the PSG: its top-level items naming a PSG, a chip or an engine."""
    chip_re = re.compile("|".join(chips), re.I) if chips else None
    items = [item for item in _top_level_items(audio)
             if _PSG_WORDS.search(item) or (chip_re and chip_re.search(item))]
    return ", ".join(items) if items else None


def _version_part(segment: str, model: str) -> tuple[str, bool]:
    """(the text that applies to *model*, whether the parts are alternatives).

    "A in /00 version, B for /19, /29 versions": the part naming the model's suffix
    (else "/00"). "1st version: A, 2nd version: B": all of it, as alternatives."""
    if not re.search(r"\bversions?\b", segment, re.I):
        return segment, False
    parts = [p for p in re.split(r",(?!\s*[/\d])\s*", segment) if re.search(r"\bversions?\b", p, re.I)]
    if len(parts) < 2:
        return segment, False
    if not any(re.search(r"/\d", p) for p in parts):
        return segment, True
    suffix = re.search(r"(/\d+[A-Z]?)\s*$", model)
    for wanted in ([suffix.group(1)] if suffix else []) + ["/00"]:
        for part in parts:
            if re.search(re.escape(wanted) + r"(?![\w])", part):
                return part, False
    return segment, False


def _chips_in(text: str, chips: dict[str, str]) -> list[_Chip]:
    found: list[_Chip] = []
    probably = "probably" in text.lower()
    pattern = re.compile("|".join(f"(?<![\\w-])({rx})(?![\\w-])" for rx in chips), re.I)
    for m in pattern.finditer(text):
        name = next(chips[rx] for rx, group in zip(chips, m.groups()) if group is not None)
        if any(c.name == name for c in found):
            continue
        before, after = text[:m.start()].rstrip(), text[m.end():]
        uncertain = probably or before.endswith("?") or after.startswith("?")
        compatible = bool(re.match(r"\??\s+compatible", after, re.I))
        found.append(_Chip(name, uncertain, compatible))
    return found


def _engine_key(engine_id: str, engines: dict[str, Any]) -> str:
    """T9769x / T9769B → T9769 when only the base is known; T7937A stays."""
    if engine_id in engines:
        return engine_id
    return engine_id[:-1] if engine_id[:-1] in engines else engine_id


def _engine_from_column(model: dict[str, Any], engines: dict[str, Any]) -> tuple[list[str], bool]:
    """(engine ids with a known PSG entry, uncertain) from the model's Engine columns."""
    from .columns import _parse_engine_field
    for index in (1, 0):   # full-custom, then semi-custom (HD62003)
        value = _parse_engine_field(model, index) or ""
        if not value or "None" in value:   # "None or S3527": no engine in some versions
            continue
        ids = [_engine_key(i, engines) for i in re.findall(_ENGINE_ID, value)]
        ids = [i for i in ids if i in engines]
        if ids:
            return list(dict.fromkeys(ids)), "?" in value
    return [], False


def _base(name: str) -> str:
    """A chip name without "comp." and package letters: YM2149F → YM2149, AY-3-8910 comp. → AY-3-8910."""
    return re.sub(r"(?<=YM2149)F$", "", name.replace(" comp.", "").rstrip("?"))


def _agrees(chips: list[_Chip], engine_ids: list[str], engines: dict[str, Any]) -> bool:
    """Whether every named chip is the PSG the engine integrates (no engine: nothing to contradict)."""
    entry = engines.get(engine_ids[0]) if engine_ids else None
    if entry is None or entry.get("psg") is None:
        return True
    return all(_base(c.name) == _base(entry["psg"]) for c in chips)


def _compose(chips: list[_Chip], alternatives: bool, engine_ids: list[str], engine_uncertain: bool,
             engines: dict[str, Any]) -> tuple[str | None, str | None]:
    """(cell value, engine note)."""
    entry = engines.get(engine_ids[0]) if engine_ids else None
    if entry is not None and entry.get("psg") is None:
        engine_ids, entry = [], None            # an engine without a sound chip (T7775)
    where = " or ".join(engine_ids) + ("?" if engine_uncertain else "")
    if entry is not None:
        name = entry["psg"] + ("?" if any(c.uncertain for c in chips) else "")
        return f"{name} in {where}", entry.get("note")
    if not chips:
        return None, None
    names = " or ".join(c.text() for c in chips)
    return (f"{names} in {where}" if engine_ids else names), None


def psg_chip(model: dict[str, Any], table: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    """(cell value, tooltip) for *model*'s PSG Chip cell; (None, None) when no source says.

    Reads ``audio_raw`` (msx.org Audio text), ``psg_type`` (openMSX) and the
    Engine columns' source (``engine_raw``)."""
    table = table or load_psg_chips()
    engines, chips = table["engines"], table["chips"]
    audio = model.get("audio_raw") or ""
    segment = psg_segment(audio, chips) if audio else None
    column_ids, column_uncertain = _engine_from_column(model, engines)

    # The page says there is no PSG and its Audio text names none (Haesung Super Free Kick:
    # "Yamaha YM2203C a.k.a. OPN"): "None", with the page's sentence as tooltip.
    if not segment and model.get("psg_absent"):
        return "None", "msx.org: " + model["psg_absent"]

    if segment:
        text, alternatives = _version_part(segment, model.get("model") or "")
        found = _chips_in(text, chips)
        engine = re.search(_ENGINE_WORD + r"(\?)?((?:\s+(?:or\s+)?" + _ENGINE_ID + r"\b)*)", text, re.I)
        engine_ids, engine_uncertain = column_ids, column_uncertain
        if engine:
            named = [_engine_key(i, engines) for i in re.findall(_ENGINE_ID, engine.group(2))]
            if named:
                engine_ids, engine_uncertain = list(dict.fromkeys(named)), False
            elif engine.group(1):               # "MSX-Engine?": which engine, if any, is unknown
                engine_ids, engine_uncertain = [], False
                for chip in found:
                    chip.uncertain = True
        elif found and not _agrees(found, engine_ids, engines):
            # The page names a chip but no engine, and the Engine column's engine has another
            # PSG (Sanyo PHC-33: "PSG (AY-3-8910)", Engine S3527): the named chip wins.
            engine_ids, engine_uncertain = [], False
        value, note = _compose(found, alternatives, engine_ids, engine_uncertain, engines)
        if value:
            return value, "msx.org: " + segment + (f". {note}" if note else "")

    # An FPGA machine emulates the PSG: "Emulated PSG , MSX-MUSIC and SCC by FPGA", or Engine FPGA
    # (the 1chipMSX, no Audio text). The cell says so, without a chip link.
    if re.search(r"\bFPGA\b", audio):
        return "FPGA", "msx.org: " + audio
    from .columns import _parse_engine_field
    if (_parse_engine_field(model, 1) or "").strip() == "FPGA":
        return "FPGA", "msx.org Engine: " + (model.get("engine_raw") or "FPGA")

    psg_type = model.get("psg_type")
    if psg_type:
        name = "YM2149" if psg_type.upper() == "YM2149" else "AY-3-8910"
        value, note = _compose([_Chip(name, False, False)], False, column_ids, column_uncertain, engines)
        source = "openMSX: " + (psg_type if psg_type != "default" else "AY8910 (no type given: openMSX's default)")
        return value, source + (f". {note}" if note else "")
    return None, None

"""Region column: region names and flags (data/regions.json).

A Region value names one or more regions in free text ("Belgium, France, the
Netherlands and Spain", "se/fi", "Probably Japan"). ``parse_region`` splits it
into regions and matches each part against data/regions.json — a region's name,
its aliases, or (single-flag regions) its ISO code, case-insensitively and
ignoring a leading "the". The build then

- replaces the value with the region names ("Belgium, France, Netherlands,
  Spain"), which the page sorts, filters and shows as the cell tooltip, and
- ships ``ColumnDef.displayValues`` {value: flags}, which the page shows in the
  cell ("🇧🇪🇫🇷🇳🇱🇪🇸").

A part that matches no region is kept as text, both in the value and in the
cell, and reported.

Language columns (Character Set, Keyboard Type) keep their value ("French
(AZERTY)") and only get the flags of its language (``languages`` in
data/regions.json, ``RegionTable.language_display``). Design:
technical-design.md, *Feature Design: Region Flags*.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REGIONS_PATH = Path("data/regions.json")

_SPLIT_RE = re.compile(r"\s*(?:,|/|;|\band\b)\s*", re.IGNORECASE)
_THE_RE = re.compile(r"^the\s+", re.IGNORECASE)
_CODE_RE = re.compile(r"^[A-Z]{2}$")
_NOTE_RE = re.compile(r"\s*\([^)]*\)\s*$")     # a closing "(AZERTY)" / "(JIS)" note


def flag_emoji(code: str) -> str:
    """ISO 3166 alpha-2 code (or EU / UN) → flag emoji: two regional indicator symbols."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


@dataclass
class Region:
    name: str
    flags: list[str]
    aliases: list[str] = field(default_factory=list)


@dataclass
class RegionParse:
    names: list[str]          # region names (unmatched parts as written)
    display: str              # flags, unmatched parts as text
    unknown: list[str]        # parts that matched no region


def _key(text: str) -> str:
    return _THE_RE.sub("", text.strip()).lower()


class RegionTable:
    def __init__(self, regions: list[Region], languages: dict[str, str] | None = None) -> None:
        self.regions = regions
        self._by_key: dict[str, Region] = {}
        by_name = {r.name: r for r in regions}
        self._languages: dict[str, Region] = {}
        for language, name in (languages or {}).items():
            if name not in by_name:
                raise ValueError(f"regions.json: language {language!r} names unknown region {name!r}")
            self._languages[language.lower()] = by_name[name]
        for r in regions:
            for k in [r.name, *r.aliases]:
                existing = self._by_key.get(_key(k))
                if existing is not None and existing is not r:
                    raise ValueError(f"regions.json: {k!r} names both {existing.name!r} and {r.name!r}")
                self._by_key[_key(k)] = r
        # An ISO code ("pl", "se/fi") names the first single-flag region with that flag,
        # unless a name or alias already means something else.
        for r in regions:
            if len(r.flags) == 1:
                self._by_key.setdefault(_key(r.flags[0]), r)

    def lookup(self, text: str) -> Region | None:
        return self._by_key.get(_key(text))

    def language_region(self, language: str) -> Region | None:
        """The region of a language ("German" → Germany), or a region named directly ("UK"); None if neither."""
        base = _NOTE_RE.sub("", language).strip()
        return self._languages.get(base.lower()) or self.lookup(base)

    def language_tag(self, languages: str) -> str | None:
        """Country tag of a version named by language(s): "German" → "DE", "Danish/Norwegian" → "DK/NO".

        None when a part has no single-country region ("Arabic" → Middle East).
        """
        codes = []
        for part in languages.split("/"):
            region = self.language_region(part)
            if region is None or len(region.flags) != 1:
                return None
            codes.append(region.flags[0])
        return "/".join(codes)

    def language_display(self, value: str) -> str | None:
        """Flags of a language value ("French (AZERTY)" → 🇫🇷, "UK" → 🇬🇧), or None.

        The value's language, without a closing "(...)" note, is looked up in
        ``languages``, then as a region name or alias.
        """
        base = _NOTE_RE.sub("", value).strip()
        region = self._languages.get(base.lower()) or self.lookup(base)
        return "".join(flag_emoji(c) for c in region.flags) if region else None

    def parse(self, value: str) -> RegionParse:
        """Regions named by *value*: the whole value first ("South Korea (original version)"), else its parts."""
        whole = self.lookup(value)
        parts = [value.strip()] if whole else [p for p in _SPLIT_RE.split(value) if p.strip()]
        names: list[str] = []
        display: list[str] = []
        unknown: list[str] = []
        flags_seen: set[str] = set()
        for part in parts:
            region = self.lookup(part)
            name = region.name if region else part.strip()
            if name in names:
                continue
            names.append(name)
            if region is None:
                unknown.append(name)
                display.append(f" {name} ")
                continue
            for code in region.flags:
                if code not in flags_seen:
                    flags_seen.add(code)
                    display.append(flag_emoji(code))
        return RegionParse(names=names, display=re.sub(r"\s+", " ", "".join(display)).strip(), unknown=unknown)


def load_regions(path: Path = REGIONS_PATH) -> RegionTable:
    """Load and validate data/regions.json."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    regions = []
    for i, entry in enumerate(raw.get("regions", [])):
        name, flags = entry.get("name"), entry.get("flags")
        if not name or not flags or not all(isinstance(c, str) and _CODE_RE.match(c) for c in flags):
            raise ValueError(f"regions.json entry {i}: needs a name and flags of two capital letters, got {entry!r}")
        regions.append(Region(name=name, flags=list(flags), aliases=list(entry.get("aliases", []))))
    languages = {k: v for k, v in (raw.get("languages") or {}).items() if not k.startswith("_")}
    return RegionTable(regions, languages)

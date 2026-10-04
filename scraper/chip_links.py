"""Chip links — the page each chip id (or MSX generation) in a cell links to.

One table for every column flagged ``chip_links`` in scraper/columns.py (the
Generation, CPU, Sub-CPU, Engine, VDP and PSG Chip columns): the web page turns each whole chip id it finds in such
a cell into a link. Every spelling that occurs in the data is listed on its own
("TMS9918A" and "TMS9918" both point at the TMS9918 page), so nothing is
guessed from suffixes.

Design: .claude/artifacts/planning/technical-design.md, *Feature Design: Chip Links*.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

CHIP_LINKS_PATH = Path("data/chip-links.json")


def load_chip_links(path: Path = CHIP_LINKS_PATH) -> dict[str, str]:
    """``{chip id: URL}`` from *path*; ``{}`` when the file is absent.

    Raises ``ValueError`` on malformed input: not a JSON object, a ``links``
    that is not an object, an empty chip id, or a URL that is not https.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("links", {}), dict):
        raise ValueError(f"{path}: expected an object with a 'links' object")
    links = raw.get("links", {})
    for chip, url in links.items():
        if not chip.strip() or not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"{path}: chip {chip!r} must map to an https URL, got {url!r}")
    log.debug("Loaded %d chip links from %s", len(links), path)
    return dict(links)

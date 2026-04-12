"""Local supplemental data source.

Loads maintainer-curated model data from ``data/local-raw.json``.
A missing file is not an error — returns an empty list.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def load_local(path: Path) -> list[dict[str, Any]]:
    """Load local supplemental model data from *path*.

    Returns an empty list if the file does not exist.
    Raises ``ValueError`` on malformed JSON or if the top-level value
    is not a list.
    """
    if not path.exists():
        log.debug("Local data file not found (skipping): %s", path)
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array at top level")
    log.info("Loaded %d local model entries from %s", len(data), path)
    return data

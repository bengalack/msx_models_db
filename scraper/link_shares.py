"""Link-shares LUT — allow models to inherit links from a donor model.

When a model has no ``links`` entry in the output (because it has no msx.org
page of its own), a link-shares entry can specify another model whose links
it should adopt.  Keys and values are natural keys in the form
``"manufacturer|model"`` (lowercase, trimmed) — the same format used by
:func:`scraper.merge.natural_key`.

The donor model must itself have a links entry; if neither the donor nor the
recipient has links, the entry is silently skipped.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_link_shares(path: str | Path) -> dict[str, str]:
    """Load and validate a link-shares JSON file.

    Returns a mapping of ``{recipient_model_name: donor_model_name}``.
    Raises ``FileNotFoundError`` if the file is absent.
    Raises ``ValueError`` on malformed JSON or wrong structure.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Link-shares LUT not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object at top level")

    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(
                f"{path}: all keys and values must be strings; "
                f"got key={key!r}, value={value!r}"
            )
        if key == value:
            raise ValueError(
                f"{path}: model '{key}' cannot share links with itself"
            )

    log.debug("Loaded link-shares LUT: %d entry/entries from %s", len(raw), path)
    return dict(raw)


def apply_link_shares(
    records: list[dict],
    natural_keys: list[str],
    shares: dict[str, str],
) -> None:
    """Back-fill missing ``links`` on records by copying from a donor model.

    Parameters
    ----------
    records:
        The list of JS model record dicts (each may have a ``"links"`` key).
    natural_keys:
        The natural key (``"manufacturer|model"``, lowercase) corresponding to
        each record (parallel list).
    shares:
        Mapping from recipient natural key → donor natural key, as returned by
        :func:`load_link_shares`.

    The function modifies *records* in-place.  A recipient is skipped when:
    - it already has a ``links`` entry, or
    - the donor model is not found in the dataset, or
    - the donor model itself has no ``links`` entry.
    """
    # Build natural_key → links index from the current records
    nk_to_links: dict[str, dict | None] = {
        nk: rec.get("links") for nk, rec in zip(natural_keys, records)
    }

    for i, nk in enumerate(natural_keys):
        if records[i].get("links", {}).get("model"):
            continue  # already has a model link — nothing to do
        donor_nk = shares.get(nk)
        if donor_nk is None:
            continue  # not in the shares LUT
        donor_links = nk_to_links.get(donor_nk)
        if not donor_links or not donor_links.get("model"):
            log.warning(
                "link-shares: donor '%s' for '%s' has no model link — skipping",
                donor_nk, nk,
            )
            continue
        records[i].setdefault("links", {})["model"] = donor_links["model"]
        log.debug("link-shares: '%s' inherited model link from '%s'", nk, donor_nk)

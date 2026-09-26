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
from typing import Any, Callable

from .inherit import fill_blanks

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


def fill_from_link_shares(
    models: list[dict[str, Any]],
    shares: dict[str, str],
    key: Callable[[dict[str, Any]], str],
) -> int:
    """Fill each recipient's missing fields from its donor's row (in place).

    A link-share says the recipient is described by the donor's msx.org page, so
    the donor's data applies too — with the same rules as adaptations
    (scraper/inherit.py): only missing fields, never identity, the openMSX
    machine or BIOS-derived fields; the slot map only when the recipient has
    none. Chains (A <- B <- C) resolve regardless of order.
    Returns the number of recipients that gained data.
    """
    by_key = {key(m): m for m in models}
    done: set[str] = set()
    filled = 0

    def fill(recipient_key: str, active: frozenset[str]) -> None:
        nonlocal filled
        if recipient_key in done:
            return
        done.add(recipient_key)
        donor_key = shares.get(recipient_key)
        recipient, donor = by_key.get(recipient_key), by_key.get(donor_key) if donor_key else None
        if recipient is None or donor is None:
            return
        if donor_key in shares and donor_key not in active:
            fill(donor_key, active | {recipient_key})
        if fill_blanks(recipient, donor):
            filled += 1
            log.info("[link-shares] %s filled from %s", recipient_key, donor_key)

    for recipient_key in shares:
        fill(recipient_key, frozenset())
    return filled


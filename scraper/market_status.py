"""Market status values and the openMSX description rule.

The Market status column says whether a model was never released
("Unreleased") or is known to be rare ("Rare"). msx.org pages are read by
``market_status`` in scraper/msxorg.py; openMSX machine XMLs by
``status_from_description`` here, from ``<info><description>``, whose subject
is always the machine itself ("Rare MSX that was never mass produced …",
"An extremely rare Russian version of the F9P.", "Prototype MSX?").

Design: technical-design.md, *Feature Design: Market Status*.
"""
from __future__ import annotations

import re

MARKET_UNRELEASED = "Unreleased"
MARKET_RARE = "Rare"

# When openMSX and msx.org give different statuses, the earlier value wins:
# Rare beats Unreleased. A source that says nothing never clears the other's.
# (Within one msx.org page, Unreleased beats Rare — see msxorg.market_status.)
MERGE_PRECEDENCE = (MARKET_RARE, MARKET_UNRELEASED)

_DESCRIPTION_UNRELEASED_RE = re.compile(
    r"^\s*(?:an?\s+)?(?:\w+\s+)?prototype\b|\b(?:unreleased|non-released|never\s+(?:been\s+)?released|not\s+released)\b",
    re.IGNORECASE,
)
_DESCRIPTION_RARE_RE = re.compile(
    r"^\s*(?:an?\s+)?(?:(?:very|extremely)\s+)?rare\b|\b(?:is|was)\s+(?:an?\s+)?(?:(?:very|extremely)\s+)?rare\b"
    r"(?!\s+(?:for|on|nowadays))",
    re.IGNORECASE,
)


def status_from_description(description: str | None) -> str | None:
    """"Unreleased", "Rare" or None from an openMSX machine description."""
    if not description:
        return None
    if _DESCRIPTION_UNRELEASED_RE.search(description):
        return MARKET_UNRELEASED
    if _DESCRIPTION_RARE_RE.search(description):
        return MARKET_RARE
    return None


def merged_status(a: str | None, b: str | None) -> str | None:
    """The status of a model whose sources say *a* and *b* (Rare beats Unreleased)."""
    for status in MERGE_PRECEDENCE:
        if status in (a, b):
            return status
    return a or b

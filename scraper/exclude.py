"""Scraper exclude list — load and match rules from data/exclude.json."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_VALID_MODES = frozenset([
    frozenset(["manufacturer", "model"]),
    frozenset(["filename"]),
])


def _validate_entry(index: int, entry: object) -> None:
    """Raise ValueError if an entry has an invalid shape."""
    if not isinstance(entry, dict):
        raise ValueError(
            f"exclude.json entry {index} must be a JSON object, got {type(entry).__name__!r}"
        )
    keys = frozenset(entry.keys())
    if keys not in _VALID_MODES:
        raise ValueError(
            f"exclude.json entry {index} has unrecognised keys {sorted(entry.keys())}. "
            "Each entry must have exactly {\"manufacturer\", \"model\"} or {\"filename\"}."
        )
    for k, v in entry.items():
        if not isinstance(v, str):
            raise ValueError(
                f"exclude.json entry {index} key {k!r} must be a string, got {type(v).__name__!r}"
            )


def _field_matches(rule_value: str, actual_value: str | None) -> bool:
    """Return True if a single field in a manufacturer+model rule matches."""
    if rule_value == "*":
        return True
    actual = actual_value or ""
    return rule_value == actual


@dataclass
class ExcludeList:
    """Loaded exclude rules with per-rule match tracking."""

    rules: list[dict] = field(default_factory=list)
    _match_counts: list[int] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._match_counts = [0] * len(self.rules)

    def is_excluded(self, manufacturer: str | None, model: str | None) -> bool:
        """Return True if a manufacturer+model pair matches any rule.

        Checks only entries with the {manufacturer, model} mode.
        Updates internal match counters for dead-rule detection.
        """
        for i, rule in enumerate(self.rules):
            if "filename" in rule:
                continue
            if _field_matches(rule["manufacturer"], manufacturer) and \
               _field_matches(rule["model"], model):
                self._match_counts[i] += 1
                return True
        return False

    def is_excluded_by_filename(self, filename: str) -> bool:
        """Return True if a filename matches any filename rule (exact match).

        Checks only entries with the {filename} mode.
        Updates internal match counters for dead-rule detection.
        """
        for i, rule in enumerate(self.rules):
            if "filename" not in rule:
                continue
            if rule["filename"] == filename:
                self._match_counts[i] += 1
                return True
        return False

    def dead_rules(self) -> list[int]:
        """Return indices of rules that matched zero items since this list was created."""
        return [i for i, count in enumerate(self._match_counts) if count == 0]


def load_excludes(path: Path) -> ExcludeList:
    """Load and validate an exclude list from a JSON file.

    Returns an empty ExcludeList if the file does not exist.
    Raises ValueError on malformed JSON or invalid entry shapes.
    """
    if not path.exists():
        log.debug("[exclude:load] File not found, no exclusions | path=%s", path)
        return ExcludeList()

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        log.error("[exclude:load] Invalid JSON | path=%s error=%s", path, e)
        raise ValueError(f"Failed to parse exclude list {path}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(
            f"exclude.json must contain a JSON array, got {type(data).__name__!r}"
        )

    for i, entry in enumerate(data):
        _validate_entry(i, entry)

    # Warn on all-wildcard entries
    for i, entry in enumerate(data):
        if entry.get("manufacturer") == "*" and entry.get("model") == "*":
            log.warning(
                "[exclude:load] All-wildcard rule at index %d will exclude every model "
                "— verify this is intentional", i
            )

    exclude_list = ExcludeList(rules=data)
    log.info(
        "[exclude:load] Loaded | path=%s rule_count=%d", path, len(data)
    )
    return exclude_list

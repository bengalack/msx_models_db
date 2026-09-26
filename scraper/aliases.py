"""Alias LUT — normalize field values to canonical names at merge time."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# A composite rule: ({col: match_value_lower, ...}, {col: canonical_value, ...})
CompositeRule = tuple[dict[str, str], dict[str, str]]

_RESERVED = "composite"
_VARIANT_TAG = "variant_tag"

# A variant tag closing a model name: "CF-2700 (GE)", "PX-7(UK)".
_TAG_RE = re.compile(r"\((?P<tag>[A-Za-z]{2,3})\)$")


@dataclass
class AliasLUT:
    """Loaded alias rules, ready for application."""
    single: dict[str, dict[str, str]] = field(default_factory=dict)
    """Single-column rules: {column: {alias_lower: canonical}}."""
    composite: list[CompositeRule] = field(default_factory=list)
    """Multi-column rules: [(match_lower, canonical), ...]."""
    variant_tag: dict[str, str] = field(default_factory=dict)
    """Country tags closing a model name: {alias_lower: canonical} ("ge" -> "DE")."""


def load_aliases(path: str | Path) -> AliasLUT:
    """Load and validate an alias JSON file.

    Returns an :class:`AliasLUT` with single-column and composite rules.
    Raises FileNotFoundError if the file is absent.
    Raises ValueError on malformed JSON, wrong structure, or conflicting aliases.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Alias LUT not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object at top level")

    lut = AliasLUT()

    for column, value in raw.items():
        if column == _RESERVED:
            lut.composite = _parse_composite(path, value)
            continue
        if column == _VARIANT_TAG:
            lut.variant_tag = _parse_variant_tags(path, value)
            continue

        if not isinstance(value, dict):
            raise ValueError(
                f"{path}: value for column '{column}' must be an object"
            )
        col_lut: dict[str, str] = {}
        for canonical, aliases in value.items():
            if not isinstance(aliases, list):
                raise ValueError(
                    f"{path}: aliases for '{canonical}' in column '{column}' must be a list"
                )
            for alias in aliases:
                key = alias.lower()
                if key in col_lut and col_lut[key] != canonical:
                    raise ValueError(
                        f"{path}: duplicate alias '{alias}' in column '{column}': "
                        f"maps to both '{col_lut[key]}' and '{canonical}'"
                    )
                col_lut[key] = canonical
        lut.single[column] = col_lut

    log.debug(
        "Loaded alias LUT: %d single-column rule(s), %d composite rule(s) from %s",
        sum(len(v) for v in lut.single.values()),
        len(lut.composite),
        path,
    )
    return lut


def _parse_variant_tags(path: Path, raw: object) -> dict[str, str]:
    """Parse the ``"variant_tag"`` section: ``{canonical: [alias, ...]}``."""
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: '{_VARIANT_TAG}' must be an object")
    tags: dict[str, str] = {}
    for canonical, aliases in raw.items():
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise ValueError(f"{path}: '{_VARIANT_TAG}' aliases for '{canonical}' must be a list of strings")
        if not _TAG_RE.fullmatch(f"({canonical})"):
            raise ValueError(f"{path}: '{_VARIANT_TAG}' tag '{canonical}' must be 2-3 letters")
        for alias in aliases:
            key = alias.lower()
            if key in tags and tags[key] != canonical:
                raise ValueError(
                    f"{path}: duplicate variant tag '{alias}': maps to both '{tags[key]}' and '{canonical}'"
                )
            tags[key] = canonical
    return tags


def _parse_composite(path: Path, raw: object) -> list[CompositeRule]:
    """Parse and validate the ``"composite"`` section of an alias file."""
    if not isinstance(raw, list):
        raise ValueError(f"{path}: 'composite' must be a list")

    rules: list[CompositeRule] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "match" not in item or "canonical" not in item:
            raise ValueError(
                f"{path}: composite rule #{i} must be an object with 'match' and 'canonical' keys"
            )
        match_raw = item["match"]
        canonical_raw = item["canonical"]
        if not isinstance(match_raw, dict) or not match_raw:
            raise ValueError(
                f"{path}: composite rule #{i} 'match' must be a non-empty object"
            )
        if not isinstance(canonical_raw, dict) or not canonical_raw:
            raise ValueError(
                f"{path}: composite rule #{i} 'canonical' must be a non-empty object"
            )
        for src_name, src in (("match", match_raw), ("canonical", canonical_raw)):
            for k, v in src.items():
                if not isinstance(v, str):
                    raise ValueError(
                        f"{path}: composite rule #{i}: value for '{k}' in '{src_name}' must be a string"
                    )
        match_lower = {k: v.lower() for k, v in match_raw.items()}
        rules.append((match_lower, dict(canonical_raw)))

    return rules


def apply_aliases(record: dict, lut: AliasLUT) -> None:
    """Replace alias values in *record* with their canonical names (in-place).

    The variant tag closing the model name is canonicalised first
    ("CF-2700 (GE)" -> "CF-2700 (DE)"), then single-column rules, then
    composite rules.  The first matching composite rule wins; subsequent rules
    are skipped.
    """
    # Pass 0 — country tag closing the model name
    model = record.get("model")
    if lut.variant_tag and isinstance(model, str):
        m = _TAG_RE.search(model)
        canonical_tag = lut.variant_tag.get(m.group("tag").lower()) if m else None
        if m and canonical_tag:
            record["model"] = f"{model[:m.start()]}({canonical_tag})"

    # Pass 1 — single-column aliases
    for column, alias_map in lut.single.items():
        value = record.get(column)
        if not isinstance(value, str):
            continue
        canonical = alias_map.get(value.lower())
        if canonical is not None:
            record[column] = canonical

    # Pass 2 — composite (multi-column) aliases
    for match_lower, canonical in lut.composite:
        if all(
            isinstance(record.get(col), str)
            and record[col].lower() == val
            for col, val in match_lower.items()
        ):
            record.update(canonical)
            break  # first match wins


# Internal field on an msx.org record: other names its page says the model is
# "also known as" ("The HX-51 computer, also known as the HX-51I, ...").
# merge_models uses them to join the openMSX machine of that name.
KNOWN_AS_FIELD = "_known_as"

# Internal field on an msx.org record whose model name the parser cleaned (an
# editorial note dropped from the Model field): the name as the page wrote it.
# merge_models treats it as a former name, so the model keeps its registry id.
FORMER_MODEL_FIELD = "_former_model"

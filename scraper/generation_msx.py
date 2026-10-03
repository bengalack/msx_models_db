"""generation-msx.nl links: the map file and the command that (re)creates it.

``data/generation-msx.json`` maps our model ids to the model's page on
generation-msx.nl, which the Identity column "generation-msx" links to. The
two sites name models differently ("MPC-25F (WAVY25)", "SANYO Electric Co.,
Ltd.", "CF-2700(GE)"), so the map is keyed by our permanent model id, not by
name, and each entry records how it was found:

- ``exact``   the model name (after our aliases / country tags) is theirs
- ``variant`` theirs adds a nickname or suffix ("MPC-25F (WAVY25)", "CPC-400 X-II")
- ``family``  no page for the model itself; the page of its family / base model
              ("VG 8235" for "VG 8235/00", "HB-F500" for "HB-F500 (v2)")
- ``manual``  set by hand; kept as is by every rerun (``"url": null`` = never link)

Recreate or refresh it with ``python -m scraper gmsx-links`` (crawls the four
MSX computer listings on generation-msx.nl, matches every model of the built
``docs/data.js``, keeps manual entries). Design: technical-design.md,
*Feature Design: generation-msx Links*.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote

from bs4 import BeautifulSoup

from .aliases import AliasLUT, apply_aliases

log = logging.getLogger(__name__)

GENERATION_MSX_PATH = Path("data/generation-msx.json")
BASE_URL = "https://generation-msx.nl"
PRODUCT_TYPES = ("MSX 1", "MSX 2", "MSX 2+", "MSX turbo R")
MATCH_KINDS = ("exact", "variant", "family", "manual")

_COMMENT = (
    "Our model id -> its page on generation-msx.nl, for the Identity column 'generation-msx'. "
    "match: exact | variant (their name adds a nickname/suffix) | family (page of the family/base model) | "
    "manual (set by hand, kept by reruns; url null = never link). Regenerate with "
    "`python -m scraper gmsx-links` (needs a built docs/data.js); see technical-design.md, "
    "Feature Design: generation-msx Links."
)

_HARDWARE_LINK_RE = re.compile(r"/hardware/[^/]+/[^/]+/\d+$")


@dataclass(frozen=True)
class GmsxEntry:
    """One computer in a generation-msx.nl hardware listing."""
    url: str
    name: str
    brand: str


# ── Map file ──────────────────────────────────────────────────────────────

def load_links(path: Path = GENERATION_MSX_PATH) -> dict[int, dict[str, Any]]:
    """``{model id: {"model", "url", "match"}}``; ``{}`` when the file is absent."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    links = raw.get("links", {}) if isinstance(raw, dict) else {}
    if not isinstance(links, dict):
        raise ValueError(f"{path}: 'links' must be an object keyed by model id")
    out: dict[int, dict[str, Any]] = {}
    for key, entry in links.items():
        if not str(key).isdigit() or not isinstance(entry, dict):
            raise ValueError(f"{path}: entry {key!r} must be keyed by a model id and be an object")
        url = entry.get("url")
        if url is not None and not (isinstance(url, str) and url.startswith("https://")):
            raise ValueError(f"{path}: entry {key}: url must be an https URL or null")
        if entry.get("match") not in MATCH_KINDS:
            raise ValueError(f"{path}: entry {key}: match must be one of {MATCH_KINDS}")
        out[int(key)] = entry
    return out


def write_links(path: Path, links: dict[int, dict[str, Any]]) -> None:
    payload = {"_comment": _COMMENT,
               "links": {str(k): links[k] for k in sorted(links)}}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Listing pages ───────────────────────────────────────────────────────────

def listing_url(product_type: str, page: int) -> str:
    return f"{BASE_URL}/hardware/result?product_type%5B0%5D={quote(product_type)}&page={page}"


def parse_listing(html: str) -> tuple[list[GmsxEntry], int]:
    """Entries of one listing page (table rows: name, brand, type) and its last page number."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[GmsxEntry] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        link = next((a for a in tr.find_all("a", href=True) if _HARDWARE_LINK_RE.search(a["href"])), None)
        if link is None or len(cells) < 2:
            continue
        href = link["href"]
        url = href if href.startswith("http") else BASE_URL + href
        name = re.sub(r"\s+", " ", link.get_text(" ", strip=True))
        if not name:   # the first link of a row may wrap the thumbnail only
            name = next((re.sub(r"\s+", " ", a.get_text(" ", strip=True)) for a in tr.find_all("a", href=href)
                         if a.get_text(strip=True)), "")
        brand = re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True))
        if name:
            entries.append(GmsxEntry(url=url, name=name, brand=brand))
    pages = [int(p) for p in re.findall(r"[?&](?:amp;)?page=(\d+)", html)]
    return entries, max(pages or [1])


def crawl(fetch: Callable[[str], str], delay: float = 1.0) -> list[GmsxEntry]:
    """Every computer in the four MSX listings (one request per page, *delay* seconds apart)."""
    found: dict[str, GmsxEntry] = {}
    for product_type in PRODUCT_TYPES:
        page, last = 1, 1
        while page <= last:
            entries, last = parse_listing(fetch(listing_url(product_type, page)))
            log.info("[gmsx] %s page %d/%d: %d entries", product_type, page, last, len(entries))
            for e in entries:
                found.setdefault(e.url, e)
            if not entries:
                break
            page += 1
            if delay:
                time.sleep(delay)
    return list(found.values())


# ── Matching ──────────────────────────────────────────────────────────────

def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _words(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


# A trailing nickname in brackets that is not a country tag: "(WAVY25)", "(IQ2000)", "(Victory)".
_NICKNAME_RE = re.compile(r"\s*\((?![A-Z]{2,3}\))[^)]*\)\s*$")
# Our regional / revision / sub-model suffixes, stripped to find a family page.
_FAMILY_SUFFIX_RE = re.compile(
    r"(?:/\d+|\s*\((?:v\d+|[A-Z]{2,3})\)|\s+v\d+(?:\.\d+)?|\s+(?:Russian|Home Banking))$", re.IGNORECASE)


def _exact_key(entry: GmsxEntry, lut: AliasLUT) -> str:
    record = {"brand": entry.brand, "model": entry.name}
    apply_aliases(record, lut)                    # country tags (UK -> GB), renamed models
    return _norm(record["model"])


def _variant_keys(entry: GmsxEntry, lut: AliasLUT) -> set[str]:
    """Their name without a trailing nickname, and every shorter leading run of its words."""
    keys: set[str] = set()
    base = _NICKNAME_RE.sub("", entry.name)
    words = base.split()
    for n in range(1, len(words) + 1):
        record = {"brand": entry.brand, "model": " ".join(words[:n])}
        apply_aliases(record, lut)
        keys.add(_norm(record["model"]))
    keys.discard(_exact_key(entry, lut))
    return keys


def _pick(brand: str, candidates: Iterable[GmsxEntry]) -> GmsxEntry | None:
    """The one candidate, or the one whose brand shares a word with ours; else None."""
    unique = list({e.url: e for e in candidates}.values())
    if len(unique) > 1:
        same_maker = [e for e in unique if _words(brand) & _words(e.brand)]
        if same_maker:
            unique = same_maker
    return unique[0] if len(unique) == 1 else None


def match_models(
    models: Iterable[tuple[int, str, str]],
    entries: list[GmsxEntry],
    lut: AliasLUT,
) -> dict[int, dict[str, Any]]:
    """``{id: {"model", "url", "match"}}`` for every (id, brand, model) with a page."""
    exact: dict[str, list[GmsxEntry]] = {}
    variant: dict[str, list[GmsxEntry]] = {}
    for e in entries:
        exact.setdefault(_exact_key(e, lut), []).append(e)
        for k in _variant_keys(e, lut):
            variant.setdefault(k, []).append(e)

    def find(brand: str, name: str) -> tuple[GmsxEntry | None, str]:
        key = _norm(name)
        if key in exact:
            hit = _pick(brand, exact[key])
            return hit, "exact"
        if key in variant:
            return _pick(brand, variant[key]), "variant"
        return None, ""

    out: dict[int, dict[str, Any]] = {}
    for model_id, brand, name in models:
        hit, kind = find(brand, name)
        if hit is None:
            base = _FAMILY_SUFFIX_RE.sub("", name)
            if base != name:
                hit, _ = find(brand, base)
                kind = "family"
        if hit is not None:
            out[model_id] = {"model": f"{brand} {name}", "url": hit.url, "match": kind}
    return out


def models_from_data_js(path: Path) -> list[tuple[int, str, str]]:
    """(id, brand, model) of every model in a built data.js."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    keys = [c["key"] for c in data["columns"]]
    im, imo = keys.index("brand"), keys.index("model")
    return [(m["id"], m["values"][im] or "", m["values"][imo] or "") for m in data["models"]]


def run(output: Path, db_path: Path, aliases_path: Path, fetch: Callable[[str], str],
        delay: float = 1.0, dry_run: bool = False) -> dict[str, int]:
    """Crawl, match every model of *db_path*, keep manual entries, write *output*. Returns counts."""
    from .aliases import load_aliases
    lut = load_aliases(aliases_path) if aliases_path.exists() else AliasLUT()
    entries = crawl(fetch, delay=delay)
    models = models_from_data_js(db_path)
    generated = match_models(models, entries, lut)
    existing = load_links(output)
    merged = merge_with_manual(generated, existing)
    counts = {kind: sum(1 for e in merged.values() if e.get("match") == kind) for kind in MATCH_KINDS}
    counts.update({"models": len(models), "listed": len(entries),
                   "unlinked": sum(1 for mid, _, _ in models if not merged.get(mid, {}).get("url"))})
    if not dry_run:
        write_links(output, merged)
    return counts


def merge_with_manual(generated: dict[int, dict[str, Any]],
                      existing: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Generated entries, with every existing ``manual`` entry kept as it is."""
    merged = dict(generated)
    for model_id, entry in existing.items():
        if entry.get("match") == "manual":
            merged[model_id] = entry
    return merged

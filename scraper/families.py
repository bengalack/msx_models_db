"""Model families: the Series (same brand) and Rebrand (other brands) columns.

msx.org relates models in several ways; the msx.org parser records them on each
record (internal fields), the merge keeps them, and ``compute_families`` turns
them into groups once the model ids are known:

- ``_series``         the series page a member page defers to ("Sony_HB-75")
- ``_family_links``   qualified links from the page text: a list of
                      ``{"title", "via", "directed"}`` — "localised for … - see X",
                      "There are also specific versions … see X", "sold … as the X",
                      a "localised for" list item "Germany - see X" (see
                      ``msxorg.family_links``); *directed* = X is a version of this page
- ``_variant_names``  model names in the page's variant table (first column
                      "Product" or "Version")
- ``_adapted_from``   "X is the adaptation of Y" (scraper/msxorg.py)
- records sharing one msx.org page, and data/link-shares.json pairs

Two models are related when any of these links them. **Series**: the groups of
related models of the *same* brand; named after the series page ("HB-75") when
one exists, else after the base model's name, linking to the series page or the
base model's page. **Rebrand**: groups of related models spanning *more than
one* brand; named after the original — its brand's initial and model
("D. DPC-200") — linking to its page. Every
member, base / original included, carries the group's value. The base /
original is the member no other member is a version of; ties go to the earliest
year, then the lowest id.

The build writes the result to ``data/families.json`` (generated, committed for
review). Design: technical-design.md, *Feature Design: Families*.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

FAMILIES_PATH = Path("data/families.json")
MSXORG_WIKI = "https://www.msx.org/wiki/"

SERIES_FIELD = "_series"
FAMILY_LINKS_FIELD = "_family_links"
VARIANT_NAMES_FIELD = "_variant_names"

SERIES_KEY = "family_series"
REBRAND_KEY = "family_rebrand"


def _squash(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def page_url(title: str) -> str:
    return MSXORG_WIKI + title.replace(" ", "_")


@dataclass
class Edge:
    a: int            # the version / rebrand ...
    b: int            # ... of this model (when directed)
    signal: str
    directed: bool


@dataclass
class Group:
    name: str
    url: str | None
    root: int
    members: list[int] = field(default_factory=list)


@dataclass
class Families:
    series: list[Group] = field(default_factory=list)
    rebrands: list[Group] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def value_of(self, kind: str) -> dict[int, Group]:
        groups = self.series if kind == "series" else self.rebrands
        return {m: g for g in groups for m in g.members}


class _UnionFind:
    def __init__(self, items: Iterable[int]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self) -> list[list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i in self.parent:
            out[self.find(i)].append(i)
        return [sorted(g) for g in out.values() if len(g) > 1]


def collect_edges(rows: list[dict[str, Any]], link_shares: dict[str, str]) -> list[Edge]:
    """Every relation between two of *rows* (merged models carrying ``_id``)."""
    by_title: dict[str, list[int]] = defaultdict(list)
    by_key: dict[str, int] = {}
    by_name: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r.get("msxorg_title"):
            by_title[r["msxorg_title"]].append(r["_id"])
        by_key[f"{(r.get('brand') or '').lower()}|{(r.get('model') or '').lower()}"] = r["_id"]
        by_name[_squash(r.get("model"))].append(r["_id"])
        by_name[_squash(f"{r.get('brand')} {r.get('model')}")].append(r["_id"])
    makers = {r["_id"]: _squash(r.get("brand")) for r in rows}

    edges: list[Edge] = []
    # Records of one msx.org page (split models, revisions, localised products)
    for title, ids in by_title.items():
        for i in ids[1:]:
            edges.append(Edge(i, ids[0], "same page", directed=False))
    for r in rows:
        rid = r["_id"]
        donor = (r.get("_adapted_from") or {}).get("title")
        for d in by_title.get(donor or "", []):
            edges.append(Edge(rid, d, "adaptation", directed=True))
        for link in r.get(FAMILY_LINKS_FIELD) or []:
            for t in by_title.get(link.get("title") or "", []):
                if t != rid:
                    edges.append(Edge(t, rid, f"text: {link.get('via')}", directed=bool(link.get("directed"))))
        for name in r.get(VARIANT_NAMES_FIELD) or []:
            hits = [i for i in by_name.get(_squash(name), []) if i != rid]
            same_maker = [i for i in hits if makers[i] == makers[rid]]
            for i in sorted(set(same_maker or hits)):
                edges.append(Edge(i, rid, "variant table", directed=True))
    for recipient, donor in link_shares.items():
        if recipient in by_key and donor in by_key:
            edges.append(Edge(by_key[recipient], by_key[donor], "link-share", directed=True))
    # Members of one series page
    by_series: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r.get(SERIES_FIELD):
            by_series[r[SERIES_FIELD]].append(r["_id"])
    for ids in by_series.values():
        for i in ids[1:]:
            edges.append(Edge(i, ids[0], "series page", directed=False))
    return edges


def _root(members: list[int], edges: list[Edge], rows_by_id: dict[int, dict]) -> int:
    """The member no other member is a version of; ties: earliest year, then lowest id."""
    inside = set(members)
    has_parent = {e.a for e in edges if e.directed and e.a in inside and e.b in inside and e.a != e.b}
    candidates = [m for m in members if m not in has_parent] or members
    return min(candidates, key=lambda m: (rows_by_id[m].get("year") or 9999, m))


# A regional tag or revision closing a model name: "V-20 (JP)", "HB-F500 (v2)".
_VARIANT_SUFFIX_RE = re.compile(r"\s*\((?:[A-Z]{2,3}|v\d+)\)$")


def base_name(model: str) -> str:
    """The model's base name for a series: "V-20 (JP)" -> "V-20"."""
    return _VARIANT_SUFFIX_RE.sub("", model).strip() or model


def rebrand_name(brand: str | None, model: str | None) -> str:
    """The Rebrand cell: the original's brand shortened to its initial — "D. DPC-200"."""
    maker = (brand or "").strip()
    initial = f"{maker[0].upper()}. " if maker else ""
    return f"{initial}{model or ''}".strip()


def _series_slug_name(slug: str, brand: str | None) -> str:
    name = slug.replace("_", " ")
    if brand and name.lower().startswith(brand.lower() + " "):
        name = name[len(brand) + 1:]
    return name


def compute_families(rows: list[dict[str, Any]], link_shares: dict[str, str]) -> Families:
    rows_by_id = {r["_id"]: r for r in rows}
    edges = collect_edges(rows, link_shares)
    brand = {i: _squash(r.get("brand")) for i, r in rows_by_id.items()}

    same_brand = _UnionFind(rows_by_id)
    everything = _UnionFind(rows_by_id)
    for e in edges:
        everything.union(e.a, e.b)
        if brand[e.a] == brand[e.b]:
            same_brand.union(e.a, e.b)

    result = Families(edges=edges)
    for members in same_brand.groups():
        root = _root(members, edges, rows_by_id)
        slugs = [rows_by_id[m].get(SERIES_FIELD) for m in [root, *members] if rows_by_id[m].get(SERIES_FIELD)]
        if slugs:
            slug = slugs[0]
            name, url = _series_slug_name(slug, rows_by_id[root].get("brand")), page_url(f"Category:{slug}")
        else:
            title = rows_by_id[root].get("msxorg_title")
            name, url = base_name(rows_by_id[root].get("model") or ""), page_url(title) if title else None
        result.series.append(Group(name=name, url=url, root=root, members=members))
    for members in everything.groups():
        if len({brand[m] for m in members}) < 2:
            continue
        root = _root(members, edges, rows_by_id)
        r = rows_by_id[root]
        title = r.get("msxorg_title")
        result.rebrands.append(Group(name=rebrand_name(r.get("brand"), r.get("model")),
                                     url=page_url(title) if title else None, root=root, members=members))
    result.series.sort(key=lambda g: g.name.lower())
    result.rebrands.sort(key=lambda g: g.name.lower())
    return result


def write_families(path: Path, families: Families, rows_by_id: dict[int, dict[str, Any]]) -> None:
    """``data/families.json``: the groups and the relations behind them (for review)."""
    label = lambda i: f"{rows_by_id[i].get('brand') or ''} {rows_by_id[i].get('model') or ''}".strip()

    def group(g: Group) -> dict[str, Any]:
        return {"name": g.name, "url": g.url, "base": label(g.root),
                "members": [{"id": m, "model": label(m)} for m in g.members]}

    seen = set()
    relations = []
    for e in families.edges:
        key = (e.a, e.b, e.signal)
        if key in seen or e.a == e.b:
            continue
        seen.add(key)
        relations.append({"model": label(e.a), "of" if e.directed else "with": label(e.b), "signal": e.signal})
    payload = {
        "_comment": "Generated by `python -m scraper build` (scraper/families.py) — do not edit; "
                    "Series = related models of one brand, Rebrand = related models across brands. "
                    "See technical-design.md, Feature Design: Families.",
        "series": [group(g) for g in families.series],
        "rebrands": [group(g) for g in families.rebrands],
        "relations": sorted(relations, key=lambda r: (r["model"].lower(), r["signal"])),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)

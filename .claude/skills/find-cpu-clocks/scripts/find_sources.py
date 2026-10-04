"""Candidate service manuals / schematics for the models in docs/data.js.

Three sources, merged into one JSON list (default <cache>/sources.json):
  1. links on each model's msx.org page (local mirror from data/scraper-config.json) whose
     text says service manual / schematic / circuit diagram / technical manual or guide;
  2. the computer manuals on Hans Otten's list (hansotten.file-hunter.com/manuals-and-guides/);
  3. archive.org items matching MSX + service manual / schematic (mediatype texts).
Each entry: {"url", "label", "origin", "models": [msx.org page titles that link it]}.

usage: python find_sources.py [--cache DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

KIND = re.compile(r"service|schemat|circuit|technical (?:manual|guide|data)|repair", re.I)
NOT_COMPUTER = re.compile(r"monitor|printer|mouse|drive|cassette|tape|modem|cartridge|keyboard YK|trackball|"
                          r"scanner|titler|music module|ram cart|memory mapper|interface|joystick|tablet", re.I)
HANS_OTTEN = "https://hansotten.file-hunter.com/manuals-and-guides/"
ARCHIVE_QUERY = 'msx AND ("service manual" OR schematic OR schematics OR "circuit diagram" OR "technical manual" OR "technical guide") AND mediatype:texts'


def curl(url: str) -> bytes:
    return subprocess.run(["curl", "-sL", "--max-time", "120", "-A", "Mozilla/5.0", url], capture_output=True).stdout


def msxorg_links(repo: Path) -> list[dict]:
    config = json.loads((repo / "data" / "scraper-config.json").read_text(encoding="utf-8"))
    mirror = Path(config.get("msxorg_mirror") or "")
    text = (repo / "docs" / "data.js").read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex(";")])
    titles = sorted({(m.get("links") or {}).get("model", "").split("/wiki/")[-1].replace("_", " ")
                     for m in data["models"] if "/wiki/" in (m.get("links") or {}).get("model", "")})
    # Series pages (Category_<series>) too: member pages defer to them, and their External links
    # hold manuals the member pages do not repeat (Category:Sony_HB-75 → the HB-55P/75P/75B manual).
    # Generation listings (Category_MSX2 Computers, …) hold no manuals and are skipped.
    series = sorted(p.name[len("Category_"):-len(" - MSX Wiki.html")] for p in mirror.glob("Category_* - MSX Wiki.html")
                    if not re.search(r"Computers|Components|PSG|_page\d", p.name))
    out: dict[str, dict] = {}
    for title in titles + [f"Category_{s}" for s in series]:
        page = mirror / f"{title} - MSX Wiki.html"
        if not page.exists():
            continue
        body = BeautifulSoup(page.read_bytes(), "lxml")
        body = body.select_one("#bodyContent") or body
        for a in body.find_all("a", href=True):
            li = a.find_parent("li")
            around = li.get_text(" ", strip=True) if li else a.get_text(" ", strip=True)
            href = a["href"]
            if KIND.search(around) and href.startswith("http"):
                entry = out.setdefault(href, {"url": href, "label": a.get_text(" ", strip=True), "origin": "msx.org", "models": []})
                entry["models"].append(title)
    return list(out.values())


def hans_otten() -> list[dict]:
    soup = BeautifulSoup(curl(HANS_OTTEN), "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        if KIND.search(label) and not NOT_COMPUTER.search(label) and a["href"].lower().endswith(".pdf"):
            out.append({"url": urllib.parse.urljoin(HANS_OTTEN, a["href"]), "label": label, "origin": "hansotten", "models": []})
    return out


def archive_org() -> list[dict]:
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": ARCHIVE_QUERY, "fl[]": ["identifier", "title"], "rows": "1000", "output": "json"}, doseq=True)
    docs = json.loads(curl(url) or b"{}").get("response", {}).get("docs", [])
    return [{"url": f"https://archive.org/details/{d['identifier']}", "label": d.get("title", ""), "origin": "archive.org",
             "models": []} for d in docs if not NOT_COMPUTER.search(str(d.get("title", "")))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "msx-manuals")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    sources = msxorg_links(args.repo) + hans_otten() + archive_org()
    out = args.cache / "sources.json"
    out.write_text(json.dumps(sources, indent=1, ensure_ascii=False), encoding="utf-8")
    by_origin: dict[str, int] = {}
    for s in sources:
        by_origin[s["origin"]] = by_origin.get(s["origin"], 0) + 1
    print(f"{len(sources)} candidate documents {by_origin} -> {out}")


if __name__ == "__main__":
    main()

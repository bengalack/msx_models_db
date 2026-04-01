"""Scrape MSX model data from msx.org wiki pages."""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .exclude import ExcludeList
from .http import fetch_with_retry

log = logging.getLogger(__name__)

BASE_URL = "https://www.msx.org"
WIKI_URL = f"{BASE_URL}/wiki/"

# Category pages that list models by MSX standard.
CATEGORY_URLS: dict[str, str] = {
    "MSX2": f"{WIKI_URL}Category:MSX2_Computers",
    "MSX2+": f"{WIKI_URL}Category:MSX2%2B_Computers",
    "turbo R": f"{WIKI_URL}Category:MSX_turbo_R_Computers",
}

# Pages that are overview/standard pages, not actual model pages.
SKIP_TITLES = {
    "MSX2", "MSX2+", "MSX turbo R", "1chipMSX",
}

# ── Regex helpers for field extraction ───────────────────────────────

_RE_KB = re.compile(r"(\d+)\s*kB", re.IGNORECASE)
_RE_YEAR = re.compile(r"(\d{4})")
_RE_VDP = re.compile(r"(V9958|V9938|TMS99[12][89]A?)", re.IGNORECASE)
_RE_RAM_MAIN = re.compile(
    r"(\d+)\s*kB(?:\s+(?:in|mapped|main|slot))", re.IGNORECASE
)
_RE_FLOPPY = re.compile(
    r"(\d+)\s*(?:×|x)\s*(?:\d+kB\s+)?(?:3[,.]5|5[,.]25)[\"\u201D\u2033]?\s*"
    r"(?:floppy|disk|FDD)",
    re.IGNORECASE,
)
_RE_FLOPPY_SINGLE = re.compile(
    r"(?:one|single|1)?\s*(?:\d+\s*kB\s+)?(?:3[.,]5|5[.,]25)[\"\u201D\u2033]?"
    r"\s*(?:floppy|disk)",
    re.IGNORECASE,
)
_RE_CART_SLOTS = re.compile(r"(\d+)\s*cartridge\s*slot", re.IGNORECASE)


def _text_content(tag: Tag) -> str:
    """Get cleaned text from a BeautifulSoup tag."""
    return tag.get_text(separator=" ", strip=True)


# ── Category page parsing ────────────────────────────────────────────


def list_model_pages(
    session: requests.Session,
    *,
    delay: float = 0.5,
) -> list[dict[str, str]]:
    """Enumerate all model page URLs from the category pages.

    Returns list of {title, url, standard}.
    """
    models: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for standard, cat_url in CATEGORY_URLS.items():
        log.info("Fetching category page for %s…", standard)
        resp = fetch_with_retry(session, cat_url)
        soup = BeautifulSoup(resp.content, "lxml")

        # Model links are inside the <div id="mw-pages"> or similar.
        # They appear as <a> tags inside list items under the category listing.
        # Look for links that point to /wiki/... pages (not Category: or Special:).
        for a_tag in soup.select("#mw-pages a, .mw-category a"):
            href = a_tag.get("href", "")
            title = a_tag.get("title", "") or _text_content(a_tag)
            if not href or not title:
                continue
            # Skip non-article links.
            if "/wiki/Category:" in href or "/wiki/Special:" in href:
                continue
            if title in SKIP_TITLES:
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            models.append({
                "title": title,
                "url": full_url,
                "standard": standard,
            })

        time.sleep(delay)

    log.info("Found %d model pages across all categories", len(models))
    return models


# ── Model page parsing ───────────────────────────────────────────────


def _find_specs_table(soup: BeautifulSoup) -> dict[str, str] | None:
    """Find the specifications infobox table and return its rows as a dict.

    The msx.org wiki uses a 2-column table (key | value) near the top of the page.
    Keys include: Brand, Model, Year, Region, RAM, VRAM, Video, Audio, etc.
    """
    for table in soup.find_all("table"):
        rows: dict[str, str] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) == 2:
                key = _text_content(cells[0]).rstrip(":").strip()
                val = _text_content(cells[1]).strip()
                if key and val:
                    rows[key] = val
        # Check if this looks like a specs table: must have "Brand" or "Model".
        if "Brand" in rows or "Model" in rows:
            return rows
    return None


def _parse_year(raw: str) -> int | None:
    """Extract a 4-digit year from a date string like '1988-10-21' or '1986'."""
    m = _RE_YEAR.search(raw)
    return int(m.group(1)) if m else None


def _parse_ram_kb(raw: str) -> int | None:
    """Extract main RAM in KB from strings like '64kB in slot 3-0 + 16kB SRAM'."""
    # First try the specific "NNkB in/mapped/main/slot" pattern.
    m = _RE_RAM_MAIN.search(raw)
    if m:
        return int(m.group(1))
    # Fallback: first kB number.
    m = _RE_KB.search(raw)
    return int(m.group(1)) if m else None


def _parse_vram_kb(raw: str) -> int | None:
    """Extract VRAM in KB from strings like '128kB'."""
    m = _RE_KB.search(raw)
    return int(m.group(1)) if m else None


def _parse_vdp(raw: str) -> str | None:
    """Extract VDP chip name from strings like 'Yamaha V9958'."""
    m = _RE_VDP.search(raw)
    return m.group(1) if m else None


def _parse_audio(raw: str) -> dict[str, Any]:
    """Parse audio string into PSG and FM chip info."""
    result: dict[str, Any] = {}
    raw_lower = raw.lower()
    if "psg" in raw_lower or "ay-3-8910" in raw_lower or "ym2149" in raw_lower:
        result["psg"] = "AY-3-8910"
        result["audio_channels"] = 3
    # FM chips.
    fm_chips: list[str] = []
    if "msx-music" in raw_lower or "ym2413" in raw_lower or "opll" in raw_lower:
        fm_chips.append("MSX-MUSIC")
    if "msx-audio" in raw_lower or "y8950" in raw_lower or "opa" in raw_lower:
        fm_chips.append("MSX-AUDIO")
    if "moonsound" in raw_lower or "opl4" in raw_lower:
        fm_chips.append("MoonSound")
    if fm_chips:
        result["fm_chip"] = ", ".join(fm_chips)
    return result


def _parse_media(raw: str) -> dict[str, Any]:
    """Parse media string into floppy drives and other storage."""
    result: dict[str, Any] = {}
    raw_lower = raw.lower()
    # Floppy drives: try "N × 720kB 3.5" pattern first.
    if "floppy" in raw_lower or "disk drive" in raw_lower or "3,5" in raw_lower or "3.5" in raw_lower:
        # Try regex to extract numeric count (requires explicit × or x separator).
        m = _RE_FLOPPY.search(raw)
        if m:
            result["floppy_drives"] = m.group(1)
        elif "two" in raw_lower:
            result["floppy_drives"] = "2"
        elif "three" in raw_lower:
            result["floppy_drives"] = "3"
        else:
            # Default to 1 if floppy is mentioned.
            result["floppy_drives"] = "1"
    if "cartridge" in raw_lower:
        m = _RE_CART_SLOTS.search(raw)
        if m:
            result["cartridge_slots"] = int(m.group(1))
    return result


def _parse_connections(soup: BeautifulSoup) -> dict[str, Any]:
    """Look for connectivity info in the Connections section."""
    result: dict[str, Any] = {}
    ports: list[str] = []

    # Look for "Connections" section.
    for heading in soup.find_all(["h2", "h3"]):
        if "connection" in _text_content(heading).lower():
            # Get the list after this heading.
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3"):
                text = _text_content(sibling).lower()
                if "data recorder" in text or "cassette" in text:
                    if "Cassette" not in ports:
                        ports.append("Cassette")
                    if "tape_interface" not in result:
                        result["tape_interface"] = "Yes"
                if "printer" in text or "parallel" in text or "centronics" in text:
                    if "Printer" not in ports:
                        ports.append("Printer")
                if "cartridge slot" in text:
                    m = re.search(r"(\d+)\s*(?:×|x)?\s*cartridge", text)
                    if m:
                        result["cartridge_slots"] = int(m.group(1))
                    elif "cartridge_slots" not in result:
                        result["cartridge_slots"] = 2  # common default
                sibling = sibling.find_next_sibling()
            break

    if ports:
        # Sort ports alphabetically for normalization
        result["connectivity"] = ", ".join(sorted(ports, key=lambda s: s.lower()))
    return result


def parse_model_page(
    html: bytes,
    standard: str,
    page_title: str,
) -> dict[str, Any] | None:
    """Parse a single model wiki page. Returns field dict or None if no specs table."""
    soup = BeautifulSoup(html, "lxml")
    specs = _find_specs_table(soup)
    if not specs:
        log.warning("No specs table found on %s — skipped", page_title)
        return None

    brand = specs.get("Brand", "").strip()
    model = specs.get("Model", "").strip()
    if not model:
        log.warning("No Model field in specs table on %s — skipped", page_title)
        return None

    # Clean up brand: "Philips (Manufacturer: Sanyo)" → "Philips"
    brand = re.sub(r"\s*\(.*?\)\s*", "", brand).strip()

    result: dict[str, Any] = {
        "manufacturer": brand,
        "model": model,
        "standard": standard,
        "msxorg_title": page_title,
    }

    # Year
    year_raw = specs.get("Year", "")
    if year_raw:
        result["year"] = _parse_year(year_raw)

    # Region
    region = specs.get("Region", "")
    if region:
        result["region"] = region

    # RAM
    ram_raw = specs.get("RAM", "")
    if ram_raw:
        ram = _parse_ram_kb(ram_raw)
        if ram:
            result["main_ram_kb"] = ram

    # VRAM
    vram_raw = specs.get("VRAM", "")
    if vram_raw:
        vram = _parse_vram_kb(vram_raw)
        if vram:
            result["vram_kb"] = vram

    # Video / VDP
    video_raw = specs.get("Video", "")
    if video_raw:
        vdp = _parse_vdp(video_raw)
        if vdp:
            result["vdp"] = vdp

    # Audio
    audio_raw = specs.get("Audio", "")
    if audio_raw:
        result.update(_parse_audio(audio_raw))

    # Media (floppy, cartridge slots) — also check Extras, which often has
    # the explicit drive count (e.g. "Two 720kB 3,5" floppy disk drives")
    # when Media only describes the format (e.g. "2DD floppy disks").
    media_raw = " ".join(filter(None, [specs.get("Media", ""), specs.get("Extras", "")]))
    if media_raw:
        result.update(_parse_media(media_raw))

    # Keyboard layout
    kb = specs.get("Keyboard layout", "")
    if kb:
        result["keyboard_layout"] = kb

    # Connections section for tape, printer, cartridge slots.
    conn = _parse_connections(soup)
    # Only set if not already found from Media or specs table.
    for k, v in conn.items():
        if k not in result:
            result[k] = v

    # Remove None values.
    return {k: v for k, v in result.items() if v is not None}


# ── Main entry point ─────────────────────────────────────────────────


def fetch_all(
    session: requests.Session | None = None,
    *,
    delay: float = 0.5,
    limit: int | None = None,
    exclude_list: ExcludeList | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse all msx.org model pages. Returns list of model dicts."""
    if session is None:
        session = requests.Session()
    session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"

    pages = list_model_pages(session, delay=delay)
    if limit:
        pages = pages[:limit]

    models: list[dict[str, Any]] = []
    excluded = 0
    skipped = 0
    errors = 0

    for i, page in enumerate(pages):
        title = page["title"]
        url = page["url"]
        standard = page["standard"]
        try:
            resp = fetch_with_retry(session, url)
            result = parse_model_page(resp.content, standard, title)
            if result:
                if exclude_list and exclude_list.is_excluded(
                    result.get("manufacturer"), result.get("model")
                ):
                    log.debug(
                        "[exclude:skip] Excluded model | manufacturer=%s model=%s source=msxorg",
                        result.get("manufacturer"), result.get("model"),
                    )
                    excluded += 1
                else:
                    models.append(result)
            else:
                skipped += 1
        except Exception:
            log.exception("Error fetching/parsing %s", title)
            errors += 1

        if delay and i < len(pages) - 1:
            time.sleep(delay)

    total = len(pages)
    fail_rate = (errors / total * 100) if total else 0
    log.info(
        "msx.org: %d models extracted, %d excluded, %d skipped, %d errors (%.1f%% failure rate)",
        len(models), excluded, skipped, errors, fail_rate,
    )
    if total and fail_rate > 20:
        log.error(
            "Failure rate %.1f%% exceeds 20%% threshold — results may be unreliable",
            fail_rate,
        )

    return models

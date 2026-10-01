"""Scrape MSX model data from msx.org wiki pages."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Callable
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .aliases import FORMER_MODEL_FIELD, KNOWN_AS_FIELD, LOCALISED_FIELD
from .inherit import fill_blanks
from .market_status import MARKET_RARE, MARKET_UNRELEASED
from .families import FAMILY_LINKS_FIELD, SERIES_FIELD, VARIANT_NAMES_FIELD
from .exclude import ExcludeList
from .revisions import REVISION_FIELD, revision_name, revision_numbers
from .mirror import LivePageSource, MirrorPageSource, PageSource, slug_to_filename
from .msxorg_series import (
    VariantContext,
    choose_slotmap_table,
    localised_specs,
    named_specs,
    product_names,
    page_context,
    resolve_specs,
    revisions_in,
    series_context,
    series_slug,
)
from .msxorg_slotmap import (
    _flatten_table,
    mapper_from_table,
    parse_mapper_from_soup,
    parse_slotmap_from_soup,
    parse_slotmap_table,
)

log = logging.getLogger(__name__)

BASE_URL = "https://www.msx.org"
WIKI_URL = f"{BASE_URL}/wiki/"

# Category pages that list models by MSX standard.
CATEGORY_URLS: dict[str, str] = {
    "MSX2":    f"{WIKI_URL}Category:MSX2_Computers",
    "MSX2+":   f"{WIKI_URL}Category:MSX2%2B_Computers",
    "turbo R": f"{WIKI_URL}Category:MSX_turbo_R_Computers",
    "MSX1":    f"{WIKI_URL}Category:MSX1_Computers",
}

# Ranking for "pick the highest" logic when a model appears in multiple categories.
GENERATION_RANK: dict[str, int] = {"MSX1": 0, "MSX2": 1, "MSX2+": 2, "turbo R": 3}

# Pages that are overview/standard pages, not actual model pages.
# NOTE: "1chipMSX" is intentionally NOT in this set — it is an FPGA-based
# unofficial model with a dedicated wiki page and must be scraped as a model.
SKIP_TITLES = {
    "MSX1", "MSX2", "MSX2+", "MSX turbo R",
}

def _find_next_page_url(soup: BeautifulSoup) -> str | None:
    """Return the MediaWiki 'next N' pagination URL from a category page, or None.

    Handles both URL formats used by msx.org:
      - /wiki/Category:MSX1_Computers?pagefrom=Toshiba+HX-22I  (newer MediaWiki)
      - /wiki/index.php?title=Category:MSX1_Computers&from=Toshiba+HX-22I  (older)
    The pagination link may appear outside the #mw-pages div, so the full page
    is searched.

    The older index.php form is normalised to the canonical /wiki/<title>?pagefrom=<from>
    form so that MirrorPageSource can derive the correct filename.
    """
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not ("pagefrom=" in href or "from=" in href):
            continue
        if "next" not in _text_content(a).lower():
            continue
        full_url = urljoin(BASE_URL, href)
        # Normalise older index.php?title=Category:X&from=Y → /wiki/Category:X?pagefrom=Y
        if "index.php" in full_url and "title=" in full_url:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(full_url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            title = qs.get("title", [None])[0]
            from_val = qs.get("from", [None])[0]
            if title:
                canonical = f"{BASE_URL}/wiki/{title}"
                if from_val:
                    canonical += f"?pagefrom={from_val}"
                return canonical
        return full_url
    return None


# ── Regex helpers for field extraction ───────────────────────────────

_RE_KB = re.compile(r"(\d+)\s*kB", re.IGNORECASE)
_RE_YEAR = re.compile(r"(\d{4})")
# VDP part numbers: Yamaha V99x8; TI TMS99x8/99x9 and the TMS91x8/91x9 family
# (optionally written "TMS-9118", optionally followed by a package suffix such as
# "NL", which is not part of the chip); Toshiba T6950 and Yamaha YM2220 clones.
_RE_VDP = re.compile(
    r"\b(V99[35]8|TMS-?9[19][12][89]A?|T6950A?|YM2220)(?=[A-Z]*\b)", re.IGNORECASE
)
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
    source: PageSource,
    *,
    delay: float = 0.5,
) -> list[dict[str, str]]:
    """Enumerate all model page URLs from the category pages.

    Returns list of {title, url, standard}.
    """
    url_to_entry: dict[str, dict[str, str]] = {}
    any_category = False

    for standard, cat_url in CATEGORY_URLS.items():
        current_url = cat_url
        page_num = 1
        while True:
            log.info("Fetching category page for %s (page %d)…", standard, page_num)
            content = source.fetch_category(standard, current_url, page=page_num)
            if content is None:
                break
            any_category = True
            soup = BeautifulSoup(content, "lxml")

            for a_tag in soup.select("#mw-pages a, .mw-category a"):
                href = a_tag.get("href", "")
                title = a_tag.get("title", "") or _text_content(a_tag)
                if not href or not title:
                    continue
                if "/wiki/Category:" in href or "/wiki/Special:" in href:
                    continue
                if title in SKIP_TITLES:
                    continue
                full_url = urljoin(BASE_URL, href)
                if full_url in url_to_entry:
                    entry = url_to_entry[full_url]
                    if GENERATION_RANK.get(standard, -1) > GENERATION_RANK.get(entry["standard"], -1):
                        entry["standard"] = standard
                    continue
                url_to_entry[full_url] = {
                    "title": title,
                    "url": full_url,
                    "standard": standard,
                }

            next_url = _find_next_page_url(soup)
            if next_url is None:
                break
            current_url = next_url
            page_num += 1
            if delay:
                time.sleep(delay)

        if delay:
            time.sleep(delay)

    if not any_category and hasattr(source, "scan_pages"):
        log.info("No category pages available — enumerating model pages from the mirror directory")
        return _list_model_pages_from_mirror(source)

    models = list(url_to_entry.values())
    log.info("Found %d model pages across all categories", len(models))
    return models


# Category slug (decoded, e.g. "Category:MSX2+_Computers") → standard.
_CATEGORY_SLUG_TO_STANDARD: dict[str, str] = {
    unquote(url.split("/wiki/", 1)[1]): standard for standard, url in CATEGORY_URLS.items()
}
_RE_PAGE_NAME = re.compile(rb'wgPageName\s*[=:]\s*"((?:[^"\\]|\\.)*)"')


def _list_model_pages_from_mirror(source: Any) -> list[dict[str, str]]:
    """Enumerate model pages by scanning a mirror directory that has no category pages.

    Each page supplies its own wiki slug (``wgPageName``) and its standard (the
    highest-ranked MSX computer category in its category links). Pages in none
    of those categories, or without a slug, are skipped.
    """
    models: list[dict[str, str]] = []
    for filename, content in source.scan_pages():
        m = _RE_PAGE_NAME.search(content)
        if not m:
            log.warning("[mirror:scan] No wgPageName in %s — skipping", filename)
            continue
        slug = m.group(1).decode("utf-8").replace("\\/", "/")
        soup = BeautifulSoup(content, "lxml")
        standard: str | None = None
        for a_tag in soup.select("#mw-normal-catlinks a"):
            href = unquote(a_tag.get("href", ""))
            cat = _CATEGORY_SLUG_TO_STANDARD.get(href.split("/wiki/", 1)[-1])
            if cat and GENERATION_RANK[cat] > GENERATION_RANK.get(standard or "", -1):
                standard = cat
        title = slug.replace("_", " ")
        if standard is None or title in SKIP_TITLES:
            log.debug("[mirror:scan] Not an MSX computer model page: %s", filename)
            continue
        url = WIKI_URL + quote(slug, safe="/")
        if slug_to_filename(url) != filename:
            log.warning(
                "[mirror:scan] Page %r is saved as %s, expected %s — skipping",
                slug, filename, slug_to_filename(url),
            )
            continue
        models.append({"title": title, "url": url, "standard": standard})
    log.info("Found %d model pages in the mirror directory", len(models))
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


_VDP_RANK: dict[str, int] = {"v9958": 2, "v9938": 1}  # TMS99xx → 0 (default)


def _parse_vdp(raw: str) -> str | None:
    """Extract VDP chip name; when multiple are listed, return the highest-ranked."""
    matches = [m.upper().replace("-", "") for m in _RE_VDP.findall(raw)]
    if not matches:
        return None
    return max(matches, key=lambda v: _VDP_RANK.get(v.lower(), 0))


def _parse_audio(raw: str) -> dict[str, Any]:
    """Parse audio string into PSG and FM chip info."""
    result: dict[str, Any] = {}
    raw_lower = raw.lower()
    if "psg" in raw_lower or "ay-3-8910" in raw_lower or "ym2149" in raw_lower:
        result["psg"] = "Yes"   # present; which chip is not yet specified
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
            result["scraped_cart_slots"] = int(m.group(1))
    return result


def _connection_items(sibling: Any) -> list[str]:
    """Return individual text strings from a connections-section sibling.

    ``<ul>`` elements are decomposed into their ``<li>`` children so that a
    negation in one bullet (e.g. "Note: No printer port!") does not bleed into
    sibling bullets that genuinely describe a port.
    """
    if getattr(sibling, "name", None) == "ul":
        return [_text_content(li) for li in sibling.find_all("li", recursive=False)]
    return [_text_content(sibling)]


# Negation words that, when present in the same bullet as a port keyword,
# indicate the port is absent rather than present.
# A tape connector that needs an adapter: "MT/IF connector (requires the FA-32 CMT I/F package ...)".
_TAPE_ADAPTER_RE = re.compile(r"\bCMT\b|\bMT/IF\b", re.IGNORECASE)
_NEGATION_RE = re.compile(r"\b(no|not|without|none)\b", re.IGNORECASE)


def _parse_connections(soup: BeautifulSoup) -> dict[str, Any]:
    """Tape interface, printer port and cartridge slots from the Connections section.

    Tape Interface is "Yes" when a (not negated) item mentions a cassette or
    data recorder, "Adapter" when the only tape connector needs one (Casio
    "MT/IF connector", CMT I/F package); PRN Port is "Yes" when an item
    mentions a printer, parallel or Centronics port. Each is "No" otherwise,
    and unknown (not set) when the page has no Connections section.
    """
    result: dict[str, Any] = {}
    printer: bool | None = None
    tape: bool | None = None
    modem = False
    tape_adapter = False

    # Look for "Connections" section.
    for heading in soup.find_all(["h2", "h3"]):
        if "connection" in _text_content(heading).lower():
            printer = tape = False
            # Get the list after this heading.
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3"):
                for item_text in _connection_items(sibling):
                    text = item_text.lower()
                    negated = bool(_NEGATION_RE.search(text))
                    if not negated:
                        if _TAPE_ADAPTER_RE.search(item_text):
                            tape_adapter = True
                        elif "data recorder" in text or "cassette" in text:
                            tape = True
                        if "printer" in text or "parallel" in text or "centronics" in text:
                            printer = True
                        if _PHONE_JACK_RE.search(item_text):
                            modem = True
                    # Cartridge slot count is structural — not negation-sensitive.
                    if "cartridge slot" in text:
                        m = re.search(r"(\d+)\s*(?:×|x)?\s*cartridge", text)
                        if m:
                            result["scraped_cart_slots"] = int(m.group(1))
                        elif "scraped_cart_slots" not in result:
                            result["scraped_cart_slots"] = 2  # common default
                sibling = sibling.find_next_sibling()
            break

    if printer is not None:
        result["printer_port"] = "Yes" if printer else "No"
    if tape is not None:
        result["tape_interface"] = "Yes" if tape else "Adapter" if tape_adapter else "No"
    if modem:   # a telephone-line socket on the machine: built-in modem (RS-232C "for modem" does not count)
        result["modem"] = MODEM_YES
    return result


# ── "Also known as" ─────────────────────────────────────────────────────


_QUOTES = "'\"‘’“”"
# Where the alias name ends: punctuation, or a word that starts the rest of the sentence.
_KNOWN_AS_END = r"(?=\s*(?:[,.;(]|$)|\s+(?:as|is|was|has|had|and|for|in|with|by|but)\b)"


def known_as_names(page: bytes | BeautifulSoup, model: str, brand: str) -> list[str]:
    """Other names the page gives *its own* model ("also known as ...").

    Only sentences whose subject is the page's model count: "The [brand] <model>
    [computer], (also | more commonly) known (simply) as (the) X" or "This model
    is also known as X". Sentences about another computer ("the adaptation of
    the MPC-25FD computer, also known as Wavy 25"), a revision, software, chips
    or companies are not aliases.
    """
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    body = soup.select_one("#bodyContent") or soup
    subject = rf"(?:{re.escape(brand)}\s+)?{re.escape(model)}(?:\s+computer)?" if model else r"(?!)"
    pattern = re.compile(
        rf"\b(?:The\s+{subject}|This\s+(?:model|computer|machine))\s*,?\s*"
        rf"(?:(?:is|was)\s+)?(?:also|more\s+commonly|commonly|better)?\s*known\s+(?:simply\s+)?as\s+"
        rf"(?:the\s+)?[{_QUOTES}]?\s*(?P<name>[A-Za-z0-9][A-Za-z0-9\-/+ ]*?)\s*[{_QUOTES}]?{_KNOWN_AS_END}",
        re.IGNORECASE,
    )
    names: list[str] = []
    for node in body.find_all(["p", "li"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        for m in pattern.finditer(text):
            name = m.group("name").strip()
            if name and name.upper() != model.upper() and name not in names and len(name) <= 30:
                names.append(name)
    return names


# ── Market status ───────────────────────────────────────────────────────
#
# "Unreleased" or "Rare", from what the page says about *its own* model.
# Design: technical-design.md, *Feature Design: Market Status*.

# MARKET_UNRELEASED / MARKET_RARE: scraper/market_status.py (shared with the openMSX description rule).

# Specs fields msx.org fills with "unreleased" / "1986 (never released)".
_STATUS_FIELDS = ("Year", "Region", "Launch price")
_UNRELEASED_VALUE_RE = re.compile(r"^\s*(?:unreleased|non-released)\b|\b(?:never|not)\s+released\b", re.IGNORECASE)
# A specs value that is only a status ("unreleased") is not a region.
_STATUS_ONLY_RE = re.compile(r"^\s*(?:unreleased|non-released|never released)\s*$", re.IGNORECASE)

_UNRELEASED_PHRASE = (
    r"(?:(?:has|had)\s+never\s+been\s+released|was\s+never\s+released|(?:was|has)\s+not\s+been\s+released"
    r"|(?:is|was)\s+(?:a|an)\s+(?:\w+\s+){0,2}?(?:unreleased|non-released)"
    r"|(?:has\s+|is\s+)?remained\s+(?:at\s+the\s+prototype\s+level|a\s+prototype))"
)
# Sentence breaks, but not after "a.k.a." ("The PHC-25SK a.k.a. Wavy25SK is ...").
_SENTENCE_SPLIT_RE = re.compile(r"(?<![aA]\.k\.a\.)(?<=[.!?])\s+")
_RARE_TAIL = r"(?:(?:a|an|actually)\s+)?(?:(?:very|extremely)\s+)?rare\b(?!\s+(?:for|on|nowadays))"
_FEW_KNOWN_RE = re.compile(
    r"\b(?:very|only\s+a)\s+few\s+units\s+(?:are|were)\s+known\s+to\s+exist"
    r"|\bonly\s+one\s+(?:system|unit|machine)\s+is\s+known\s+to\s+exist",
    re.IGNORECASE,
)


def _page_subject(names: list[str], brand: str) -> str:
    """Regex for a sentence subject that is the page's own model.

    The model's names (with or without brand, optionally "computer"),
    "This model/machine/computer/system/version" or "It". Shared by the
    Market status and Modem description rules.
    """
    named = "|".join(re.escape(n) for n in sorted({n for n in names if n}, key=len, reverse=True)) or r"(?!)"
    brand_part = rf"(?:{re.escape(brand)}\s+)?" if brand else ""
    return (rf"(?:(?:The\s+)?{brand_part}(?:{named})(?:\s+computer)?"
            rf"|This\s+(?:model|machine|computer|system|version)|It)")


# The subject opens the sentence (after an optional "Note:").
_SUBJECT_START = r"^(?:Note\s*:\s*)?"
# "The Sanyo MPC-3, a.k.a Wavy3 , is ..." / "The PHC-25SK a.k.a. Wavy25SK is ..."
_APPOSITION = r"(?:\s*,[^,]{1,40},|\s+a\.?k\.?a\.?\s+[\w+-]{1,30})?"
# Up to the phrase, no new subject: "It was planned to …, but it has never been released" is not about the model.
_SUBJECT_GAP = r"(?:(?!\b(?:it|they)\b)[^.]){0,120}?"


def _status_patterns(names: list[str], brand: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """(unreleased, rare) sentence patterns whose subject is the page's own model."""
    subject = _page_subject(names, brand)
    unreleased = re.compile(
        rf"(?:{_SUBJECT_START}{subject}|\bthis\s+(?:model|machine|computer|system))\b{_SUBJECT_GAP}\b{_UNRELEASED_PHRASE}",
        re.IGNORECASE,
    )
    rare = re.compile(
        rf"{_SUBJECT_START}(?:{subject}{_APPOSITION}\s+(?:is|was|seems\s+to\s+be)\s+{_RARE_TAIL}"
        rf"|It['’]s\s+{_RARE_TAIL}"
        rf"|This\s+(?:very\s+)?rare\b)"
        rf"|\bthis\s+(?:model|machine|computer|system)\s+(?:is|was|seems\s+to\s+be)\s+{_RARE_TAIL}",
        re.IGNORECASE,
    )
    return unreleased, rare


def market_status(page: bytes | BeautifulSoup, specs: dict[str, str], names: list[str], brand: str) -> str | None:
    """"Unreleased", "Rare" or None for the page's model.

    Unreleased: a Year / Region / Launch price value says so ("unreleased",
    "1986 (never released)"), or a sentence whose subject is the model does
    ("This computer has never been released", "The X is an unreleased
    prototype", "It has remained at the prototype level").
    Rare: a sentence whose subject is the model calls it (very) rare ("The X is
    a very rare MSX1 computer", "This model is very rare", "It's a rare version
    of …", "This rare machine …"), or says very few units are known to exist.
    Sentences about something else — "a few rare cartridges", "a lightpen …
    was never released", "one of the rare MSX1 computers having …" — do not
    count. Unreleased wins over Rare.
    """
    if any(_UNRELEASED_VALUE_RE.search(specs.get(f, "")) for f in _STATUS_FIELDS):
        return MARKET_UNRELEASED
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    body = soup.select_one("#bodyContent") or soup
    unreleased, rare = _status_patterns(names, brand)
    found_rare = False
    for node in body.find_all(["p", "li"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        for sentence in _SENTENCE_SPLIT_RE.split(text):
            if unreleased.search(sentence):
                return MARKET_UNRELEASED
            if rare.search(sentence) or _FEW_KNOWN_RE.search(sentence):
                found_rare = True
    return MARKET_RARE if found_rare else None

# ── Modem ───────────────────────────────────────────────────────────────
#
# "Yes" for a built-in modem; never "No" (an external modem can always be added).
# Design: technical-design.md, *Feature Design: Modem Column*.

MODEM_YES = "Yes"

_MODEM_WORD_RE = re.compile(r"\bmodem\b", re.IGNORECASE)
# A telephone-line socket on the machine itself: "RJ11 modular connector (telephone line)".
_PHONE_JACK_RE = re.compile(r"\bRJ-?11\b|\bmodular\s+connectors?\b", re.IGNORECASE)
# "The FS-A1FM ... has a built-in modem", "It has a Russian keyboard and a non-standard modem".
_HAS_MODEM = r"\b(?:has|have|had|with|includes?|comes\s+with|contains?)\b[^.]{0,80}?\bmodem\b"


def modem_from_specs(specs: dict[str, str]) -> bool:
    """A specs Extras item (not negated) names a modem: "Modem", "built-in modem …", "non-standard modem"."""
    return any(_MODEM_WORD_RE.search(item) and not _NEGATION_RE.search(item)
               for item in specs.get("Extras", "").split(","))


def modem_in_description(page: bytes | BeautifulSoup, names: list[str], brand: str) -> bool:
    """A sentence whose subject is the page's model says it has a modem.

    Side notes about other machines or versions ("a special version with a
    modem", "the FS-CM1 modem") do not count.
    """
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    body = soup.select_one("#bodyContent") or soup
    pattern = re.compile(
        rf"{_SUBJECT_START}{_page_subject(names, brand)}{_APPOSITION}\b{_SUBJECT_GAP}{_HAS_MODEM}", re.IGNORECASE)
    for node in body.find_all("p"):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        if any(pattern.search(s) for s in _SENTENCE_SPLIT_RE.split(text)):
            return True
    return False

# ── Adaptations ─────────────────────────────────────────────────────────
#
# "The Fenner FPC-900 is the adaptation of the Sanyo MPC-25FD computer ..." —
# the adaptation's blanks are filled from the donor model's record.
# Design: .claude/artifacts/planning/2026-09-26-adaptations-design.md

# Internal field on an msx.org record: {"title": donor page title, "revision": N}.
ADAPTED_FROM_FIELD = "_adapted_from"

# Which fields travel from a donor is shared with link-shares: see scraper/inherit.py.

_LINK_START, _LINK_END = "\x01", "\x02"
_NOT_A_MODEL_PAGE = re.compile(r"^(?:Category|File|Image|Special|Template|Help|User):|index\.php", re.IGNORECASE)
_ADAPTATION_RE = re.compile(
    r"(?:^|\s)(?P<subj>(?:The|This)\s+[^.]{1,80}?|[Ii]t(?:'s|’s|\s+is|\s+was))\s+"
    r"(?:(?:is|was)\s+)?(?:actually\s+)?(?:the|an|one\s+of\s+the(?:\s+\w+)?)\s+(?:\w+\s+)?adaptations?\b(?P<rest>.*)"
)
_ADAPTED_FOR_RE = re.compile(
    rf"(?:^|\s)(?P<subj>(?:The|This)\s+[^.{_LINK_START}]{{1,60}}?)\s+is\s+the\s+"
    rf"{_LINK_START}(?P<slug>[^{_LINK_END}]+){_LINK_END}[^.{_LINK_START}]{{0,60}}?\s+adapted\s+for\b"
)
_LINK_RE = re.compile(rf"{_LINK_START}(?P<slug>[^{_LINK_END}]*){_LINK_END}")


def _text_with_links(node: Tag) -> str:
    """Node text with each wiki link marked as <START>slug<END> before its anchor text."""
    parts: list[str] = []
    for el in node.descendants:
        if isinstance(el, Tag) and el.name == "a":
            href = el.get("href", "")
            slug = unquote(href.split("/wiki/", 1)[1]) if "/wiki/" in href else ""
            parts.append(f" {_LINK_START}{slug}{_LINK_END}")
        elif isinstance(el, NavigableString) and not isinstance(el, Comment):
            parts.append(str(el))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _is_own_subject(subject: str, model: str) -> bool:
    """The sentence is about the page's own model (not another computer)."""
    plain = _LINK_RE.sub(" ", subject).strip().lower()
    if plain.startswith("it") or plain in ("this computer", "this machine", "this model"):
        return True
    first = re.split(r"[\s(]", model.strip().lower(), maxsplit=1)[0]
    return bool(first) and first in plain


def adapted_from(page: bytes | BeautifulSoup, model: str, brand: str) -> dict[str, Any] | None:
    """The model this page's model is an adaptation of, or None.

    ``{"title": "<donor page title>", "revision": N}``. Only forward statements
    about the page's own model count ("The X is the adaptation ... of <link>",
    "It's the adaptation of <link>", "The X is the <link> adapted for ...");
    "has been adapted for ... - see Y" (this page is the donor), sentences about
    a prototype, and links to categories are not donors.
    """
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    body = soup.select_one("#bodyContent") or soup
    for node in body.find_all(["p", "li"]):
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", _text_with_links(node)):
            if re.search(r"\bprototype\b", sentence, re.IGNORECASE):
                continue
            m = _ADAPTED_FOR_RE.search(sentence)
            if m and _is_own_subject(m.group("subj"), model) and not _NOT_A_MODEL_PAGE.search(m.group("slug")):
                return {"title": m.group("slug").replace("_", " "), "revision": 1}
            m = _ADAPTATION_RE.search(sentence)
            if not m or not _is_own_subject(m.group("subj"), model):
                continue
            of = re.search(r"\bof\b", m.group("rest"))
            if not of:
                continue
            after = m.group("rest")[of.end():]
            for link in _LINK_RE.finditer(after):
                slug = link.group("slug")
                if not slug or _NOT_A_MODEL_PAGE.search(slug):
                    continue
                revs = revision_numbers(_LINK_RE.sub(" ", after[:link.start()]))
                return {"title": slug.replace("_", " "), "revision": min(revs) if len(revs) == 1 else 1}
    return None


def fill_from_donors(
    records: list[dict[str, Any]],
    load: Callable[[str], list[dict[str, Any]] | None],
    *,
    max_depth: int = 5,
) -> int:
    """Fill each adaptation's blanks from its donor's record (in place).

    A field the adaptation lacks is copied, except identity and market fields
    (``scraper.inherit.NEVER_INHERITED``). The slot map is copied as a unit (with its Memory
    Mapper) and only when the adaptation has none. The donor's own blanks are
    filled from *its* donor first (nesting; cycle-safe, depth-limited). Donor
    pages outside ``records`` are fetched with ``load(title)``.
    Returns the number of records that gained data.
    """
    pages: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        pages.setdefault(record.get("msxorg_title"), []).append(record)
    loaded: dict[str, list[dict[str, Any]]] = {}

    def donor_of(record: dict[str, Any]) -> dict[str, Any] | None:
        ref = record.get(ADAPTED_FROM_FIELD)
        if not ref:
            return None
        title = ref.get("title")
        candidates = pages.get(title)
        if candidates is None:
            if title not in loaded:
                loaded[title] = load(title) or []
            candidates = loaded[title]
        if not candidates:
            log.info("[msxorg:adaptation] Donor page %r not available for %s", title, record.get("msxorg_title"))
            return None
        revision = ref.get("revision", 1)
        if revision > 1:
            for candidate in candidates:
                if candidate.get(REVISION_FIELD) == revision:
                    return candidate
        return next((c for c in candidates if not c.get(REVISION_FIELD) and not c.get(LOCALISED_FIELD)), candidates[0])

    done: set[int] = set()
    filled = 0

    def fill(record: dict[str, Any], active: frozenset[int]) -> None:
        nonlocal filled
        if id(record) in done:
            return
        donor = donor_of(record)
        if donor is None or donor is record:
            done.add(id(record))
            return
        if id(donor) not in active and len(active) < max_depth:
            fill(donor, active | {id(record)})
        changed = fill_blanks(record, donor)
        if changed:
            filled += 1
            log.info("[msxorg:adaptation] %s filled from %s", record.get("msxorg_title"), donor.get("msxorg_title"))
        done.add(id(record))

    for record in records:
        fill(record, frozenset())
    return filled


_MODEL_NOTE_RE = re.compile(r"\s*(?:-\s*note\b.*|\(\s*note\b[^)]*\))\s*$", re.IGNORECASE)


def _strip_model_note(name: str) -> str:
    """Drop an editorial note from a Model value ("X - note: ...", "X (note: ...)")."""
    return _MODEL_NOTE_RE.sub("", name).strip() or name


# "CX5M (CX5MA, CX5MC, ... or CX5MU)": a model and the product codes of its localised versions.
_PRODUCT_LIST_RE = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<list>[^()]*(?:,|\bor\b)[^()]*)\)$")
_PRODUCT_CODE_RE = re.compile(r"^\S*\d\S*$")
_OR_RE = re.compile(r"\s+or\s+")
# Alternatives sharing this much of their start are models of one family
# ("CX5MII or CX5MII/128"); otherwise they are two names of one model ("FM-X or MB25150").
_FAMILY_STEM = 3


def split_model_field(model_raw: str) -> tuple[list[str], dict[str, str], list[str]]:
    """``(models, products, other_names)`` named by a specs Model value.

    ``products`` maps each localised product code to the model it localises.

    - ``A / B`` and ``A or B`` of one family: several models (``models``).
    - ``A or X`` otherwise: X is another name of A (``other_names``).
    - ``A (A1, A2 or A3)``: the product codes of A's localised versions (``products``).
    - Editorial notes are dropped ("PX-7(HB) - note: ...").
    """
    models: list[str] = []
    products: dict[str, str] = {}
    other_names: list[str] = []
    for part in model_raw.split(" / "):
        name = _strip_model_note(part.strip())
        m = _PRODUCT_LIST_RE.match(name)
        if m:
            items = [i.strip() for i in re.split(r",|\bor\b", m.group("list")) if i.strip()]
            if len(items) >= 2 and all(_PRODUCT_CODE_RE.match(i) for i in items):
                name = m.group("name").strip()
                for item in items:
                    products.setdefault(item, name)
        alternatives = [name] if "(" in name else [a for a in _OR_RE.split(name) if a]
        first = alternatives[0]
        models.append(first)
        for alt in alternatives[1:]:
            family = len(os.path.commonprefix([first.lower(), alt.lower()])) >= _FAMILY_STEM
            (models if family else other_names).append(alt)
    return models, products, other_names


# A country tag closing a regional page title: "Panasonic CF-2700 (GE)".
_REGIONAL_TAG_RE = re.compile(r"\s*\((?P<tag>[A-Z]{2,3})\)\s*$")


def regional_name(page_title: str, model: str) -> tuple[str, str] | None:
    """(brand, model) for a regional page whose specs table names the base model.

    msx.org gives some regional versions a page of their own titled with a
    country tag while the specs table repeats the base model: the page
    "Panasonic CF-2700 (GE)" says Brand "National", Model "CF-2700". The tagged
    name — with the title's brand, the one the regional version was sold
    under — tells the versions apart. None when the title is not such a
    regional variant of *model*.
    """
    title = page_title.strip()
    m = _REGIONAL_TAG_RE.search(title)
    if not m:
        return None
    base = title[:m.start()]
    if not base.lower().endswith(" " + model.lower()):
        return None
    brand = base[: -len(model)].strip()
    return (brand, f"{model} ({m.group('tag')})") if brand else None



# ── Families ────────────────────────────────────────────────────────────
#
# Which other models a page says belong with its own (scraper/families.py turns
# them into the Series / Rebrand columns). A bare "see X" is not enough — it also
# points at threads, disks, sections and other machines' keyboards — so a link
# counts only after "see" in a sentence that states a localisation / version /
# brand relation, after "sold … as the X", or in a list item under a lead such as
# "This model has been localised for:" ("Germany - see HB-75D").

# Before "see": the sentence says the linked model is a version / localisation / rebrand.
_FAMILY_REL_RE = re.compile(
    r"locali[sz]|adapt(?:ed|ations?)\b"
    r"|\b(?:also|special|specific|other|downgraded|white|rare|first)\s+(?:\w+\s+)?(?:versions?|models?)\b"
    r"|\b(?:european|french|german|spanish|italian|dutch|arabic|japanese|korean|russian|brazilian)\s+versions?\b"
    r"|\bversions?\s+(?:for|aimed)\b|\bsame model was available\b"
    r"|\bunder\s+(?:the|another)\s+(?:\w+\s+)?(?:brand|trademark|name)\b",
    re.IGNORECASE,
)
# The page states the linked model is its own version: the relation is directed.
_FAMILY_DIRECTED_RE = re.compile(r"locali[sz]|adapted\s+for|under\s+(?:the|another)|same model was available|"
                                 r"(?:special|downgraded|white|rare)\s+(?:\w+\s+)?version", re.IGNORECASE)
_FAMILY_EXCLUDE_RE = re.compile(r"\b(?:previous|successor|predecessor|thread|section|below|above)\b|\bdisk\s+\d",
                                re.IGNORECASE)
_FAMILY_LEAD_RE = re.compile(r"locali[sz]|adapted\s+for|versions?\s+for", re.IGNORECASE)
_SEE_RE = re.compile(r"\bsee\b", re.IGNORECASE)
# "was also sold in Italy as the <link>", "released under the <link>"
_SOLD_AS_RE = re.compile(r"\b(?:sold|released|marketed)\b[^.\x01]{0,60}?\b(?:as|under)\s+(?:the\s+)?$", re.IGNORECASE)


def _link_titles(text: str, page_title: str) -> list[str]:
    titles = []
    for m in _LINK_RE.finditer(text):
        slug = m.group("slug")
        title = slug.replace("_", " ").strip()
        if title and not _NOT_A_MODEL_PAGE.search(slug) and title != page_title and title not in titles:
            titles.append(title)
    return titles


def family_links(page: bytes | BeautifulSoup, page_title: str) -> list[dict[str, Any]]:
    """Models the page's text names as versions / localisations / rebrands of its model.

    ``[{"title": page title, "via": "see" | "list" | "sold as", "directed": bool}]``;
    *directed*: the page says the linked model is a version of its own.
    """
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    body = soup.select_one("#bodyContent") or soup
    found: dict[str, dict[str, Any]] = {}

    def add(titles: list[str], via: str, directed: bool) -> None:
        for t in titles:
            found.setdefault(t, {"title": t, "via": via, "directed": directed})

    for node in body.find_all(["p", "li"]):
        if node.find_parent("table") or node.find(["p", "li"]):
            continue
        text = _text_with_links(node)
        if node.name == "li":
            lst = node.find_parent(["ul", "ol"])
            lead_el = lst.find_previous_sibling(["p", "h2", "h3", "h4"]) if lst is not None else None
            lead = lead_el.get_text(" ", strip=True) if lead_el is not None else ""
            see = _SEE_RE.search(text)
            if see and _FAMILY_LEAD_RE.search(lead) and not _FAMILY_EXCLUDE_RE.search(text):
                add(_link_titles(text[see.end():], page_title), "list", directed=True)
                continue
        for sentence in _SENTENCE_SPLIT_RE.split(text):
            if _FAMILY_EXCLUDE_RE.search(sentence):
                continue
            see = _SEE_RE.search(sentence)
            if see and _FAMILY_REL_RE.search(sentence[:see.start()]):
                directed = bool(_FAMILY_DIRECTED_RE.search(sentence[:see.start()]))
                add(_link_titles(sentence[see.end():], page_title), "see", directed)
            for m in _LINK_RE.finditer(sentence):
                if _SOLD_AS_RE.search(sentence[:m.start()]):
                    add(_link_titles(m.group(0), page_title), "sold as", directed=True)
    return list(found.values())


def variant_table_names(page: bytes | BeautifulSoup) -> list[str]:
    """Model names in the page's variant table(s): first column headed "Product" or "Version"."""
    soup = page if isinstance(page, BeautifulSoup) else BeautifulSoup(page, "lxml")
    names: list[str] = []
    for table in soup.find_all("table"):
        grid = _flatten_table(table)
        if not grid or not grid[0] or grid[0][0].strip().lower() not in ("product", "version"):
            continue
        for row in grid[1:]:
            name = re.sub(r"\s+", " ", row[0]).strip() if row else ""
            if name and name not in names:
                names.append(name)
    return names


def _record_from_specs(
    specs: dict[str, str],
    *,
    brand: str,
    model: str,
    standard: str,
    page_title: str,
    sections: BeautifulSoup,
    slot_table: Tag | None,
    slot_page: BeautifulSoup | None,
) -> dict[str, Any]:
    """Build one model record from a (possibly per-variant) specs dict.

    ``sections`` holds the Connections section. The slot map comes from
    ``slot_table`` when one was chosen, else from ``slot_page``'s first slot map.
    """
    result: dict[str, Any] = {
        "manufacturer": brand,
        "model": model,
        "generation": standard,
        "msxorg_title": page_title,
    }

    # Year
    year_raw = specs.get("Year", "")
    if year_raw:
        result["year"] = _parse_year(year_raw)

    # Region ("unreleased" is a market status, not a region)
    region = specs.get("Region", "")
    if region and not _STATUS_ONLY_RE.match(region):
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

    # Engine (chipset)
    chipset = specs.get("Chipset", "")
    if chipset:
        result["engine_raw"] = chipset

    # Keyboard layout
    kb = specs.get("Keyboard layout", "")
    if kb:
        result["keyboard_layout"] = kb

    # A built-in data recorder: Media "cassette tapes" or an Extras item
    # "built-in data recorder" (the Connections section then often says
    # "No Data Recorder connector!" — no socket for an external one).
    extras = [item for item in specs.get("Extras", "").split(",") if not _NEGATION_RE.search(item)]
    if "cassette" in specs.get("Media", "").lower() or any(
            "data recorder" in item.lower() or "cassette" in item.lower() for item in extras):
        result["tape_interface"] = "Yes"

    # Built-in modem named in Extras ("Modem", "built-in modem …", "non-standard modem").
    if modem_from_specs(specs):
        result["modem"] = MODEM_YES

    # Connections section for tape, printer, cartridge slots.
    conn = _parse_connections(sections)
    # Only set if not already found from Media or specs table.
    for k, v in conn.items():
        if k not in result:
            result[k] = v

    # Remove None values.
    result = {k: v for k, v in result.items() if v is not None}

    # Slot map and the Memory Mapper derived from it.
    if slot_table is not None:
        result.update(parse_slotmap_table(slot_table, page_title))
        result["mapper"] = mapper_from_table(slot_table)
    elif slot_page is not None:
        slotmap = parse_slotmap_from_soup(slot_page, page_title)
        if slotmap is not None:
            result.update(slotmap)
        mapper = parse_mapper_from_soup(slot_page, page_title)
        if mapper is not None:
            result["mapper"] = mapper
    return result


def _revision_records(
    ctx: VariantContext,
    base_specs: dict[str, str],
    base_table: Tag | None,
    base: dict[str, Any],
    build: Callable[[dict[str, str], Tag | None], dict[str, Any]],
) -> list[dict[str, Any]]:
    """One record per later revision with its own properties (``M (vN)``).

    Each starts as a copy of the base record and is overridden by every value
    marked for that revision; the msx.org link (``msxorg_title``) is shared.
    See .claude/artifacts/planning/2026-09-26-model-revisions-design.md.
    """
    records = []
    for n in revisions_in(ctx):
        override_specs, override_table = resolve_specs(ctx, revision=n, override=True)
        if not override_specs and override_table is None:
            continue
        parsed = build({**base_specs, **override_specs}, override_table or base_table)
        record = {**base, **parsed, "model": revision_name(base["model"], n), REVISION_FIELD: n}
        if all(record.get(k) == base.get(k) for k in record if k not in ("model", REVISION_FIELD)):
            continue  # nothing of this revision differs from the base
        log.info("[msxorg:revision] %s: revision %d emitted as %r", base["msxorg_title"], n, record["model"])
        records.append(record)
    return records


def _localised_records(
    soup: BeautifulSoup,
    specs: dict[str, str],
    model_names: list[str],
    products: dict[str, str],
    model_specs: Callable[[str], tuple[dict[str, str], Tag | None]],
    build: Callable[..., dict[str, Any]],
    page_title: str,
) -> list[dict[str, Any]]:
    """One record per localised product of the page's models ("CX5MU" of "CX5M").

    Products come from the Model field's list and from the per-product table
    (first column "Product"); a table-only product localises the longest model
    name it starts with. Each record is its model's, with the values that name
    the product and its table row (Region, Keyboard, VDP) on top. The merge
    keeps it only when openMSX has that machine (``LOCALISED_FIELD``).
    """
    found = dict(products)
    for name in product_names(soup):
        if name in model_names or name in found:
            continue
        prefixed = [m for m in model_names if name.upper().startswith(m.upper())]
        found[name] = max(prefixed, key=len) if prefixed else model_names[0]
    variants = model_names + [p for p in found if p not in model_names]
    records = []
    for product, base in found.items():
        base_specs, table = model_specs(base)
        record = build(localised_specs(specs, soup, base_specs, product, variants), table, product)
        record[LOCALISED_FIELD] = base
        records.append(record)
    if records:
        log.info("[msxorg:localised] %s: %d localised product(s) %s", page_title, len(records), list(found))
    return records


def parse_model_page(
    html: bytes,
    standard: str,
    page_title: str,
    *,
    series_loader: Callable[[str], bytes | None] | None = None,
) -> list[dict[str, Any]]:
    """Parse a single model wiki page.

    Returns a list of model dicts (one per variant when the Model field
    contains " / ", plus one per later revision — ``M (v2)`` — when the page
    describes revision-specific properties).  Returns an empty list if no specs
    table is found.

    A member page without its own specs table that defers to a series page
    ("see HB-75 series for the technical details") is parsed from that series
    page for its own variant; ``series_loader(slug)`` returns the series HTML.
    See scraper/msxorg_series.py and scraper/revisions.py.
    """
    soup = BeautifulSoup(html, "lxml")
    specs = _find_specs_table(soup)
    ctx: VariantContext | None = None
    sections = soup              # page holding Connections
    slot_table: Tag | None = None
    slot_page: BeautifulSoup | None = soup
    series = None
    if not specs:
        series = series_slug(soup)
        series_html = series_loader(series) if series and series_loader else None
        if series_html:
            series_soup = BeautifulSoup(series_html, "lxml")
            ctx = series_context(series_soup, page_title)
            if ctx is not None:
                specs, slot_table = resolve_specs(ctx, page_title=page_title)
                sections, slot_page = series_soup, None
                log.info("[msxorg:series] %s parsed from series %s", page_title, series)
    if not specs:
        if series:
            log.warning("No specs table on %s and series %s unavailable — skipped", page_title, series)
        else:
            log.warning("No specs table found on %s — skipped", page_title)
        return []

    brand = specs.get("Brand", "").strip()
    model_raw = specs.get("Model", "").strip()
    if not model_raw:
        log.warning("No Model field in specs table on %s — skipped", page_title)
        return []

    # Clean up brand: "Philips (Manufacturer: Sanyo)" → "Philips"
    brand = re.sub(r"\s*\(.*?\)\s*", "", brand).strip()

    # Several models ("AX-350II / AX-350IIF", "CX5MII or CX5MII/128"), localised
    # product codes ("CX5M (CX5MA, ... or CX5MU)") and other names ("FM-X or
    # MB25150") in the Model field; editorial notes dropped.
    model_names, products, other_names = split_model_field(model_raw)
    first_raw = model_raw.split(" / ")[0].strip()
    renamed = model_names[0] != first_raw
    own_page = ctx is None

    # A page with its own specs that describes revisions: the base record takes
    # the 1st-revision values of the fields that mention revisions, and the
    # 1st-revision slot map.
    if ctx is None and len(model_names) == 1:
        page = page_context(soup, specs, brand, model_names[0], model_names)
        if revisions_in(page):
            ctx = page
            base_specs, slot_table = resolve_specs(ctx, page_title=page_title)
            specs = {k: base_specs[k] if revision_numbers(v) else v
                     for k, v in specs.items() if not revision_numbers(v) or k in base_specs}
            slot_page = None if slot_table is not None else soup

    # A regional page ("Panasonic CF-2700 (GE)") is named after its title.
    name_brand, name_model = brand, model_names[0]
    regional = regional_name(page_title, model_names[0]) if len(model_names) == 1 else None
    if regional:
        name_brand, name_model = regional
        log.info("[msxorg:regional] %s named %s %s", page_title, name_brand, name_model)

    def build(spec: dict[str, str], table: Tag | None, model: str = name_model) -> dict[str, Any]:
        return _record_from_specs(spec, brand=name_brand, model=model, standard=standard, page_title=page_title,
                                  sections=sections, slot_table=table, slot_page=None if table else slot_page)

    # Several models on the page's own specs: each takes the values that name it
    # and its own slot map; a series page was already resolved for this member.
    multi = own_page and len(model_names) > 1

    def model_specs(model: str) -> tuple[dict[str, str], Tag | None]:
        if not multi:
            return specs, slot_table
        spec = named_specs(specs, model, model_names)
        return spec, choose_slotmap_table(soup, model, model_names, spec.get("RAM", ""))

    records: list[dict[str, Any]] = []
    for model in model_names:
        spec, table = model_specs(model)
        records.append(build(spec, table, model) if model != model_names[0] else build(spec, table))
    result = records[0]
    if renamed:
        result[FORMER_MODEL_FIELD] = first_raw
    aliases = known_as_names(soup, model_names[0], brand) + [n for n in other_names]
    if aliases:
        result[KNOWN_AS_FIELD] = list(dict.fromkeys(aliases))
    donor = adapted_from(soup, model_names[0], brand)
    if donor:
        result[ADAPTED_FROM_FIELD] = donor
    for record in records[1:]:
        for field in (KNOWN_AS_FIELD, ADAPTED_FROM_FIELD):
            if field in result:
                record[field] = result[field]
    if len(records) > 1:
        log.info("[msxorg:split] Split %d variants from %s | models=%s", len(records), page_title, model_names)
    if ctx is not None and len(model_names) == 1:
        records += _revision_records(ctx, specs, slot_table, result, build)
    if own_page:
        records += _localised_records(soup, specs, model_names, products, model_specs, build, page_title)
    names = model_names + (result.get(KNOWN_AS_FIELD) or [])
    status = market_status(soup, specs, names, brand)
    if status:
        for record in records:
            record["market_status"] = status
    if modem_in_description(soup, names, brand):
        for record in records:
            record["modem"] = MODEM_YES
    # Family relations (scraper/families.py): the series page this page defers to,
    # the models its text names as versions / rebrands, its variant table.
    links = family_links(soup, page_title)
    variants = variant_table_names(soup)
    for record in records:
        if series:
            record[SERIES_FIELD] = series
        if links:
            record[FAMILY_LINKS_FIELD] = links
        if variants:
            record[VARIANT_NAMES_FIELD] = variants
    return records


# ── Main entry point ─────────────────────────────────────────────────


def fetch_all(
    session: requests.Session | None = None,
    *,
    source: PageSource | None = None,
    delay: float = 0.5,
    limit: int | None = None,
    exclude_list: ExcludeList | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse all msx.org model pages. Returns list of model dicts.

    If *source* is provided it is used directly (e.g. ``MirrorPageSource``).
    Otherwise a ``LivePageSource`` backed by *session* is created.
    """
    if source is None:
        if session is None:
            session = requests.Session()
        session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        source = LivePageSource(session)

    pages = list_model_pages(source, delay=delay)
    if limit:
        pages = pages[:limit]

    models: list[dict[str, Any]] = []
    excluded = 0
    skipped = 0
    errors = 0

    # Series pages (Category:<Series>) shared by several member pages: fetched
    # through the same source, once per run.
    series_cache: dict[str, bytes | None] = {}

    def load_series(slug: str) -> bytes | None:
        if slug not in series_cache:
            series_cache[slug] = source.fetch_page(
                f"Category:{slug.replace('_', ' ')}", WIKI_URL + "Category:" + quote(slug, safe="/"),
            )
        return series_cache[slug]

    for i, page in enumerate(pages):
        title = page["title"]
        url = page["url"]
        standard = page["standard"]

        # Pre-fetch filename exclude: skip before attempting the mirror read so
        # no "Mirror file not found" warning is emitted for intentionally
        # excluded pages.
        if exclude_list:
            filename = slug_to_filename(url)
            if exclude_list.is_excluded_by_filename(filename):
                log.debug(
                    "[exclude:skip] Excluded by filename | filename=%s source=msxorg",
                    filename,
                )
                excluded += 1
                continue

        content = source.fetch_page(title, url)
        if content is None:
            errors += 1
            continue
        try:
            parsed = parse_model_page(content, standard, title, series_loader=load_series)
            if parsed:
                for result in parsed:
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
            log.exception("Error parsing %s", title)
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

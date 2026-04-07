"""Page source abstraction for the msx.org scraper.

Provides a protocol (PageSource) and two implementations:
  LivePageSource  — fetches pages via HTTP from the live msx.org site.
  MirrorPageSource — reads pages from a local directory of browser-saved
                     HTML files (browser Save-As, HTML Only format).

Filename convention (MirrorPageSource):
  URL slug (e.g. ``Sony_HB-F9S``, ``Category:MSX2_Computers``) is mapped to
  a filename by:
    1. URL-decoding percent-encoded characters (``%2B`` → ``+``)
    2. Replacing underscores with spaces
    3. Replacing colons with underscores (Windows forbids colons in filenames)
    4. Appending `` - MSX Wiki.html``

  Examples:
    ``Sony_HB-F9S``            → ``Sony HB-F9S - MSX Wiki.html``
    ``Category:MSX2_Computers`` → ``Category_MSX2 Computers - MSX Wiki.html``
    ``CIEL_Expert_2%2B_Turbo`` → ``CIEL Expert 2+ Turbo - MSX Wiki.html``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote

import requests

log = logging.getLogger(__name__)


class PageSource(Protocol):
    """Abstract source of msx.org wiki HTML pages."""

    def fetch_category(self, standard: str, url: str) -> bytes | None:
        """Return raw HTML bytes for a category listing page, or None on failure."""
        ...

    def fetch_page(self, title: str, url: str) -> bytes | None:
        """Return raw HTML bytes for a model wiki page, or None on failure."""
        ...


class LivePageSource:
    """Fetches pages from the live msx.org website via HTTP."""

    def __init__(self, session: requests.Session) -> None:
        self._session = session

    def fetch_category(self, standard: str, url: str) -> bytes | None:
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception:
            log.exception(
                "Failed to fetch category page for %s (%s) — skipping", standard, url
            )
            return None

    def fetch_page(self, title: str, url: str) -> bytes | None:
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception:
            log.exception("Failed to fetch model page for %s (%s)", title, url)
            return None


def _slug_to_filename(url: str) -> str:
    """Derive the browser Save-As filename from a msx.org wiki URL.

    Extracts the wiki slug from the URL, applies the naming convention, and
    returns the expected filename (without directory prefix).
    """
    # Extract slug after /wiki/
    slug = url.split("/wiki/", 1)[-1] if "/wiki/" in url else url
    # URL-decode percent-encoded chars, then underscores → spaces
    title = unquote(slug).replace("_", " ")
    # Colons are illegal in Windows filenames → replace with underscore
    safe_title = title.replace(":", "_")
    return f"{safe_title} - MSX Wiki.html"


class MirrorPageSource:
    """Reads pages from a local directory of browser-saved HTML files.

    The directory must contain files saved via browser Save-As (HTML Only).
    Files are looked up by name using the wiki URL slug → filename convention
    described in the module docstring.

    If the mirror directory does not exist, all fetches return None and an
    ERROR is logged once at construction time.
    """

    def __init__(self, mirror_dir: Path) -> None:
        self._dir = mirror_dir
        if not mirror_dir.exists():
            log.error(
                "Mirror directory not found: %s — msx.org data will be empty",
                mirror_dir,
            )

    def _read(self, filename: str, label: str) -> bytes | None:
        if not self._dir.exists():
            return None
        path = self._dir / filename
        if not path.exists():
            log.warning("Mirror file not found for %s: %s", label, path)
            return None
        return path.read_bytes()

    def fetch_category(self, standard: str, url: str) -> bytes | None:
        filename = _slug_to_filename(url)
        return self._read(filename, f"category {standard!r}")

    def fetch_page(self, title: str, url: str) -> bytes | None:
        filename = _slug_to_filename(url)
        return self._read(filename, f"model {title!r}")

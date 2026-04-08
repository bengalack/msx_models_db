"""XML source abstraction for the openMSX scraper.

Provides a protocol (XMLSource) and three implementations:
  LiveXMLSource     — fetches machine XML files from the openMSX GitHub repository.
  MirrorXMLSource   — reads machine XML files from a local directory of .xml files.
  FallbackXMLSource — tries live first; falls back to the mirror on any failure.

Filename convention (MirrorXMLSource):
  Files must be named exactly as in the openMSX repository (e.g. Sony_HB-F9S.xml).
  The openMSX share/machines directory can be used directly as a mirror.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import requests

from .exclude import ExcludeList
from .http import fetch_with_retry

log = logging.getLogger(__name__)

GITHUB_API_URL = (
    "https://api.github.com/repos/openMSX/openMSX/contents/share/machines"
)

# Files / prefixes to skip (test rigs, boosted configs, WIP).
SKIP_PREFIXES = ("Acid", "Boosted_", "WIP_", "ColecoVision", "Sega_")


class XMLSource(Protocol):
    """Abstract source of openMSX machine XML files."""

    def list_files(self, exclude_list: ExcludeList | None = None) -> list[str]:
        """Return list of machine XML filenames (e.g. 'Sony_HB-F9S.xml')."""
        ...

    def fetch_file(self, name: str) -> bytes | None:
        """Return XML bytes for the given filename, or None on failure."""
        ...


class LiveXMLSource:
    """Fetches machine XML files from the openMSX GitHub repository."""

    def __init__(self, session: requests.Session) -> None:
        self._session = session
        self._url_map: dict[str, str] = {}  # name → download_url, populated by list_files

    def list_files(self, exclude_list: ExcludeList | None = None) -> list[str]:
        resp = fetch_with_retry(self._session, GITHUB_API_URL)
        names: list[str] = []
        for item in resp.json():
            name: str = item["name"]
            if item["type"] != "file" or not name.endswith(".xml"):
                continue
            if any(name.startswith(p) for p in SKIP_PREFIXES):
                continue
            if exclude_list and exclude_list.is_excluded_by_filename(name):
                log.debug("[exclude:skip] Excluded filename | filename=%s", name)
                continue
            self._url_map[name] = item["download_url"]
            names.append(name)
        return names

    def fetch_file(self, name: str) -> bytes | None:
        url = self._url_map.get(name)
        if url is None:
            log.warning("No download URL cached for %s — was list_files called?", name)
            return None
        try:
            resp = fetch_with_retry(self._session, url)
            return resp.content
        except Exception:
            log.exception("Failed to fetch %s from GitHub", name)
            return None


class MirrorXMLSource:
    """Reads machine XML files from a local directory.

    Files must be named exactly as in the openMSX repository (e.g. Sony_HB-F9S.xml).
    The openMSX share/machines directory can be used directly as a mirror.

    If the mirror directory does not exist, list_files returns [] and all
    fetch_file calls return None; an ERROR is logged once at construction time.
    """

    def __init__(self, mirror_dir: Path) -> None:
        self._dir = mirror_dir
        if not mirror_dir.exists():
            log.error(
                "Mirror directory not found: %s — openMSX data will be empty",
                mirror_dir,
            )

    def list_files(self, exclude_list: ExcludeList | None = None) -> list[str]:
        if not self._dir.exists():
            return []
        names: list[str] = []
        for path in sorted(self._dir.glob("*.xml")):
            name = path.name
            if any(name.startswith(p) for p in SKIP_PREFIXES):
                continue
            if exclude_list and exclude_list.is_excluded_by_filename(name):
                log.debug("[exclude:skip] Excluded filename | filename=%s", name)
                continue
            names.append(name)
        log.info(
            "[mirror:mode] Using local openMSX mirror | path=%s | files=%d",
            self._dir, len(names),
        )
        return names

    def fetch_file(self, name: str) -> bytes | None:
        if not self._dir.exists():
            return None
        path = self._dir / name
        if not path.exists():
            log.warning("Mirror file not found: %s", path)
            return None
        return path.read_bytes()


class FallbackXMLSource:
    """Try live GitHub first; on any failure fall back to the local mirror.

    Use this when GitHub may be inaccessible but local files are available.
    """

    def __init__(self, live: LiveXMLSource, mirror: MirrorXMLSource) -> None:
        self._live = live
        self._mirror = mirror

    def list_files(self, exclude_list: ExcludeList | None = None) -> list[str]:
        try:
            return self._live.list_files(exclude_list)
        except Exception:
            log.exception(
                "Failed to list openMSX files from GitHub — falling back to mirror"
            )
            return self._mirror.list_files(exclude_list)

    def fetch_file(self, name: str) -> bytes | None:
        content = self._live.fetch_file(name)
        if content is not None:
            return content
        log.info("Live fetch failed for %s — falling back to mirror", name)
        return self._mirror.fetch_file(name)

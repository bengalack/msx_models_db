"""Tests for scraper/chip_links.py (data/chip-links.json)."""
from __future__ import annotations

import json

import pytest

from scraper.chip_links import CHIP_LINKS_PATH, load_chip_links
from scraper.columns import active_columns


def _write(tmp_path, raw) -> object:
    path = tmp_path / "chip-links.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_loads_links(tmp_path):
    path = _write(tmp_path, {"_comment": "x", "links": {"X1": "https://example.org/X1"}})
    assert load_chip_links(path) == {"X1": "https://example.org/X1"}


def test_missing_file_means_no_links(tmp_path):
    assert load_chip_links(tmp_path / "absent.json") == {}


def test_links_are_optional(tmp_path):
    assert load_chip_links(_write(tmp_path, {"_comment": "x"})) == {}


@pytest.mark.parametrize("raw", [
    [],                                          # not an object
    {"links": []},                               # links not an object
    {"links": {"X1": 42}},                       # URL not a string
    {"links": {"X1": "http://example.org/X1"}},  # not https
    {"links": {" ": "https://example.org/"}},    # empty chip id
])
def test_malformed_raises(tmp_path, raw):
    with pytest.raises(ValueError):
        load_chip_links(_write(tmp_path, raw))


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "chip-links.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_chip_links(path)


def test_committed_file_loads_and_is_used():
    assert CHIP_LINKS_PATH.exists()
    assert load_chip_links(), "the committed file ships chip links"
    assert any(c.chip_links for c in active_columns())

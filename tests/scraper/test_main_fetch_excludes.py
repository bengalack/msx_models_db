"""The standalone fetch-* CLI commands must honour data/exclude.json, like build --fetch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scraper import __main__ as cli
from scraper import build as build_module


@pytest.fixture
def exclude_file(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "exclude.json"
    path.write_text(json.dumps([{"manufacturer": "Acme", "model": "X-1"}]))
    monkeypatch.setattr(build_module, "EXCLUDE_PATH", path)
    return path


def _args(tmp_path: Path, **extra) -> argparse.Namespace:
    return argparse.Namespace(output=str(tmp_path / "out.json"), limit=None, delay=0.0, **extra)


def _captured_exclude_list(fetch_all_mock):
    fetch_all_mock.assert_called_once()
    return fetch_all_mock.call_args.kwargs.get("exclude_list")


def test_fetch_msxorg_passes_exclude_list(tmp_path, exclude_file):
    args = _args(tmp_path, msxorg_mirror=None, local_msxorg_only=False)
    with patch.object(build_module, "load_scraper_config", return_value={}), \
         patch.object(cli.msxorg, "fetch_all", return_value=[]) as fetch_all:
        cli.cmd_fetch_msxorg(args)
    exclude_list = _captured_exclude_list(fetch_all)
    assert exclude_list is not None
    assert exclude_list.is_excluded("Acme", "X-1")


def test_fetch_openmsx_passes_exclude_list(tmp_path, exclude_file):
    args = _args(tmp_path, openmsx_mirror=None, local_openmsx_only=False)
    with patch.object(build_module, "load_scraper_config", return_value={}), \
         patch.object(cli.openmsx, "fetch_all", return_value=[]) as fetch_all:
        cli.cmd_fetch_openmsx(args)
    exclude_list = _captured_exclude_list(fetch_all)
    assert exclude_list is not None
    assert exclude_list.is_excluded("Acme", "X-1")


def test_fetch_msxorg_malformed_exclude_file_fails_before_fetching(tmp_path, exclude_file):
    """Same fail-fast contract as build: bad exclude.json aborts before any network I/O."""
    exclude_file.write_text("not json")
    args = _args(tmp_path, msxorg_mirror=None, local_msxorg_only=False)
    with patch.object(build_module, "load_scraper_config", return_value={}), \
         patch.object(cli.msxorg, "fetch_all", return_value=[]) as fetch_all, \
         pytest.raises(ValueError):
        cli.cmd_fetch_msxorg(args)
    fetch_all.assert_not_called()

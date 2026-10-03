"""Tests for scraper/market_status.py (openMSX description rule, ranking)."""
from __future__ import annotations

import pytest

from scraper.market_status import (
    MARKET_RARE,
    MERGE_PRECEDENCE,
    MARKET_UNRELEASED,
    status_from_description,
    merged_status,
)
from scraper.merge import merge_models


@pytest.mark.parametrize("description,expected", [
    ("Rare MSX that was never mass produced as the company had to close.", MARKET_RARE),
    ("An extremely rare Russian version of the F9P.", MARKET_RARE),
    ("Rare Japanese MSX2 with stereo PSG.", MARKET_RARE),
    ("This machine is very rare.", MARKET_RARE),
    ("Prototype MSX?", MARKET_UNRELEASED),
    ("A prototype of a CD-ROM MSX.", MARKET_UNRELEASED),
    ("An MSX2 that was never released.", MARKET_UNRELEASED),
    ("The last officially released MSX machine. With built in disk drive.", None),
    ("First MSX2 released by the company, with software built in.", None),
    ("A 64kB MSX1 with a numeric keypad (rare for a MSX1).", None),
    ("", None),
    (None, None),
])
def test_status_from_description(description, expected):
    assert status_from_description(description) == expected


def test_merged_status_follows_the_rank():
    strong, weak = MERGE_PRECEDENCE[0], MERGE_PRECEDENCE[-1]
    assert merged_status(weak, strong) == strong
    assert merged_status(strong, weak) == strong
    assert merged_status(None, weak) == weak
    assert merged_status(None, None) is None


@pytest.mark.parametrize("o_value,m_value", [
    (MARKET_RARE, MARKET_UNRELEASED),
    (MARKET_UNRELEASED, MARKET_RARE),
])
def test_merge_keeps_the_merged_status(o_value, m_value):
    openmsx = [{"brand": "Maker", "model": "M-1", "market_status": o_value}]
    msxorg = [{"brand": "Maker", "model": "M-1", "market_status": m_value}]
    [row] = merge_models(openmsx, msxorg)
    assert row["market_status"] == MARKET_RARE


@pytest.mark.parametrize("o_value,m_value", [(None, MARKET_UNRELEASED), (MARKET_UNRELEASED, None)])
def test_a_silent_source_keeps_the_other_status(o_value, m_value):
    openmsx = [{"brand": "Maker", "model": "M-1", "market_status": o_value}]
    msxorg = [{"brand": "Maker", "model": "M-1", "market_status": m_value}]
    [row] = merge_models(openmsx, msxorg)
    assert row["market_status"] == MARKET_UNRELEASED


def test_openmsx_description_sets_market_status():
    from scraper.openmsx import parse_machine_xml
    xml = (b"<machine><info><manufacturer>Maker</manufacturer><code>M-1</code><type>MSX</type>"
           b"<description>Rare MSX that was never mass produced.</description></info><devices/></machine>")
    assert parse_machine_xml(xml, "Maker_M-1.xml")["market_status"] == MARKET_RARE

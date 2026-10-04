"""Tests for the PSG Chip column (scraper/psg.py).

The engine / chip table is built here (inline), so editing data/psg-chips.json
never breaks these tests; the real file is only checked for consistency.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.psg import load_psg_chips, psg_chip

TABLE = {
    "engines": {
        "HD62003": {"psg": "AY-3-8910 comp.", "note": "HD62003: PSG AY-3-8910 compatible"},
        "S3527": {"psg": "YM2149", "note": "S3527: YM2149"},
        "S1985": {"psg": "YM2149", "note": "S1985: YM2149"},
        "T7937A": {"psg": "AY-3-8910 comp.", "note": "T7937A: T7766A"},
        "T9769": {"psg": "AY-3-8910 comp.", "note": "T9769: T7766A"},
        "T7775": {"psg": None, "note": "T7775: no sound chip"},
    },
    "chips": {
        "AY-?3-?8910A": "AY-3-8910A", "AY-?3-?8910": "AY-3-8910", "AY-?3-?8912": "AY-3-8912",
        "YM[- ]?2149F": "YM2149F", "YM[- ]?2149": "YM2149", "T7766A": "T7766A",
        "KC89C72": "KC89C72", "OY-2-8910AC": "OY-2-8910AC",
    },
}


def cell(audio=None, engine=None, psg_type=None, model="MX-1"):
    record = {"brand": "Maker", "model": model}
    if audio is not None:
        record["audio_raw"] = audio
    if engine is not None:
        record["engine_raw"] = engine
    if psg_type is not None:
        record["psg_type"] = psg_type
    return psg_chip(record, TABLE)


@pytest.mark.parametrize("audio,engine,expected", [
    # a plain chip, in its spellings
    ("PSG (AY-3-8910)", None, "AY-3-8910"),
    ("PSG (AY-3-8910A)", None, "AY-3-8910A"),
    ("PSG (YM-2149)", None, "YM2149"),
    ("PSG ( Yamaha YM2149 )", None, "YM2149"),
    ("PSG (YM2149F)", None, "YM2149F"),
    ("PSG (File KC89C72)", None, "KC89C72"),
    ("AY-3-8912 PSG (Shared resource with SVI-838)", None, "AY-3-8912"),
    # a chip in a named engine: the engine's PSG from the table
    ("PSG (YM2149 integrated in MSX-Engine S3527)", "Yamaha S3527", "YM2149 in S3527"),
    ("PSG (custom chip integrated in MSX-Engine S3527)", "Yamaha S3527", "YM2149 in S3527"),
    ("PSG (integrated into MSX-Engine S3527), (AX-200M version) SFG , MIDI", "Yamaha S3527", "YM2149 in S3527"),
    ("PSG -sound chip General Instrument AY-3-8910 compatible (Integrated in MSX-Engine T7937A)", "Toshiba T7937A",
     "AY-3-8910 comp. in T7937A"),
    ("PSG (AY-3-8910 compatible, integrated in MSX-Engine T9769x)", None, "AY-3-8910 comp. in T9769"),
    ("PSG (YM2149 integrated in MSX-Engine S1985 or S3527)", None, "YM2149 in S1985 or S3527"),
    # an engine the table does not know keeps the page's chip
    ("PSG (AY-3-8910 compatible, integrated in MSX-Engine T9763)", None, "AY-3-8910 comp. in T9763"),
    # "in MSX Engine" without a name: the model's Engine column
    ("PSG (AY-3-8910 in MSX Engine)", "Hitachi HD62003", "AY-3-8910 comp. in HD62003"),
    ("PSG (YM2149 integrated in MSX-Engine)", "Yamaha S1985", "YM2149 in S1985"),
    # plain "PSG" with an engine: the engine's PSG
    ("PSG , MSX-MUSIC", "Toshiba T9769 model A or B", "AY-3-8910 comp. in T9769"),
    # a named chip that agrees with the engine gets it; one that contradicts it wins
    ("PSG (AY-3-8910 compatible), MSX-MUSIC", "Toshiba T9769", "AY-3-8910 comp. in T9769"),
    ("PSG (AY-3-8910)", "Yamaha S3527", "AY-3-8910"),
    # an engine without a sound chip is ignored
    ("PSG (AY-3-8910 or T7766A)", "Toshiba T7775", "AY-3-8910 or T7766A"),
    # uncertainty
    ("PSG (?AY-3-8910)", None, "AY-3-8910?"),
    ("PSG (probably AY-3-8910 or T7766A)", "probably Toshiba T7775", "AY-3-8910? or T7766A?"),
    ("PSG (probably YM2149 integrated in MSX-Engine S3527)", "Yamaha S3527", "YM2149? in S3527"),
    ("PSG (YM2149 integrated in MSX-Engine?)", "?", "YM2149?"),
    ("PSG (AY-3-8910A in the MSX-Engine?)", "?", "AY-3-8910A?"),
    # alternatives
    ("PSG (YM2149 or AY-3-8910)", None, "YM2149 or AY-3-8910"),
    ("PSG clone (1st version: OY-2-8910AC, 2nd version: File KC89C72)", None, "OY-2-8910AC or KC89C72"),
])
def test_msxorg_text(audio, engine, expected):
    value, tooltip = cell(audio, engine)
    assert value == expected
    assert tooltip.startswith("msx.org: ")


@pytest.mark.parametrize("model,expected", [
    ("VG-8020", "YM2149"),                  # the main model is the /00 version
    ("VG-8020/00", "YM2149"),
    ("VG-8020/29", "YM2149 in S3527"),
    ("VG-8020/40", "YM2149 in S3527"),
])
def test_versions_take_their_own_part(model, expected):
    audio = "PSG (YM2149 in /00 version, custom chip integrated in MSX-Engine S3527 for /19, /20, /29 and /40 versions)"
    engine = "none (separate IC's) for /00 version, Yamaha S3527 for /19, /20, /29 and /40 versions"
    assert cell(audio, engine, model=model)[0] == expected


def test_engine_note_in_the_tooltip():
    value, tooltip = cell("PSG (AY-3-8910 in MSX Engine)", "Hitachi HD62003")
    assert tooltip == "msx.org: PSG (AY-3-8910 in MSX Engine). " + TABLE["engines"]["HD62003"]["note"]


@pytest.mark.parametrize("psg_type,engine,expected", [
    ("YM2149", None, "YM2149"),
    ("AY8910", None, "AY-3-8910"),
    ("default", None, "AY-3-8910"),                   # no <type>: openMSX's default
    ("YM2149", "Yamaha S1985", "YM2149 in S1985"),    # with the model's engine
    ("AY8910", "Toshiba T7775", "AY-3-8910"),
])
def test_openmsx_when_msxorg_names_no_chip(psg_type, engine, expected):
    value, tooltip = cell(None if engine else "PSG", engine, psg_type)
    assert value == expected
    assert tooltip.startswith("openMSX: ")


@pytest.mark.parametrize("audio,engine", [("Emulated PSG , MSX-MUSIC and SCC by FPGA", "FPGA"),
                                          ("Emulated PSG , MSX-MUSIC and SCC by FPGA", None),
                                          (None, "FPGA")])
def test_fpga_machines_say_fpga(audio, engine):
    value, tooltip = cell(audio, engine)
    assert value == "FPGA"
    assert tooltip.startswith("msx.org")


@pytest.mark.parametrize("audio", [None, "PSG", "PSG (from the MSX1 host)"])
def test_no_source_names_a_chip_means_blank(audio):
    assert cell(audio) == (None, None)


def test_a_page_saying_no_psg_means_none():
    record = {"brand": "Maker", "model": "MX-1", "audio_raw": "Yamaha YM2203C a.k.a. OPN (FM Operator Type-N)",
              "psg_absent": "The sound is not provided by the classical PSG, but by an OPN chip."}
    assert psg_chip(record, TABLE) == ("None", "msx.org: " + record["psg_absent"])


def test_no_psg_sentence_does_not_override_a_named_chip():
    record = {"brand": "Maker", "model": "MX-1", "audio_raw": "PSG (AY-3-8910)", "psg_absent": "No PSG here."}
    assert psg_chip(record, TABLE)[0] == "AY-3-8910"


def test_plain_psg_with_an_engine_is_msxorg_data():
    """msx.org's Engine field names the PSG's engine: openMSX's type is not needed."""
    value, tooltip = cell("PSG", "Yamaha S1985", "AY8910")
    assert value == "YM2149 in S1985" and tooltip.startswith("msx.org: PSG. ")


def test_msxorg_wins_over_openmsx():
    assert cell("PSG (AY-3-8910A)", None, "YM2149")[0] == "AY-3-8910A"


def test_real_table_is_consistent():
    """Every engine entry names its PSG or null; every chip regex compiles; linked names have a page."""
    import re
    table = load_psg_chips()
    links = json.loads(Path("data/chip-links.json").read_text(encoding="utf-8"))["links"]
    for engine, entry in table["engines"].items():
        assert entry["psg"] is None or isinstance(entry["psg"], str), engine
        assert entry.get("note"), engine
    for rx in table["chips"]:
        re.compile(rx)
    for name in table["engines"]:
        assert name in links, f"engine {name} has no chip link"

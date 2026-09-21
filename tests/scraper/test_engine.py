"""Tests for scraper/engine.py — splitting the scraped Engine text into two ASIC columns.

Rule-by-rule cases use their own inline sources; the end-to-end expectations come
from tests/scraper/fixtures/engine_expected.tsv (the maintainer-approved table),
never from values hardcoded here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.engine import (
    CHIPS_PATH,
    NONE,
    ChipDictionary,
    load_chip_dictionary,
    normalise,
    parse_engine,
)

FIXTURE = Path("tests/scraper/fixtures/engine_expected.tsv")


@pytest.fixture(scope="module")
def chips() -> ChipDictionary:
    return load_chip_dictionary()


def _cases() -> list[tuple[str, str | None, str | None]]:
    rows = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        source, semi, full = line.split("\t")
        rows.append((source, None if semi == "-" else semi, None if full == "-" else full))
    return rows


# ── End-to-end: every live source value ───────────────────────────────────

@pytest.mark.parametrize("source,semi,full", _cases(), ids=lambda v: str(v)[:40])
def test_matches_approved_table(source, semi, full, chips):
    assert parse_engine(source, chips) == (semi, full)


def test_fixture_covers_every_chip_in_the_dictionary(chips):
    """Every chip in the vocabulary is exercised by at least one fixture row."""
    outputs = " ".join(f"{s or ''} {f or ''}" for _, s, f in _cases())
    missing = [c for c in chips.semi_custom + chips.full_custom if c not in outputs]
    assert missing == [], f"chips never produced by the fixture: {missing}"


# ── Normalisation ─────────────────────────────────────────────────────────

class TestNormalise:
    def test_collapses_double_spaces(self):
        assert normalise("Yamaha  S3527") == "Yamaha S3527"

    def test_collapses_line_breaks(self):
        assert normalise("Yamaha\nS3527") == "Yamaha S3527"
        assert normalise("Yamaha\r\n  S3527") == "Yamaha S3527"

    def test_collapses_non_breaking_space(self):
        assert normalise("Yamaha S3527") == "Yamaha S3527"

    def test_tidies_space_before_bracket_and_comma(self):
        assert normalise("MB64H131 )") == "MB64H131)"
        assert normalise("A , B") == "A, B"


# ── Unknown and uncertainty ───────────────────────────────────────────────

class TestUnknownAndUncertainty:
    @pytest.mark.parametrize("source", ["?", "???", "   ", "", "? ? ?"])
    def test_question_marks_are_unknown(self, source, chips):
        assert parse_engine(source, chips) == (None, None)

    def test_none_input_is_unknown(self, chips):
        assert parse_engine(None, chips) == (None, None)

    @pytest.mark.parametrize("word", ["probably", "Probably", "possibly", "POSSIBLY"])
    def test_uncertainty_word_appends_question_mark(self, word, chips):
        semi, full = parse_engine(f"{word} Yamaha S3527", chips)
        assert (semi, full) == (NONE, "S3527?")

    def test_leading_question_mark_is_uncertainty(self, chips):
        semi, full = parse_engine("? Gate array Toshiba TCX-1012", chips)
        assert (semi, full) == ("TCX-1012?", NONE)


# ── Chip identification ───────────────────────────────────────────────────

class TestChipIdentification:
    def test_vendor_name_is_stripped(self, chips):
        assert parse_engine("Yamaha S1985", chips) == (NONE, "S1985")

    def test_semi_and_full_custom_split_into_their_columns(self, chips):
        assert parse_engine("Yamaha S1985 + Sanyo CF77099AFT", chips) == ("CF77099AFT", "S1985")

    def test_explanatory_parenthetical_is_ignored(self, chips):
        """The S3527 mentioned in the aside is not this model's engine."""
        assert parse_engine("Yamaha X3527 (a previous version of the Yamaha S3527)", chips) == (NONE, "X3527")

    def test_unknown_chip_is_reported_not_guessed(self, chips, caplog):
        semi, full = parse_engine("Yamaha Z9999 super engine", chips, context="test|model")
        assert (semi, full) == (None, None)
        assert any("engine:unknown_chip" in r.getMessage() for r in caplog.records)


class TestT9769:
    @pytest.mark.parametrize("source,expected", [
        ("Toshiba T9769", "T9769"),
        ("Toshiba T9769 B", "T9769 (B)"),
        ("Toshiba T9769x (A or B)", "T9769 (A or B)"),
        ("Toshiba T9769 model B or C", "T9769 (B or C)"),
    ])
    def test_letters_move_into_brackets(self, source, expected, chips):
        assert parse_engine(source, chips)[1] == expected

    def test_letter_kept_when_another_chip_follows(self, chips):
        semi, full = parse_engine("Toshiba T9769 C and ASCII S1990 bus controller", chips)
        assert (semi, full) == (NONE, "T9769 (C) and S1990")

    def test_gate_array_goes_to_semi_custom_column(self, chips):
        semi, full = parse_engine("Toshiba T9769 model A or B and gate array Mitsubishi M50014", chips)
        assert (semi, full) == ("M50014", "T9769 (A or B)")


class TestJoining:
    def test_alternatives_use_or(self, chips):
        assert parse_engine("Yamaha S1985 or Yamaha S3527", chips)[1] == "S1985 or S3527"

    def test_same_family_uses_slash(self, chips):
        semi, _ = parse_engine("Gate arrays Toshiba TCX-1008, TCX-2001 and TCX-2002", chips)
        assert semi == "TCX-1008/TCX-2001/TCX-2002"

    def test_different_families_use_and(self, chips):
        semi, _ = parse_engine("MB64H120, uPD65002C022", chips)
        assert semi == "MB64H120 and uPD65002C022"

    def test_source_order_is_kept(self, chips):
        assert parse_engine("Toshiba T7937 or T7937A", chips)[1] == "T7937 or T7937A"


class TestNoneHandling:
    def test_none_fills_both_columns(self, chips):
        assert parse_engine("none (separate IC's)", chips) == (NONE, NONE)

    def test_none_yields_to_a_named_chip(self, chips):
        semi, full = parse_engine("None (separate ICs whose a gate array Fujitsu MB64H131)", chips)
        assert (semi, full) == ("MB64H131", NONE)

    def test_per_version_variants_become_alternatives(self, chips):
        semi, full = parse_engine(
            "none (separate IC's) for /00 version, Yamaha S3527 for /19, /20 and /40 versions", chips
        )
        assert (semi, full) == (NONE, f"{NONE} or S3527")

    def test_understood_source_marks_the_other_column_none(self, chips):
        assert parse_engine("Yamaha YM5214", chips) == ("YM5214", NONE)


class TestUla:
    def test_standard_logic_is_abbreviated(self, chips):
        assert parse_engine("2 ULA and standard logic", chips) == ("2 ULA + std logic", NONE)


# ── Dictionary loading ────────────────────────────────────────────────────

class TestChipDictionary:
    def test_ships_with_a_valid_dictionary(self):
        chips = load_chip_dictionary()
        assert chips.semi_custom and chips.full_custom

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_chip_dictionary(tmp_path / "absent.json")

    def test_invalid_json_raises_value_error(self, tmp_path):
        path = tmp_path / "chips.json"
        path.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            load_chip_dictionary(path)

    def test_chip_in_both_classes_raises(self, tmp_path):
        path = tmp_path / "chips.json"
        path.write_text(json.dumps({"semi_custom": ["X1"], "full_custom": ["X1"]}), encoding="utf-8")
        with pytest.raises(ValueError, match="both semi-custom and full-custom"):
            load_chip_dictionary(path)

    def test_invalid_filler_pattern_raises(self, tmp_path):
        path = tmp_path / "chips.json"
        path.write_text(json.dumps({"semi_custom": ["X1"], "filler": ["[invalid("]}), encoding="utf-8")
        with pytest.raises(ValueError, match="invalid pattern"):
            load_chip_dictionary(path)

    def test_committed_dictionary_classes_do_not_overlap(self):
        raw = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
        assert not set(raw["semi_custom"]) & set(raw["full_custom"])

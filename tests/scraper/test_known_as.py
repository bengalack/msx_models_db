"""Tests for "known as" aliases: msx.org says a model is also known under another name.

"The HX-51 computer, also known as the HX-51I, ..." means msx.org's HX-51 and
openMSX's HX-51I are one machine. The msx.org parser records the name; the
merge uses it only when openMSX has a machine under that name and none under
the msx.org name. Fixtures are inline and owned by the tests.
"""

from __future__ import annotations

import pytest

from scraper.merge import merge_models
from scraper.msxorg import KNOWN_AS_FIELD, known_as_names, parse_model_page


def _page(sentence: str, model: str = "HX-51", brand: str = "Toshiba") -> bytes:
    return (
        '<html><body><div id="bodyContent">'
        '<table class="wikitable">'
        f"<tr><th>Brand</th><td>{brand}</td></tr><tr><th>Model</th><td>{model}</td></tr></table>"
        f"<p>{sentence}</p></div></body></html>"
    ).encode()


# ── Extraction ──────────────────────────────────────────────────────────────

class TestKnownAsNames:
    @pytest.mark.parametrize("sentence,model,expected", [
        ("The HX-51 computer, also known as the HX-51I , has been designed as a very simple MSX1 computer.",
         "HX-51", ["HX-51I"]),
        ("The Toshiba HX-10P, more commonly known simply as the HX-10 as indicated on the machine, is one of the adaptations.",
         "HX-10P", ["HX-10"]),
        ("This model is also known as the Wavy35 .", "PHC-35J", ["Wavy35"]),
        ("This model is also known as ' SPC Super' and was manufactured by Sanyo.", "PHC-SPC", ["SPC Super"]),
    ])
    def test_alias_of_the_pages_own_model(self, sentence, model, expected):
        assert known_as_names(_page(sentence, model), model, "Toshiba") == expected

    @pytest.mark.parametrize("sentence", [
        # another computer is the subject — an adaptation, not an alias
        "The Fenner FPC-900 is the adaptation of the Sanyo MPC-25FD computer, also known as Wavy 25, for Italy.",
        # a revision, not the model
        "the second version (also known as SPC-800A) is less colored and without reset button.",
        # software / chips / companies
        "the multilingual office suite Ease , also known as Philips Desktop, can be used in English.",
        "the V99C37-F Video Display Co-Processor, also known as VCP or Video Control Palette.",
        "This company is also known as Forte II Games.",
    ])
    def test_other_subjects_are_not_aliases(self, sentence):
        assert known_as_names(_page(sentence, "FPC-900"), "FPC-900", "Fenner") == []

    def test_parse_model_page_records_the_names(self):
        page = _page("The HX-51 computer, also known as the HX-51I , has been designed simply.")
        [record] = parse_model_page(page, "MSX1", "Toshiba HX-51")
        assert record[KNOWN_AS_FIELD] == ["HX-51I"]

    def test_no_sentence_no_field(self):
        [record] = parse_model_page(_page("A very simple MSX1 computer."), "MSX1", "Toshiba HX-51")
        assert KNOWN_AS_FIELD not in record


# ── Merge ───────────────────────────────────────────────────────────────────

def _msxorg(model: str, *names: str, **extra) -> dict:
    record = {"manufacturer": "Toshiba", "model": model, "msxorg_title": f"Toshiba {model}", **extra}
    if names:
        record[KNOWN_AS_FIELD] = list(names)
    return record


class TestMergeKnownAs:
    def test_merges_into_the_openmsx_machine_known_by_that_name(self):
        merged = merge_models(
            [{"manufacturer": "Toshiba", "model": "HX-51I", "openmsx_id": "Toshiba_HX-51I"}],
            [_msxorg("HX-51", "HX-51I", year=1985)],
        )
        assert len(merged) == 1
        row = merged[0]
        assert row["model"] == "HX-51I"                     # openMSX's name
        assert row["openmsx_id"] == "Toshiba_HX-51I"
        assert row["msxorg_title"] == "Toshiba HX-51"       # msx.org link kept
        assert row["year"] == 1985

    def test_not_used_when_openmsx_has_the_msxorg_name(self):
        merged = merge_models(
            [{"manufacturer": "Toshiba", "model": "HX-51"}, {"manufacturer": "Toshiba", "model": "HX-51I"}],
            [_msxorg("HX-51", "HX-51I")],
        )
        assert sorted(m["model"] for m in merged) == ["HX-51", "HX-51I"]

    def test_not_used_when_nothing_matches(self):
        merged = merge_models([], [_msxorg("PHC-35J", "Wavy35")])
        assert [m["model"] for m in merged] == ["PHC-35J"]

    def test_does_not_take_over_an_msxorg_page_of_that_name(self):
        """If msx.org has its own HX-51I page, that page is the HX-51I record."""
        merged = merge_models(
            [{"manufacturer": "Toshiba", "model": "HX-51I"}],
            [_msxorg("HX-51", "HX-51I"), _msxorg("HX-51I")],
        )
        assert sorted(m["model"] for m in merged) == ["HX-51", "HX-51I"]
        assert next(m for m in merged if m["model"] == "HX-51I")["msxorg_title"] == "Toshiba HX-51I"

    def test_alias_lut_applies_to_known_as_names(self, tmp_path):
        import json
        aliases = tmp_path / "aliases.json"
        aliases.write_text(json.dumps({"model": {"HX-10": ["HX-10 (UK)"]}}), encoding="utf-8")
        merged = merge_models(
            [{"manufacturer": "Toshiba", "model": "HX-10 (UK)"}],
            [_msxorg("HX-10P", "HX-10")],
            alias_path=aliases,
        )
        assert [m["model"] for m in merged] == ["HX-10"]

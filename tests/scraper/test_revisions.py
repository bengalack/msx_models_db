"""Tests for model revisions: vocabulary, per-revision resolution and emission.

Design: .claude/artifacts/planning/2026-09-26-model-revisions-design.md
Fixtures are inline and owned by the tests.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from scraper.msxorg import parse_model_page
from scraper.msxorg_series import choose_slotmap_table, resolve_value
from scraper.revisions import REVISION_FIELD, revision_name, revision_numbers, split_revision


# ── Vocabulary ──────────────────────────────────────────────────────────────

class TestRevisionNumbers:
    @pytest.mark.parametrize("text,expected", [
        ("Slot Map for 2nd Gen HB-F500", {2}),
        ("64kB in slot 3-2 (HB-F500 second version)", {2}),
        ("(1st version) QWERTY (2nd version) QWERTY with ñ", {1, 2}),
        ("1987 (first model), 1988 (second model)", {1, 2}),
        ("in slot 3 (version 1) or in slot 1 (version 2)", {1, 2}),
        ("third generation", {3}),
        ("HB-F500 (v2)", {2}),
        ("revision 3", {3}),
    ])
    def test_references_found(self, text, expected):
        assert revision_numbers(text) == expected

    @pytest.mark.parametrize("text", [
        "Slot Map of Bruc 100 with firmware 1.1, 1.2 or 1.3",   # firmware versions are not revisions
        "MSX-DOS 2.20",
        "V9938",
        "64kB in slot 3",
    ])
    def test_no_reference(self, text):
        assert revision_numbers(text) == set()


class TestRevisionName:
    def test_revision_one_is_the_plain_name(self):
        assert revision_name("HB-F500", 1) == "HB-F500"

    def test_later_revisions_use_the_openmsx_suffix(self):
        assert revision_name("HB-F500", 2) == "HB-F500 (v2)"

    def test_split_revision(self):
        assert split_revision("HB-F500 (v2)") == ("HB-F500", 2)
        assert split_revision("HB-F500") == ("HB-F500", 1)


# ── Resolution per revision ─────────────────────────────────────────────────

F500 = ["HB-F500", "HB-F500F", "HB-F500P"]


class TestResolveRevision:
    RAM = "64kB in slot 3-2 (HB-F500 second version) - split between slots 0-0 and 0-2 (other models)"

    def test_later_revision_segment_is_not_the_base_value(self):
        """The base HB-F500 must not take the second version's RAM."""
        assert resolve_value(self.RAM, "HB-F500", F500) is None

    def test_revision_override(self):
        assert resolve_value(self.RAM, "HB-F500", F500, revision=2, override=True) == "64kB in slot 3-2"

    def test_override_only_for_the_named_variant(self):
        assert resolve_value(self.RAM, "HB-F500P", F500, revision=2, override=True) is None
        assert resolve_value(self.RAM, "HB-F500P", F500) == "split between slots 0-0 and 0-2"

    def test_override_without_specific_value_inherits(self):
        assert resolve_value("Yamaha V9938", "HB-F500", F500, revision=2, override=True) is None

    def test_shared_lead_in_before_labels_is_kept(self):
        """Sakhr AX-330: 'PSG clone' applies to both versions; the PSG parser needs it."""
        text = "PSG clone (1st version: OY-2-8910AC, 2nd version: File KC89C72)"
        assert resolve_value(text, "AX-330", ["AX-330"]) == "PSG clone OY-2-8910AC"
        assert resolve_value(text, "AX-330", ["AX-330"], revision=2, override=True) == "PSG clone File KC89C72"

    @pytest.mark.parametrize("text,base,v2", [
        ("(1st version) QWERTY (2nd version) QWERTY with a ñ key", "QWERTY", "QWERTY with a ñ key"),
        ("1st version: TMS-9929A made in Philippines, 2nd version: Yamaha V9938 (MSX2 VDP!)",
         "TMS-9929A made in Philippines", "Yamaha V9938 (MSX2 VDP!)"),
        ("64kB in slot 3 (version 1) or in slot 1 (version 2)", "64kB in slot 3", "in slot 1"),
        ("1987 (first model), 1988 (second model)", "1987", "1988"),
    ])
    def test_revision_forms(self, text, base, v2):
        assert resolve_value(text, "X-1", ["X-1"]) == base
        assert resolve_value(text, "X-1", ["X-1"], revision=2, override=True) == v2


# ── Slot map per revision ───────────────────────────────────────────────────

def _slot(heading: str, cell: str) -> str:
    return (f'<h2><span id="{heading.replace(" ", "_")}" class="mw-headline">{heading}</span></h2>'
            '<table><tr><td></td><th>Slot 0</th></tr>'
            f'<tr><th>Page 0000h~3FFFh</th><td>{cell}</td></tr></table>')


_F500_SLOTS = (_slot("Slot Map for 1st Gen HB-F500", "GEN1")
               + _slot("Slot Map for 2nd Gen HB-F500", "GEN2")
               + _slot("Slot Map for HB-F500F & HB-F500P", "FP"))


def _cell(table) -> str:
    return table.find_all("td")[-1].get_text(strip=True)


class TestSlotmapPerRevision:
    def soup(self):
        return BeautifulSoup(f"<html><body>{_F500_SLOTS}</body></html>", "lxml")

    def test_base_takes_the_first_revision(self):
        assert _cell(choose_slotmap_table(self.soup(), "HB-F500", F500, "")) == "GEN1"

    def test_revision_two(self):
        table = choose_slotmap_table(self.soup(), "HB-F500", F500, "", revision=2, override=True)
        assert _cell(table) == "GEN2"

    def test_other_variant_unaffected(self):
        assert _cell(choose_slotmap_table(self.soup(), "HB-F500P", F500, "")) == "FP"
        assert choose_slotmap_table(self.soup(), "HB-F500P", F500, "", revision=2, override=True) is None


# ── Emission from a model page ──────────────────────────────────────────────

_BRUC_PAGE = ("""
<html><body><div id="bodyContent">
<table>
<tr><th>Brand</th><td>Frael</td></tr>
<tr><th>Model</th><td>Bruc 100</td></tr>
<tr><th>Year</th><td>1987 (first model), 1988 (second model)</td></tr>
<tr><th>RAM</th><td>64kB in slot 3 (version 1) or in slot 1 (version 2)</td></tr>
<tr><th>Video</th><td>Texas Instruments TMS9129</td></tr>
</table>
""" + _slot("Slot Map of Bruc 100 version 1 with firmware 1.0", "Main-ROM")
    + _slot("Slot Map of Bruc 100 version 2 with firmware 1.1", "64kB Memory Mapper")
    + "</div></body></html>").encode()


class TestEmitRevisions:
    def parse(self):
        return {r["model"]: r for r in parse_model_page(_BRUC_PAGE, "MSX1", "Frael Bruc 100")}

    def test_base_and_revision_records(self):
        records = self.parse()
        assert set(records) == {"Bruc 100", "Bruc 100 (v2)"}

    def test_revision_record_shares_the_msxorg_link(self):
        records = self.parse()
        assert records["Bruc 100 (v2)"]["msxorg_title"] == records["Bruc 100"]["msxorg_title"] == "Frael Bruc 100"

    def test_revision_overrides_and_inherits(self):
        records = self.parse()
        base, v2 = records["Bruc 100"], records["Bruc 100 (v2)"]
        assert (base["year"], v2["year"]) == (1987, 1988)
        assert base["main_ram_kb"] == v2["main_ram_kb"] == 64      # "in slot 1" has no size -> inherited
        assert base["vdp"] == v2["vdp"] == "TMS9129"                # shared -> inherited
        assert (base["mapper"], v2["mapper"]) == ("No", "Yes")      # each revision's slot map

    def test_revision_marker(self):
        records = self.parse()
        assert records["Bruc 100 (v2)"][REVISION_FIELD] == 2
        assert REVISION_FIELD not in records["Bruc 100"]

    def test_page_without_revisions_emits_one_record(self):
        page = _BRUC_PAGE.replace(b"(first model), 1988 (second model)", b"").replace(
            b" (version 1) or in slot 1 (version 2)", b"")
        for rev in (b"1", b"2"):   # heading text and anchor id
            page = page.replace(b"version " + rev + b" with", b"with").replace(b"version_" + rev + b"_with", b"with")
        assert [r["model"] for r in parse_model_page(page, "MSX1", "Frael Bruc 100")] == ["Bruc 100"]


# ── Merge gate: only when openMSX has the revision ──────────────────────────

class TestMergeGate:
    def test_revision_kept_when_openmsx_has_it(self):
        from scraper.merge import merge_models
        merged = merge_models(
            [{"manufacturer": "Sony", "model": "HB-F500"}, {"manufacturer": "Sony", "model": "HB-F500 (v2)"}],
            [{"manufacturer": "Sony", "model": "HB-F500", "msxorg_title": "Sony HB-F500"},
             {"manufacturer": "Sony", "model": "HB-F500 (v2)", "msxorg_title": "Sony HB-F500", REVISION_FIELD: 2}],
        )
        v2 = next(m for m in merged if m["model"] == "HB-F500 (v2)")
        assert v2["msxorg_title"] == "Sony HB-F500"

    def test_revision_dropped_without_openmsx_machine(self):
        from scraper.merge import merge_models
        merged = merge_models(
            [],
            [{"manufacturer": "Sakhr", "model": "AX-330"},
             {"manufacturer": "Sakhr", "model": "AX-330 (v2)", REVISION_FIELD: 2}],
        )
        assert [m["model"] for m in merged] == ["AX-330"]

"""Unit tests for scraper/merge.py — CS/ES renumbering and merge preference."""

from __future__ import annotations

from scraper.merge import _renumber_cs_es, _is_slot_type, merge_models


# ── Helpers ───────────────────────────────────────────────────────────────

def _slotmap(**kwargs: str) -> dict:
    """Build a model dict with all 64 slotmap keys set to '•' by default,
    then override specific keys via kwargs (e.g. slotmap_1_0_0='CS1')."""
    m: dict = {}
    for ms in range(4):
        for ss in range(4):
            for p in range(4):
                m[f"slotmap_{ms}_{ss}_{p}"] = "•"
    m.update(kwargs)
    return m


def _fill_slot(ms: int, ss: int, val: str) -> dict:
    """Return a dict of all 4 page keys for (ms, ss) set to val."""
    return {f"slotmap_{ms}_{ss}_{p}": val for p in range(4)}


# ── _is_slot_type ─────────────────────────────────────────────────────────

class TestIsSlotType:
    def test_cs_is_slot_type(self):
        assert _is_slot_type("CS1")
        assert _is_slot_type("CS6!")
    def test_bare_cs_is_slot_type(self):
        assert _is_slot_type("CS")   # stale raw value from msx.org scraper fallback
    def test_es_is_slot_type(self):
        assert _is_slot_type("ES1")
        assert _is_slot_type("ES3!")
    def test_bare_es_is_slot_type(self):
        assert _is_slot_type("ES")   # stale raw value (e.g. pioneer|uc-v102)
    def test_exp_is_slot_type(self):
        assert _is_slot_type("EXP")
    def test_device_abbrs_not_slot_type(self):
        for v in ("MAIN", "MM", "DSK", "MUS", "•", "⌧", None, 42):
            assert not _is_slot_type(v)


# ── _renumber_cs_es ───────────────────────────────────────────────────────

class TestRenumberCsEs:

    def test_no_cs_es_unchanged(self):
        model = {"slotmap_0_0_0": "MAIN", "slotmap_1_0_0": "MM"}
        assert _renumber_cs_es(model) == model

    def test_single_cs_renumbered_to_cs1(self):
        model = _slotmap(**_fill_slot(1, 0, "CS3"))  # stale number
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"

    def test_single_es_renumbered_to_es1(self):
        model = _slotmap(**_fill_slot(2, 0, "ES4"))  # stale number
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_2_0_{p}"] == "ES1"

    def test_bare_es_renumbered_to_es1(self):
        """Bare 'ES' (msx.org scraper fallback) is treated as unnumbered ES and assigned ES1."""
        model = _slotmap(**_fill_slot(2, 0, "ES"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_2_0_{p}"] == "ES1"

    def test_bare_cs_renumbered_to_cs1(self):
        """Bare 'CS' (msx.org scraper fallback) is treated as unnumbered CS and assigned CS1."""
        model = _slotmap(**_fill_slot(1, 0, "CS"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"

    def test_cs_and_es_independent_counters(self):
        model = _slotmap(
            **_fill_slot(1, 0, "CS2"),   # stale
            **_fill_slot(2, 0, "ES3"),   # stale
            **_fill_slot(3, 0, "CS5"),   # stale
        )
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"
            assert result[f"slotmap_2_0_{p}"] == "ES1"
            assert result[f"slotmap_3_0_{p}"] == "CS2"

    def test_bang_suffix_preserved(self):
        # CS in a subslot gets ! preserved after renumber
        model = _slotmap(**_fill_slot(3, 2, "CS5!"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_3_2_{p}"] == "CS1!"

    def test_es_bang_suffix_preserved(self):
        model = _slotmap(**_fill_slot(3, 1, "ES3!"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_3_1_{p}"] == "ES1!"

    def test_ordering_is_ms_then_ss(self):
        # CS in slot 2 should be CS2, CS in slot 1 should be CS1
        model = _slotmap(
            **_fill_slot(1, 0, "CS5"),
            **_fill_slot(2, 0, "CS5"),
        )
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"
            assert result[f"slotmap_2_0_{p}"] == "CS2"

    def test_non_slotmap_fields_untouched(self):
        model = {"model": "MB-H70", **_fill_slot(1, 0, "CS1")}
        result = _renumber_cs_es(model)
        assert result["model"] == "MB-H70"

    def test_all_4_pages_updated(self):
        model = _slotmap(**_fill_slot(0, 0, "CS3"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_0_0_{p}"] == "CS1"

    def test_mb_h70_pattern(self):
        """Simulate post-merge MB-H70: CS1 (front slot) + ES1!, ES2! (back subslots)."""
        model = _slotmap(
            **_fill_slot(1, 0, "CS1"),   # front cartridge slot (stays CS)
            **_fill_slot(2, 0, "ES1"),   # back slot 1 (upgraded by msx.org)
            **_fill_slot(3, 1, "ES2!"),  # back slot 2 in subslot (upgraded)
            **_fill_slot(3, 3, "ES3!"),  # back slot 3 in subslot (upgraded)
        )
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_1_0_{p}"] == "CS1"
            assert result[f"slotmap_2_0_{p}"] == "ES1"
            assert result[f"slotmap_3_1_{p}"] == "ES2!"
            assert result[f"slotmap_3_3_{p}"] == "ES3!"


# ── merge_models: CS/ES preference ───────────────────────────────────────

def _base_model(*, extra: dict | None = None) -> dict:
    m = {"manufacturer": "Hitachi", "model": "MB-H70", "generation": "MSX2"}
    if extra:
        m.update(extra)
    return m


class TestMergeSlotMapCsEsPreference:

    def test_msxorg_es_overrides_openmsx_cs(self):
        """When openMSX emits CS and msx.org emits ES, msx.org wins."""
        openmsx = [_base_model(extra={**_fill_slot(2, 0, "CS2")})]
        msxorg  = [_base_model(extra={**_fill_slot(2, 0, "ES1")})]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        # After merge + renumber, slotmap_2_0_* should be ES
        for p in range(4):
            assert result[0][f"slotmap_2_0_{p}"].startswith("ES")

    def test_both_cs_keeps_cs(self):
        """When both sources agree on CS type, result stays CS."""
        openmsx = [_base_model(extra={**_fill_slot(1, 0, "CS1")})]
        msxorg  = [_base_model(extra={**_fill_slot(1, 0, "CS1")})]
        result = merge_models(openmsx, msxorg)
        for p in range(4):
            assert result[0][f"slotmap_1_0_{p}"].startswith("CS")

    def test_renumber_runs_after_merge(self):
        """Numbers are reassigned fresh after type resolution."""
        openmsx = [_base_model(extra={
            **_fill_slot(1, 0, "CS1"),
            **_fill_slot(2, 0, "CS2"),
        })]
        msxorg = [_base_model(extra={
            **_fill_slot(1, 0, "CS1"),
            **_fill_slot(2, 0, "ES1"),   # slot 2 is actually expansion
        })]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        m = result[0]
        # After merge and renumber: CS1 for slot 1, ES1 for slot 2
        assert m["slotmap_1_0_0"] == "CS1"
        assert m["slotmap_2_0_0"] == "ES1"

    def test_msxorg_exp_overrides_openmsx_cs(self):
        """When openMSX emits CS and msx.org emits EXP (expansion bus), msx.org wins.

        Regression for: daewoo|cpc-300: openMSX='CS2' vs msx.org='EXP' [using openmsx]
        """
        openmsx = [_base_model(extra={**_fill_slot(2, 0, "CS2")})]
        msxorg  = [_base_model(extra={**_fill_slot(2, 0, "EXP")})]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        for p in range(4):
            assert result[0][f"slotmap_2_0_{p}"] == "EXP"

    def test_msxorg_exp_overrides_openmsx_es(self):
        """When openMSX emits ES and msx.org emits EXP, msx.org wins."""
        openmsx = [_base_model(extra={**_fill_slot(3, 0, "ES1")})]
        msxorg  = [_base_model(extra={**_fill_slot(3, 0, "EXP")})]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        for p in range(4):
            assert result[0][f"slotmap_3_0_{p}"] == "EXP"

    def test_exp_not_renumbered(self):
        """EXP values are not touched by _renumber_cs_es (EXP has no number)."""
        model = _slotmap(**_fill_slot(2, 0, "EXP"), **_fill_slot(1, 0, "CS1"))
        result = _renumber_cs_es(model)
        for p in range(4):
            assert result[f"slotmap_2_0_{p}"] == "EXP"
            assert result[f"slotmap_1_0_{p}"] == "CS1"

    def test_msxorg_cs_overrides_openmsx_empty_primary(self):
        """openMSX emits • for an empty non-external primary it can't classify;
        msx.org wins when it knows the slot is a cartridge slot.

        Covers: <primary slot="X"/> (no external="true", no devices) → openMSX: •
        msx.org has CS → merged result: CS.
        """
        openmsx = [_base_model(extra={**_fill_slot(2, 0, "•")})]
        msxorg  = [_base_model(extra={**_fill_slot(2, 0, "CS1")})]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        for p in range(4):
            assert result[0][f"slotmap_2_0_{p}"].startswith("CS")

    def test_msxorg_exp_overrides_openmsx_empty_primary(self):
        """openMSX emits • for an empty non-external primary; msx.org EXP wins.

        Covers: <primary slot="X"/> → openMSX: •; msx.org: EXP → merged: EXP.
        """
        openmsx = [_base_model(extra={**_fill_slot(3, 0, "•")})]
        msxorg  = [_base_model(extra={**_fill_slot(3, 0, "EXP")})]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        for p in range(4):
            assert result[0][f"slotmap_3_0_{p}"] == "EXP"

    def test_msxorg_es_overrides_openmsx_empty_secondary(self):
        """openMSX emits • for an empty <secondary slot="N"/>; msx.org ES wins.

        Covers: National FS-5000F2 pattern — empty secondaries are expansion
        connectors labelled ES{N}! by msx.org.
        """
        openmsx = [_base_model(extra={
            **_fill_slot(0, 1, "•"),
            **_fill_slot(0, 2, "•"),
            **_fill_slot(0, 3, "•"),
        })]
        msxorg = [_base_model(extra={
            **_fill_slot(0, 1, "ES1!"),
            **_fill_slot(0, 2, "ES2!"),
            **_fill_slot(0, 3, "ES3!"),
        })]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        m = result[0]
        for p in range(4):
            assert m[f"slotmap_0_1_{p}"] == "ES1!"
            assert m[f"slotmap_0_2_{p}"] == "ES2!"
            assert m[f"slotmap_0_3_{p}"] == "ES3!"

    def test_msxorg_bare_es_overrides_openmsx_empty_secondary(self):
        """Bare 'ES' from msx.org (scraper raw-text fallback) overrides openMSX •.

        Regression for: pioneer|uc-v102: openMSX='•' vs msx.org='ES' [using openmsx]
        After merge and renumber, bare 'ES' is assigned ES1/ES2/ES3.
        """
        openmsx = [_base_model(extra={
            **_fill_slot(2, 1, "•"),
            **_fill_slot(2, 2, "•"),
            **_fill_slot(2, 3, "•"),
        })]
        msxorg = [_base_model(extra={
            **_fill_slot(2, 1, "ES"),
            **_fill_slot(2, 2, "ES"),
            **_fill_slot(2, 3, "ES"),
        })]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        m = result[0]
        # After renumber: each bare "ES" gets a sequential number
        for p in range(4):
            assert m[f"slotmap_2_1_{p}"].startswith("ES")
            assert m[f"slotmap_2_2_{p}"].startswith("ES")
            assert m[f"slotmap_2_3_{p}"].startswith("ES")


# ── merge_models: openMSX absence wins ────────────────────────────────────

class TestOpenMSXAbsenceWins:
    """Fields in _OPENMSX_ABSENCE_WINS: if openMSX has the machine but not
    the field, msx.org's value is ignored (absence is the authoritative value).
    """

    def test_tape_absent_in_openmsx_overrides_msxorg_yes(self):
        """Core regression: Panasonic FS-A1GT — no <CassettePort> in XML,
        but msx.org wiki incorrectly lists Cassette in connectivity."""
        openmsx = [{"manufacturer": "Panasonic", "model": "FS-A1GT"}]
        msxorg  = [{"manufacturer": "Panasonic", "model": "FS-A1GT", "tape_interface": "Yes"}]
        result = merge_models(openmsx, msxorg)
        assert len(result) == 1
        assert "tape_interface" not in result[0]

    def test_tape_present_in_both_sources_kept(self):
        """When openMSX also sets tape_interface, it is kept normally."""
        openmsx = [{"manufacturer": "Sony", "model": "HB-F1", "tape_interface": "Yes"}]
        msxorg  = [{"manufacturer": "Sony", "model": "HB-F1", "tape_interface": "Yes"}]
        result = merge_models(openmsx, msxorg)
        assert result[0].get("tape_interface") == "Yes"

    def test_tape_openmsx_only_kept(self):
        """When only openMSX has tape_interface, it is kept."""
        openmsx = [{"manufacturer": "Sony", "model": "HB-F1", "tape_interface": "Yes"}]
        msxorg  = [{"manufacturer": "Sony", "model": "HB-F1"}]
        result = merge_models(openmsx, msxorg)
        assert result[0].get("tape_interface") == "Yes"

    def test_tape_msxorg_only_model_not_in_openmsx(self):
        """If openMSX has no record at all for the model, msx.org value is kept
        (the rule only applies when openMSX has the machine but omits the field)."""
        msxorg = [{"manufacturer": "Acme", "model": "X-1", "tape_interface": "Yes"}]
        result = merge_models([], msxorg)
        assert result[0].get("tape_interface") == "Yes"

"""Tests for scraper.update_himem — folding a HIMEM dump into local-raw.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from scraper import __main__ as cli
from scraper.aliases import load_aliases
from scraper.update_himem import (
    candidate_keys,
    load_db_index,
    parse_dump,
    plan_update,
    run,
    format_report,
)


# ── parse_dump ────────────────────────────────────────────────────────────


class TestParseDump:

    def test_reads_name_and_value(self):
        result = parse_dump("Sony HB-75P - 0xF380\n")
        assert result.values == {"Sony HB-75P": "0xF380"}

    def test_tolerates_crlf_line_endings(self):
        result = parse_dump("Sony HB-75P - 0xF380\r\nCanon V-10 - 0xDE79\r\n")
        assert result.values == {"Sony HB-75P": "0xF380", "Canon V-10": "0xDE79"}

    def test_ignores_blank_lines(self):
        result = parse_dump("\n  \nSony HB-75P - 0xF380\n\n")
        assert result.values == {"Sony HB-75P": "0xF380"}

    def test_line_without_a_value_is_reported_not_valued(self):
        result = parse_dump("Sony HB-F500\nCanon V-10 - 0xF380\n")
        assert result.no_reading == ["Sony HB-F500"]
        assert "Sony HB-F500" not in result.values

    def test_line_with_unparsable_value_is_malformed(self):
        result = parse_dump("Sony HB-75P - banana\n")
        assert result.malformed == ["Sony HB-75P - banana"]
        assert result.values == {}

    def test_duplicate_name_keeps_the_lowest_value(self):
        result = parse_dump("Philips NMS 8245 - 0xDF95\nPhilips NMS 8245 - 0xDE79\n")
        assert result.values == {"Philips NMS 8245": "0xDE79"}

    def test_duplicate_name_with_differing_values_is_reported(self):
        result = parse_dump("Philips NMS 8245 - 0xDF95\nPhilips NMS 8245 - 0xDE79\n")
        assert result.conflicts == {"Philips NMS 8245": ["0xDF95", "0xDE79"]}

    def test_duplicate_name_with_identical_values_is_not_a_conflict(self):
        result = parse_dump("Canon V-10 - 0xF380\nCanon V-10 - 0xF380\n")
        assert result.conflicts == {}
        assert result.values == {"Canon V-10": "0xF380"}

    def test_value_only_line_after_a_no_reading_line_still_counts(self):
        # openMSX prints the same machine twice when two configs share a name;
        # a failed boot must not mask the successful one.
        result = parse_dump("Sony HB-F500\nSony HB-F500 - 0xDF94\n")
        assert result.values == {"Sony HB-F500": "0xDF94"}

    def test_hex_value_case_is_preserved_as_written(self):
        result = parse_dump("Canon V-10 - 0xdf95\n")
        assert result.values == {"Canon V-10": "0xdf95"}


# ── database index and name resolution ────────────────────────────────────


def _write_db(path: Path, models: list[tuple[str, str]]) -> Path:
    """Write a minimal docs/data.js stand-in holding *models*."""
    payload = {
        "columns": [{"id": 1, "key": "manufacturer"}, {"id": 2, "key": "model"}],
        "models": [
            {"id": i + 1, "values": [man, mod]} for i, (man, mod) in enumerate(models)
        ],
    }
    path.write_text(
        "// header comment\nwindow.MSX_DATA = "
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    return path


def _write_aliases(path: Path, mapping: dict) -> Path:
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


@pytest.fixture
def plain_lut(tmp_path):
    return load_aliases(_write_aliases(tmp_path / "aliases.json", {}))


class TestLoadDbIndex:

    def test_indexes_models_by_canonical_key(self, tmp_path, plain_lut):
        db = load_db_index(_write_db(tmp_path / "data.js", [("Sony", "HB-75P")]), plain_lut)
        assert db == {("sony", "hb-75p"): ("Sony", "HB-75P")}

    def test_keeps_the_database_spelling_for_output(self, tmp_path, plain_lut):
        db = load_db_index(_write_db(tmp_path / "data.js", [("Yamaha", "CX5MII/128")]), plain_lut)
        assert db[("yamaha", "cx5mii/128")] == ("Yamaha", "CX5MII/128")

    def test_skips_models_missing_a_name(self, tmp_path, plain_lut):
        db = load_db_index(
            _write_db(tmp_path / "data.js", [("Sony", "HB-75P"), (None, "Orphan")]),
            plain_lut,
        )
        assert list(db) == [("sony", "hb-75p")]

    def test_applies_aliases_so_the_index_is_canonical(self, tmp_path):
        lut = load_aliases(
            _write_aliases(tmp_path / "a.json", {"manufacturer": {"Sakhr": ["Al Alamiah"]}})
        )
        db = load_db_index(_write_db(tmp_path / "data.js", [("Al Alamiah", "AX170")]), lut)
        assert db == {("sakhr", "ax170"): ("Al Alamiah", "AX170")}


class TestCandidateKeys:

    def test_resolves_a_single_word_manufacturer(self, tmp_path, plain_lut):
        db = load_db_index(_write_db(tmp_path / "data.js", [("Sony", "HB-75P")]), plain_lut)
        assert candidate_keys("Sony HB-75P", db, plain_lut) == [("sony", "hb-75p")]

    def test_resolves_a_multi_word_manufacturer(self, tmp_path, plain_lut):
        db = load_db_index(
            _write_db(tmp_path / "data.js", [("Bawareth Ent. for Trade/Daewoo", "Perfect MSX1")]),
            plain_lut,
        )
        assert candidate_keys("Bawareth Ent. for Trade/Daewoo Perfect MSX1", db, plain_lut) == [
            ("bawareth ent. for trade/daewoo", "perfect msx1")
        ]

    def test_resolves_through_a_manufacturer_alias(self, tmp_path):
        lut = load_aliases(
            _write_aliases(tmp_path / "a.json", {"manufacturer": {"Sakhr": ["Al Alamiah"]}})
        )
        db = load_db_index(_write_db(tmp_path / "data.js", [("Sakhr", "AX170")]), lut)
        assert candidate_keys("Al Alamiah AX170", db, lut) == [("sakhr", "ax170")]

    def test_resolves_through_a_model_alias(self, tmp_path):
        lut = load_aliases(
            _write_aliases(tmp_path / "a.json", {"model": {"ML-G30 Model 1": ["ML-G30/model 1"]}})
        )
        db = load_db_index(_write_db(tmp_path / "data.js", [("Mitsubishi", "ML-G30 Model 1")]), lut)
        assert candidate_keys("Mitsubishi ML-G30/model 1", db, lut) == [
            ("mitsubishi", "ml-g30 model 1")
        ]

    def test_unknown_machine_resolves_to_nothing(self, tmp_path, plain_lut):
        db = load_db_index(_write_db(tmp_path / "data.js", [("Sony", "HB-75P")]), plain_lut)
        assert candidate_keys("C-BIOS MSX2+ JP", db, plain_lut) == []

    def test_a_single_word_name_resolves_to_nothing(self, tmp_path, plain_lut):
        db = load_db_index(_write_db(tmp_path / "data.js", [("Sony", "HB-75P")]), plain_lut)
        assert candidate_keys("CIEL", db, plain_lut) == []

    def test_two_possible_splits_are_both_returned(self, tmp_path, plain_lut):
        db = load_db_index(
            _write_db(tmp_path / "data.js", [("Acme", "Big Box"), ("Acme Big", "Box")]),
            plain_lut,
        )
        assert sorted(candidate_keys("Acme Big Box", db, plain_lut)) == [
            ("acme", "big box"),
            ("acme big", "box"),
        ]


# ── plan_update ───────────────────────────────────────────────────────────


class TestPlanUpdate:

    def _plan(self, tmp_path, lut, entries, models, dump_text):
        db = load_db_index(_write_db(tmp_path / "data.js", models), lut)
        return plan_update(entries, parse_dump(dump_text), db, lut)

    def test_refreshes_the_value_of_an_existing_entry(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
        )
        assert plan.entries[0]["himem_addr"] == "0xDE79"
        assert plan.updated == [("Sony", "HB-75P", "0xF380", "0xDE79")]

    def test_keeps_the_other_fields_of_an_updated_entry(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-75P", "msxorg_title": "Sony_HB-75P",
              "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
        )
        assert plan.entries[0] == {
            "manufacturer": "Sony", "model": "HB-75P",
            "msxorg_title": "Sony_HB-75P", "himem_addr": "0xDE79",
        }

    def test_an_entry_without_a_value_gains_one(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Yamaha", "model": "CX5M", "msxorg_title": "Yamaha_CX5M"}],
            [("Yamaha", "CX5M")],
            "Yamaha CX5M - 0xF380\n",
        )
        assert plan.entries[0]["msxorg_title"] == "Yamaha_CX5M"
        assert plan.updated == [("Yamaha", "CX5M", None, "0xF380")]

    def test_an_unchanged_value_is_not_reported_as_an_update(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xF380\n",
        )
        assert plan.updated == []
        assert plan.unchanged == [("Sony", "HB-75P")]

    def test_an_entry_the_dump_never_mentions_is_untouched(self, tmp_path, plain_lut):
        curated = {"manufacturer": "ESE", "model": "One chip MSX", "nmos_cmos": "NMOS"}
        plan = self._plan(
            tmp_path, plain_lut,
            [dict(curated)],
            [("ESE", "One chip MSX"), ("Sony", "HB-75P")],
            "Sony HB-75P - 0xF380\n",
        )
        assert plan.entries[0] == curated

    def test_a_failed_boot_never_clears_an_existing_value(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-F500", "himem_addr": "0xDF94"}],
            [("Sony", "HB-F500")],
            "Sony HB-F500\n",
        )
        assert plan.entries == [
            {"manufacturer": "Sony", "model": "HB-F500", "himem_addr": "0xDF94"}
        ]
        assert plan.updated == []

    def test_appends_a_machine_that_is_in_the_database_but_not_the_file(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P"), ("Canon", "V-10")],
            "Canon V-10 - 0xF380\n",
        )
        assert plan.entries[-1] == {
            "manufacturer": "Canon", "model": "V-10", "himem_addr": "0xF380",
        }
        assert plan.added == [("Canon", "V-10", "0xF380")]

    def test_a_new_entry_uses_the_database_spelling_not_the_dump_name(self, tmp_path):
        lut = load_aliases(
            _write_aliases(tmp_path / "a.json", {"manufacturer": {"Sakhr": ["Al Alamiah"]}})
        )
        plan = self._plan(tmp_path, lut, [], [("Sakhr", "AX170")], "Al Alamiah AX170 - 0xF380\n")
        assert plan.entries == [
            {"manufacturer": "Sakhr", "model": "AX170", "himem_addr": "0xF380"}
        ]

    def test_new_entries_are_appended_sorted_after_the_existing_ones(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Zenith", "model": "Z-1", "himem_addr": "0xF380"}],
            [("Zenith", "Z-1"), ("Canon", "V-10"), ("Canon", "V-8"), ("Acme", "A-1")],
            "Canon V-8 - 0xF380\nCanon V-10 - 0xF380\nAcme A-1 - 0xF380\n",
        )
        assert [(e["manufacturer"], e["model"]) for e in plan.entries] == [
            ("Zenith", "Z-1"), ("Acme", "A-1"), ("Canon", "V-10"), ("Canon", "V-8"),
        ]

    def test_a_machine_missing_from_the_database_is_skipped(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut, [], [("Sony", "HB-75P")], "C-BIOS MSX2+ JP - 0xF380\n",
        )
        assert plan.entries == []
        assert [name for name, _ in plan.skipped] == ["C-BIOS MSX2+ JP"]

    def test_an_ambiguous_name_is_skipped_rather_than_guessed(self, tmp_path, plain_lut):
        plan = self._plan(
            tmp_path, plain_lut, [],
            [("Acme", "Big Box"), ("Acme Big", "Box")],
            "Acme Big Box - 0xF380\n",
        )
        assert plan.entries == []
        assert [name for name, _ in plan.skipped] == ["Acme Big Box"]

    def test_duplicate_file_entries_for_one_model_are_left_alone(self, tmp_path, plain_lut):
        # Two entries sharing a key would make "which one wins?" ambiguous;
        # the file is the maintainer's, so report rather than rewrite.
        plan = self._plan(
            tmp_path, plain_lut,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"},
             {"manufacturer": "sony", "model": "hb-75p", "nmos_cmos": "CMOS"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
        )
        assert plan.entries[0]["himem_addr"] == "0xF380"
        assert plan.entries[1] == {"manufacturer": "sony", "model": "hb-75p", "nmos_cmos": "CMOS"}
        assert [name for name, _ in plan.skipped] == ["Sony HB-75P"]

    def test_an_empty_dump_changes_nothing(self, tmp_path, plain_lut):
        entries = [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}]
        plan = self._plan(tmp_path, plain_lut, entries, [("Sony", "HB-75P")], "")
        assert plan.entries == entries
        assert not plan.has_changes


# ── run: file in, file out ────────────────────────────────────────────────


class TestRun:

    def _setup(self, tmp_path, entries, models, dump_text, newline="\r\n", aliases=None):
        local = tmp_path / "local-raw.json"
        body = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
        local.write_bytes(body.replace("\n", newline).encode("utf-8"))
        dump = tmp_path / "himem-values.txt"
        dump.write_bytes(dump_text.replace("\n", newline).encode("utf-8"))
        return {
            "dump_path": dump,
            "json_path": local,
            "db_path": _write_db(tmp_path / "data.js", models),
            "aliases_path": _write_aliases(tmp_path / "a.json", aliases or {}),
        }

    def test_writes_the_new_value_to_the_file(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
        )
        run(**paths)
        written = json.loads(paths["json_path"].read_text(encoding="utf-8"))
        assert written[0]["himem_addr"] == "0xDE79"

    def test_dry_run_leaves_the_file_byte_identical(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
        )
        before = paths["json_path"].read_bytes()
        plan = run(**paths, dry_run=True)
        assert plan.has_changes
        assert paths["json_path"].read_bytes() == before

    def test_keeps_crlf_line_endings(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
            newline="\r\n",
        )
        run(**paths)
        raw = paths["json_path"].read_bytes()
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")

    def test_keeps_lf_line_endings(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xDE79\n",
            newline="\n",
        )
        run(**paths)
        assert b"\r\n" not in paths["json_path"].read_bytes()

    def test_a_dump_with_nothing_new_leaves_the_file_byte_identical(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
            "Sony HB-75P - 0xF380\n",
        )
        before = paths["json_path"].read_bytes()
        run(**paths)
        assert paths["json_path"].read_bytes() == before

    def test_running_twice_changes_nothing_the_second_time(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P"), ("Canon", "V-10")],
            "Sony HB-75P - 0xDE79\nCanon V-10 - 0xF380\n",
        )
        run(**paths)
        after_first = paths["json_path"].read_bytes()
        second = run(**paths)
        assert not second.has_changes
        assert paths["json_path"].read_bytes() == after_first

    def test_a_missing_local_file_is_created(self, tmp_path):
        paths = self._setup(tmp_path, [], [("Canon", "V-10")], "Canon V-10 - 0xF380\n")
        paths["json_path"].unlink()
        run(**paths)
        assert json.loads(paths["json_path"].read_text(encoding="utf-8")) == [
            {"manufacturer": "Canon", "model": "V-10", "himem_addr": "0xF380"}
        ]

    def test_report_names_what_changed(self, tmp_path):
        paths = self._setup(
            tmp_path,
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P"), ("Canon", "V-10")],
            "Sony HB-75P - 0xDE79\nCanon V-10 - 0xF380\nC-BIOS MSX2 - 0xF380\n",
        )
        plan = run(**paths, dry_run=True)
        report = format_report(plan, parse_dump(paths["dump_path"].read_text(encoding="utf-8")))
        assert "Canon" in report and "V-10" in report
        assert "0xF380" in report and "0xDE79" in report
        assert "C-BIOS MSX2" in report


# ── CLI wiring ────────────────────────────────────────────────────────────


class TestCli:

    def _argv(self, tmp_path, dump_text, entries, models):
        local = tmp_path / "local-raw.json"
        local.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        dump = tmp_path / "himem-values.txt"
        dump.write_text(dump_text, encoding="utf-8")
        return local, [
            "python -m scraper", "update-himem", str(dump), str(local),
            "--db", str(_write_db(tmp_path / "data.js", models)),
            "--aliases", str(_write_aliases(tmp_path / "a.json", {})),
        ]

    def test_subcommand_updates_the_file(self, tmp_path, monkeypatch, capsys):
        local, argv = self._argv(
            tmp_path, "Sony HB-75P - 0xDE79\n",
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
        )
        monkeypatch.setattr(sys, "argv", argv)
        cli.main()
        assert json.loads(local.read_text(encoding="utf-8"))[0]["himem_addr"] == "0xDE79"
        assert "updated" in capsys.readouterr().out

    def test_dry_run_flag_does_not_write(self, tmp_path, monkeypatch, capsys):
        local, argv = self._argv(
            tmp_path, "Sony HB-75P - 0xDE79\n",
            [{"manufacturer": "Sony", "model": "HB-75P", "himem_addr": "0xF380"}],
            [("Sony", "HB-75P")],
        )
        before = local.read_bytes()
        monkeypatch.setattr(sys, "argv", argv + ["--dry-run"])
        cli.main()
        capsys.readouterr()
        assert local.read_bytes() == before

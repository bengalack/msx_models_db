"""Unit tests for scraper/link_shares.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper.link_shares import apply_link_shares, load_link_shares


# ---------------------------------------------------------------------------
# load_link_shares — happy path
# ---------------------------------------------------------------------------

def test_load_link_shares_returns_mapping(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": "victor|hc-90"}), encoding="utf-8")
    shares = load_link_shares(f)
    assert shares == {"victor|hc-90a": "victor|hc-90"}


def test_load_link_shares_multiple_entries(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({
        "mfra|modela": "mfra|modelb",
        "mfrc|modelc": "mfrc|modeld",
    }), encoding="utf-8")
    shares = load_link_shares(f)
    assert shares["mfra|modela"] == "mfra|modelb"
    assert shares["mfrc|modelc"] == "mfrc|modeld"


def test_load_link_shares_empty_file(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text("{}", encoding="utf-8")
    shares = load_link_shares(f)
    assert shares == {}


# ---------------------------------------------------------------------------
# load_link_shares — error handling
# ---------------------------------------------------------------------------

def test_load_link_shares_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_link_shares(Path("nonexistent/link-shares.json"))


def test_load_link_shares_invalid_json(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_link_shares(f)


def test_load_link_shares_top_level_not_object(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON object"):
        load_link_shares(f)


def test_load_link_shares_self_reference_rejected(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": "victor|hc-90a"}), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot share links with itself"):
        load_link_shares(f)


def test_load_link_shares_non_string_value_rejected(tmp_path):
    f = tmp_path / "link-shares.json"
    f.write_text(json.dumps({"victor|hc-90a": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="all keys and values must be strings"):
        load_link_shares(f)


# ---------------------------------------------------------------------------
# apply_link_shares
# ---------------------------------------------------------------------------

def _make_records(data: list[tuple[str, dict | None]]) -> tuple[list[dict], list[str]]:
    """Build parallel (records, natural_keys) lists from (natural_key, links) pairs."""
    records = [{"id": i, **({"links": lnk} if lnk is not None else {})}
               for i, (_, lnk) in enumerate(data)]
    natural_keys = [nk for nk, _ in data]
    return records, natural_keys


def test_apply_link_shares_copies_donor_links():
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == donor_links


def test_apply_link_shares_does_not_overwrite_existing_model_link():
    existing_links = {"model": "https://www.msx.org/wiki/Victor_HC-90A"}
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", existing_links),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == existing_links  # unchanged


def test_apply_link_shares_copies_model_link_when_recipient_has_only_openmsx_link():
    """Recipient with only openmsx_id (no model link) should inherit the donor's model link."""
    donor_links = {"model": "https://www.msx.org/wiki/Philips_NMS_8250", "openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Philips_NMS_8250.xml"}
    recipient_links = {"openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Philips_NMS_8250-16.xml"}
    records, natural_keys = _make_records([
        ("philips|nms 8250", donor_links),
        ("philips|nms 8250/16", recipient_links),
    ])
    shares = {"philips|nms 8250/16": "philips|nms 8250"}
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"]["model"] == donor_links["model"]
    assert records[1]["links"]["openmsx_id"] == recipient_links["openmsx_id"]  # preserved


def test_apply_link_shares_skips_donor_with_no_model_link():
    """Donor with only openmsx_id (no model link) should not trigger link inheritance."""
    donor_links = {"openmsx_id": "https://github.com/openMSX/openMSX/blob/master/share/machines/Victor_HC-90.xml"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[1]


def test_apply_link_shares_skips_missing_donor():
    records, natural_keys = _make_records([
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}  # donor not in dataset
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[0]


def test_apply_link_shares_skips_donor_with_no_links():
    records, natural_keys = _make_records([
        ("victor|hc-90", None),   # donor exists but has no links
        ("victor|hc-90a", None),
    ])
    shares = {"victor|hc-90a": "victor|hc-90"}
    apply_link_shares(records, natural_keys, shares)
    assert "links" not in records[1]


def test_apply_link_shares_model_not_in_shares_is_noop():
    records, natural_keys = _make_records([
        ("some_mfr|some model", None),
    ])
    apply_link_shares(records, natural_keys, {})
    assert "links" not in records[0]


def test_apply_link_shares_multiple_recipients_share_same_donor():
    donor_links = {"model": "https://www.msx.org/wiki/Victor_HC-90"}
    records, natural_keys = _make_records([
        ("victor|hc-90", donor_links),
        ("victor|hc-90a", None),
        ("victor|hc-90b", None),
    ])
    shares = {
        "victor|hc-90a": "victor|hc-90",
        "victor|hc-90b": "victor|hc-90",
    }
    apply_link_shares(records, natural_keys, shares)
    assert records[1]["links"] == donor_links
    assert records[2]["links"] == donor_links

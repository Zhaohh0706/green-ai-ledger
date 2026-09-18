"""Tests for the two things this tool claims to get right.

It claims the grid factor is chosen rather than guessed, and that a measured run
is never silently averaged with an estimated one. Both are tested; the energy
figures themselves come from CodeCarbon and are its business, not this tool's.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger import grid, measure, report
from ledger.measure import Record


def _record(**kwargs) -> Record:
    base = dict(
        label="x",
        project="p",
        started="2026-09-14T00:00:00+00:00",
        duration_s=10.0,
        energy_kwh=0.001,
        cpu_kwh=0.0006,
        gpu_kwh=0.0,
        ram_kwh=0.0004,
        method="estimated",
        method_note="nameplate",
        region="广东",
        grid_factor_kg_per_kwh=0.4419,
        co2_kg=0.001 * 0.4419,
        host="Darwin arm64 / Apple M1 Pro",
    )
    base.update(kwargs)
    return Record(**base)


# --------------------------------------------------------------------------
# The grid factor is chosen, not guessed
# --------------------------------------------------------------------------


def test_factors_match_the_published_2023_table():
    assert grid.resolve("全国").value == pytest.approx(0.5306)
    assert grid.resolve("南方").value == pytest.approx(0.4042)
    assert grid.resolve("广东").value == pytest.approx(0.4419)
    assert grid.resolve("四川").value == pytest.approx(0.1564)


def test_an_unknown_region_is_an_error_not_a_default():
    """The whole point: no silent fallback to a plausible-looking number."""
    with pytest.raises(KeyError) as caught:
        grid.resolve("火星")
    assert "rather than guessing" in str(caught.value)


def test_every_factor_carries_the_same_cited_source():
    assert grid.SOURCE["url"].startswith("https://www.mee.gov.cn/")
    assert len(grid.SOURCE["sha256"]) == 64
    assert grid.SOURCE["published"] == "2025-12-31"


def test_the_citation_names_the_issuer_and_the_date():
    text = grid.resolve("广东").citation()
    assert "0.4419" in text and "生态环境部" in text and "2025-12-31" in text


def test_province_and_its_region_differ_enough_to_matter():
    # Guangdong sits in the Southern grid, and the two factors are 9% apart, so
    # picking the wrong level of the table is not a rounding decision.
    province = grid.resolve("广东").value
    region = grid.resolve("南方").value
    assert abs(province - region) / region > 0.08


# --------------------------------------------------------------------------
# Measured and estimated are kept apart
# --------------------------------------------------------------------------


def test_a_ledger_of_estimates_says_so_first():
    text = report.to_markdown([_record(), _record()])
    assert "全部记录为估算，不是实测" in text
    assert text.index("全部记录为估算") < text.index("## 估算")


def test_measured_and_estimated_are_totalled_separately():
    records = [
        _record(method="estimated", energy_kwh=0.001, co2_kg=0.001 * 0.4419),
        _record(method="measured", energy_kwh=0.002, co2_kg=0.002 * 0.4419),
    ]
    text = report.to_markdown(records)
    assert "## 实测（1 条）" in text
    assert "## 估算（1 条）" in text
    assert "全部记录为估算" not in text


def test_the_badge_states_which_method_it_used():
    assert "estimated" in report.badge_line([_record()])
    assert "measured" in report.badge_line([_record(method="measured")])


def test_a_badge_mixing_methods_reports_the_weaker_one():
    line = report.badge_line([_record(method="measured"), _record(method="estimated")])
    assert "estimated" in line


# --------------------------------------------------------------------------
# The counterfactual
# --------------------------------------------------------------------------


def test_counterfactual_shows_the_spread_across_exits():
    rows = {r["exit"]: r for r in measure.counterfactual(_record())}
    # Guangdong is 0.4419; an exit resolving to South Korea applies 0.4306.
    assert rows["South Korea"]["error_pct"] == pytest.approx(-2.56, abs=0.05)
    # Iceland understates by roughly sixteen times.
    assert rows["Iceland"]["factor"] / 0.4419 == pytest.approx(1 / 16, rel=0.02)
    # Even the right country is well off: a national average is not a province.
    assert rows["China (national average)"]["error_pct"] == pytest.approx(31.8, abs=0.2)


def test_the_example_exits_cite_their_source():
    for row in measure.counterfactual(_record()):
        assert "CodeCarbon" in row["source"]


def test_the_home_directory_is_not_written_to_the_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr(measure.Path, "home", classmethod(lambda cls: tmp_path))
    command = f"env PYTHONPATH=src {tmp_path}/envs/x/bin/python -m pytest"
    assert measure.redact(command) == "env PYTHONPATH=src ~/envs/x/bin/python -m pytest"
    assert str(tmp_path) not in measure.redact(command)


def test_a_command_without_the_home_directory_is_unchanged():
    assert measure.redact("make train") == "make train"


def test_power_availability_is_reported_honestly():
    available, note = measure.power_measurement_available()
    assert isinstance(available, bool)
    assert note
    if not available:
        assert "root" in note or "not macOS" in note or "not found" in note


# --------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------


def test_records_survive_a_round_trip(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    original = _record(label="round trip", extra={"note": "kept"})
    measure.append(original, path)
    loaded = measure.load(path)
    assert len(loaded) == 1
    assert loaded[0].label == "round trip"
    assert loaded[0].extra == {"note": "kept"}
    assert loaded[0].co2_g == pytest.approx(original.co2_g)


def test_raw_energy_is_kept_so_a_correction_needs_no_rerun(tmp_path: Path):
    """If the factor turns out wrong, the kWh is still there to recompute from."""
    path = tmp_path / "ledger.jsonl"
    measure.append(_record(), path)
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["energy_kwh"] > 0
    assert row["grid_factor_kg_per_kwh"] > 0
    assert row["co2_kg"] == pytest.approx(row["energy_kwh"] * row["grid_factor_kg_per_kwh"])

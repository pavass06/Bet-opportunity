import copy
import json
from pathlib import Path

import pytest

import scanner
from scanner import analyze_events

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "examples" / "sample_odds.json").read_text())


@pytest.fixture
def events():
    return copy.deepcopy(SAMPLE)


def test_plus_ev_uses_margin_free_sharp_price_and_kelly(events):
    found = analyze_events(events, bankroll=1000, kelly_fraction=0.25, min_edge_percent=1.0)
    by_outcome = {o["bet"]["outcome"]: o for o in found["plus_ev"]}

    hawks = by_outcome["Harbor City Hawks"]
    assert hawks["bet"]["soft_book"] == "DraftKings"
    assert hawks["sharp"]["fair_odds"] == pytest.approx(2.0)  # 1.95 / 1.95 -> fair 2.00
    assert hawks["edge_percent"] == pytest.approx(3.0)
    assert hawks["kelly"]["full_percent"] == pytest.approx(2.83, abs=0.01)
    assert hawks["kelly"]["recommended_stake"] == pytest.approx(7.08, abs=0.01)

    # 3-way soccer market: fair price computed over home / draw / away
    northport = by_outcome["Northport FC"]
    implied = 1 / 2.10 + 1 / 3.50 + 1 / 3.60
    assert northport["sharp"]["fair_odds"] == pytest.approx(2.10 * implied)
    assert northport["edge_percent"] == pytest.approx((2.22 / (2.10 * implied) - 1) * 100, abs=0.01)


def test_plus_ev_respects_min_edge(events):
    found = analyze_events(events, min_edge_percent=2.0)
    assert [o["bet"]["outcome"] for o in found["plus_ev"]] == ["Harbor City Hawks"]


def test_arbitrage_detected_across_books(events):
    found = analyze_events(events, stake_amount=100)
    arbs = found["arbitrage"]
    assert len(arbs) == 1
    arb = arbs[0]
    assert arb["market"] == "h2h"
    expected_roi = (1 / (1 / 2.06 + 1 / 2.00) - 1) * 100
    assert arb["roi_percent"] == pytest.approx(expected_roi, abs=0.05)
    stakes = arb["stakes"]["breakdown"]
    assert sum(s["stake"] for s in stakes) == pytest.approx(100, abs=0.02)


def test_middle_window_and_probability(events):
    found = analyze_events(events, stake_amount=100)
    middles = found["middles"]
    assert len(middles) == 1
    mid = middles[0]
    assert mid["gap"]["middle_integers"] == [2, 3]
    assert mid["middle_probability"] == pytest.approx(0.05)  # NBA spreads: 2.5% per integer
    assert mid["ev_percent"] > 0


def test_exchange_commission_reduces_arbitrage_roi(events):
    # Re-label FanDuel as an exchange: a 2% commission must cut into the arb ROI
    # (2.00 becomes 1.98 net, still the best price for that side).
    nba = events[1]
    for book in nba["bookmakers"]:
        if book["key"] == "fanduel":
            book["key"], book["title"] = "matchbook", "Matchbook"
    found = analyze_events(events, stake_amount=100, commission_rate=0.02)
    arb = found["arbitrage"][0]
    assert arb["has_exchange"] is True
    assert arb["roi_percent"] == pytest.approx((1 / (1 / 2.06 + 1 / 1.98) - 1) * 100, abs=0.05)
    assert arb["roi_percent"] < arb["gross_roi_percent"]


def test_no_sharp_book_means_no_plus_ev(events):
    for event in events:
        event["bookmakers"] = [b for b in event["bookmakers"] if b["key"] != "pinnacle"]
    assert analyze_events(events)["plus_ev"] == []


def test_run_scan_requires_api_key():
    result = scanner.run_scan("")
    assert result["success"] is False
    assert result["error_code"] == 400

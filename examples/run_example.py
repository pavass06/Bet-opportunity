"""Run the detection pipeline offline on examples/sample_odds.json (synthetic data, no API key).

Usage:  python examples/run_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scanner import analyze_events  # noqa: E402

SAMPLE = ROOT / "examples" / "sample_odds.json"


def main() -> None:
    events = json.loads(SAMPLE.read_text())
    found = analyze_events(events, stake_amount=100.0, bankroll=1000.0, kelly_fraction=0.25)

    print("+EV bets (sharp reference: Pinnacle, margin removed proportionally, quarter Kelly, bankroll 1000)")
    for opp in found["plus_ev"]:
        bet, sharp, kelly = opp["bet"], opp["sharp"], opp["kelly"]
        print(
            f"  {opp['event']:<40} {bet['outcome']:<20} {bet['soft_book']:<13} "
            f"odds {bet['soft_odds']:.2f}  fair {sharp['fair_odds']:.3f}  "
            f"edge {opp['edge_percent']:+.2f}%  EV/100 {opp['ev_per_100']:+.2f}  "
            f"full Kelly {kelly['full_percent']:.2f}%  stake {kelly['recommended_stake']:.2f}"
        )

    print("\nArbitrages (stake 100)")
    for opp in found["arbitrage"]:
        legs = ", ".join(f"{o['outcome']} @ {o['price']:.2f} ({o['bookmaker']})" for o in opp["best_odds"])
        print(f"  {opp['event']:<40} {opp['market']:<8} ROI {opp['roi_percent']:+.2f}%  [{legs}]")

    print("\nMiddles (stake 100)")
    for opp in found["middles"]:
        print(
            f"  {opp['event']:<40} {opp['middle_zone']:<28} "
            f"P(middle) {opp['probability_percent']:.1f}%  EV {opp['ev_percent']:+.2f}%"
        )


if __name__ == "__main__":
    main()

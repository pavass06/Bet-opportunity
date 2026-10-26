"""Monte Carlo bankroll simulation: full vs fractional Kelly, with and without model error.

Each path places ``N_BETS`` sequential bets. For every bet, decimal odds are drawn uniformly in
[1.7, 3.0] and the model *believes* it has a +3% edge: p_est = 1.03 / odds. Stakes follow the
Kelly fraction computed from p_est (see ``odds_math.kelly_fraction``), times the multiplier.

Two worlds are simulated with the same random draws:
  * model right:  the true probability equals p_est (real edge +3%);
  * model wrong:  the true probability is 1 / odds (real edge 0%, the "edge" was estimation error).

Output: docs/bankroll_simulation.png and a summary table printed to stdout.
Usage:  python examples/simulate_bankroll.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from odds_math import kelly_fraction  # noqa: E402

SEED = 42
N_PATHS = 5_000
N_BETS = 1_000
ESTIMATED_EDGE = 0.03
MULTIPLIERS = {"Full Kelly": 1.0, "Half Kelly": 0.5, "Quarter Kelly": 0.25}
COLORS = {"Full Kelly": "#2a78d6", "Half Kelly": "#eb6834", "Quarter Kelly": "#1baf7a"}
OUTPUT = ROOT / "docs" / "bankroll_simulation.png"

_kelly = np.vectorize(kelly_fraction, otypes=[float])


def simulate(true_edge: float, multiplier: float, odds: np.ndarray, uniforms: np.ndarray) -> np.ndarray:
    """Return bankroll paths of shape (N_PATHS, N_BETS + 1), starting at 1."""
    p_est = (1 + ESTIMATED_EDGE) / odds
    p_true = (1 + true_edge) / odds
    stake_fraction = multiplier * _kelly(p_est, odds)
    wins = uniforms < p_true
    growth = np.where(wins, 1 + stake_fraction * (odds - 1), 1 - stake_fraction)
    paths = np.cumprod(growth, axis=1)
    return np.hstack([np.ones((paths.shape[0], 1)), paths])


def max_drawdown(paths: np.ndarray) -> np.ndarray:
    peaks = np.maximum.accumulate(paths, axis=1)
    return (1 - paths / peaks).max(axis=1)


def main() -> None:
    rng = np.random.default_rng(SEED)
    odds = rng.uniform(1.7, 3.0, size=(N_PATHS, N_BETS))
    uniforms = rng.uniform(size=(N_PATHS, N_BETS))

    worlds = {"Model right: real edge +3%": ESTIMATED_EDGE, "Model wrong: real edge 0%": 0.0}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    x = np.arange(N_BETS + 1)

    print(f"{N_PATHS} paths x {N_BETS} bets, odds U[1.7, 3.0], estimated edge +3%, start bankroll = 1")
    print(f"{'world':<28} {'sizing':<14} {'median final':>12} {'P(final<1)':>11} {'P(maxDD>=50%)':>14}")
    for ax, (title, true_edge) in zip(axes, worlds.items()):
        for label, mult in MULTIPLIERS.items():
            paths = simulate(true_edge, mult, odds, uniforms)
            final = paths[:, -1]
            dd = max_drawdown(paths)
            print(
                f"{title:<28} {label:<14} {np.median(final):>12.2f} "
                f"{(final < 1).mean():>11.1%} {(dd >= 0.5).mean():>14.1%}"
            )
            lo, med, hi = np.percentile(paths, [10, 50, 90], axis=0)
            ax.fill_between(x, lo, hi, color=COLORS[label], alpha=0.12, linewidth=0)
            ax.plot(x, med, color=COLORS[label], linewidth=2, label=f"{label} (median {med[-1]:.2f}x)")
        ax.set_yscale("log")
        ax.set_yticks([0.25, 0.5, 1, 2, 4])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}x"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.legend(frameon=False, loc="upper left", fontsize=9)
        ax.axhline(1, color="#999999", linewidth=1, linestyle="--")
        ax.set_title(title, fontsize=11, loc="left")
        ax.set_xlabel("Bets placed")
        ax.grid(axis="y", color="#e6e6e6", linewidth=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel("Bankroll (multiple of start, log scale)")
    fig.suptitle(
        "Kelly sizing on simulated +EV bets: median path and 10-90% band (5,000 paths)",
        fontsize=12, x=0.01, ha="left",
    )
    fig.tight_layout()
    OUTPUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUTPUT, dpi=150)
    print(f"\nSaved {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

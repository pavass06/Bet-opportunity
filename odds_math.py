"""Pure pricing functions: odds, bookmaker margin, edge, expected value and Kelly sizing.

All odds are decimal odds (a winning stake of 1 returns ``odds``, i.e. a net profit of ``odds - 1``).
No I/O here, so everything in this module is unit-tested in ``tests/test_odds_math.py``.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple


def implied_probability(odds: float) -> float:
    """Probability implied by a decimal price, margin included (``1 / odds``)."""
    if odds <= 0:
        raise ValueError("odds must be positive")
    return 1.0 / odds


def remove_margin(prices: Sequence[float]) -> Tuple[List[float], float]:
    """Remove the bookmaker margin from one market with the proportional method.

    Each implied probability is divided by their sum so the probabilities add up to 1.

    Returns ``(fair_odds, margin_percent)``. If any price is <= 1 the input is returned
    unchanged with a margin of 0, because such a market cannot be normalised.
    """
    prices = list(prices)
    if not prices or any(p <= 1 for p in prices):
        return prices, 0.0
    implied = [1.0 / p for p in prices]
    total = sum(implied)
    fair_odds = [total / i for i in implied]
    margin_percent = max(0.0, (total - 1.0) * 100)
    return fair_odds, margin_percent


def edge_percent(odds: float, fair_odds: float) -> float:
    """Edge of a price over the fair price, in percent: ``(odds / fair_odds - 1) * 100``."""
    if fair_odds <= 0:
        return 0.0
    return (odds / fair_odds - 1.0) * 100


def expected_value(true_probability: float, odds: float, stake: float) -> float:
    """Expected profit of a single bet, rounded to cents: ``p * (odds - 1) * stake - (1 - p) * stake``."""
    p = max(0.0, min(true_probability, 1.0))
    value = p * stake * (odds - 1.0) - (1.0 - p) * stake
    return round(value, 2)


def kelly_fraction(true_probability: float, odds: float) -> float:
    """Full-Kelly fraction of bankroll ``f* = (p * b - q) / b`` with ``b = odds - 1``.

    Returns 0 when the bet has no positive edge (Kelly never bets on a negative edge).
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    p = max(0.0, min(true_probability, 1.0))
    f = (b * p - (1.0 - p)) / b
    return max(0.0, f)


def kelly_stake(
    true_probability: float, odds: float, bankroll: float, fraction: float
) -> Tuple[float, float, float]:
    """Kelly sizing for one bet.

    ``fraction`` is the Kelly multiplier (1 = full Kelly, 0.25 = quarter Kelly), clamped to [0, 1].

    Returns ``(full_kelly_percent, applied_percent, stake)``, percentages of bankroll rounded to
    2 decimals and the stake in currency units.
    """
    if bankroll <= 0:
        return 0.0, 0.0, 0.0
    full = kelly_fraction(true_probability, odds)
    if full <= 0:
        return 0.0, 0.0, 0.0
    applied = full * max(0.0, min(fraction, 1.0))
    return round(full * 100, 2), round(applied * 100, 2), round(bankroll * applied, 2)


def odds_after_commission(price: float, commission_rate: float, is_exchange: bool) -> float:
    """Effective decimal price once an exchange commission is charged on net winnings.

    Bookmaker prices (``is_exchange=False``) are returned unchanged.
    """
    if not is_exchange:
        return price
    profit = price - 1.0
    if profit <= 0:
        return price
    return 1.0 + profit * (1.0 - commission_rate)

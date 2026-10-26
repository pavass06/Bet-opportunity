import math

import pytest

from odds_math import (
    edge_percent,
    expected_value,
    implied_probability,
    kelly_fraction,
    kelly_stake,
    odds_after_commission,
    remove_margin,
)


# --- odds -> probability ----------------------------------------------------

def test_implied_probability_is_inverse_of_odds():
    assert implied_probability(2.0) == pytest.approx(0.5)
    assert implied_probability(4.0) == pytest.approx(0.25)


def test_implied_probability_rejects_non_positive_odds():
    with pytest.raises(ValueError):
        implied_probability(0)


# --- margin removal ---------------------------------------------------------

def test_remove_margin_two_way_symmetric_market():
    fair, margin = remove_margin([1.91, 1.91])
    assert fair == pytest.approx([2.0, 2.0])
    assert margin == pytest.approx((2 / 1.91 - 1) * 100)


def test_remove_margin_probabilities_sum_to_one_three_way():
    fair, margin = remove_margin([2.10, 3.50, 3.60])
    assert sum(1 / f for f in fair) == pytest.approx(1.0)
    assert margin == pytest.approx((1 / 2.10 + 1 / 3.50 + 1 / 3.60 - 1) * 100)
    # proportional method keeps the ranking of the outcomes
    assert fair[0] < fair[1] < fair[2]


def test_remove_margin_no_margin_market_is_unchanged():
    fair, margin = remove_margin([2.0, 2.0])
    assert fair == pytest.approx([2.0, 2.0])
    assert margin == 0.0


def test_remove_margin_invalid_prices_returned_as_is():
    fair, margin = remove_margin([1.0, 3.0])
    assert fair == [1.0, 3.0]
    assert margin == 0.0


# --- edge and EV ------------------------------------------------------------

def test_edge_percent():
    assert edge_percent(2.10, 2.00) == pytest.approx(5.0)
    assert edge_percent(1.90, 2.00) == pytest.approx(-5.0)
    assert edge_percent(2.0, 0) == 0.0


def test_expected_value_matches_formula():
    # p * odds - 1 per unit staked
    assert expected_value(0.5, 2.20, 100) == pytest.approx(10.0)
    assert expected_value(0.5, 2.00, 100) == pytest.approx(0.0)
    assert expected_value(0.4, 2.00, 100) == pytest.approx(-20.0)


def test_edge_and_ev_are_consistent():
    # with p = 1 / fair_odds, EV per unit equals the edge
    fair = 2.183
    assert expected_value(1 / fair, 2.22, 100) == pytest.approx(edge_percent(2.22, fair), abs=0.01)


# --- Kelly ------------------------------------------------------------------

def test_kelly_fraction_known_value():
    # p = 0.5, b = 1.2 -> f* = (1.2*0.5 - 0.5) / 1.2 = 1/12
    assert kelly_fraction(0.5, 2.2) == pytest.approx(1 / 12)


def test_kelly_fraction_is_zero_without_edge():
    assert kelly_fraction(0.5, 2.0) == 0.0
    assert kelly_fraction(0.4, 2.0) == 0.0
    assert kelly_fraction(0.9, 1.0) == 0.0


def test_kelly_fraction_maximises_log_growth():
    p, odds = 0.55, 2.0
    f_star = kelly_fraction(p, odds)

    def growth(f):
        return p * math.log(1 + f * (odds - 1)) + (1 - p) * math.log(1 - f)

    for f in (f_star * 0.5, f_star * 1.5, f_star * 2.0):
        assert growth(f_star) > growth(f)
    # over-betting at ~2x Kelly destroys the growth despite a positive edge
    assert growth(2 * f_star) == pytest.approx(0.0, abs=1e-3)


@pytest.mark.parametrize("fraction", [1.0, 0.5, 0.25, 0.1])
def test_kelly_stake_fractional(fraction):
    full_pct, applied_pct, stake = kelly_stake(0.5, 2.2, 1000, fraction)
    assert full_pct == pytest.approx(100 / 12, abs=0.01)
    assert applied_pct == pytest.approx(100 / 12 * fraction, abs=0.01)
    assert stake == pytest.approx(1000 / 12 * fraction, abs=0.01)


def test_kelly_stake_clamps_fraction_and_handles_no_edge():
    assert kelly_stake(0.5, 2.2, 1000, 3.0) == kelly_stake(0.5, 2.2, 1000, 1.0)
    assert kelly_stake(0.4, 2.0, 1000, 0.25) == (0.0, 0.0, 0.0)
    assert kelly_stake(0.6, 2.0, 0, 0.25) == (0.0, 0.0, 0.0)


# --- exchange commission ----------------------------------------------------

def test_commission_only_applies_to_exchange_winnings():
    assert odds_after_commission(3.0, 0.05, is_exchange=True) == pytest.approx(2.9)
    assert odds_after_commission(3.0, 0.05, is_exchange=False) == 3.0
    assert odds_after_commission(1.0, 0.05, is_exchange=True) == 1.0

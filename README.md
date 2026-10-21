# Bet-opportunity (Edge Scanner)

**Arbitrage • Middles • +EV • Kelly • CLV**

Sports betting scanner that compares odds across bookmakers (via [The Odds API](https://the-odds-api.com/)) to detect arbitrage, middles and positive expected value (+EV) bets, then tracks signal quality over time (CLV, Brier score, realized ROI).

> Fork of an open source sports arbitrage scanner, extended with: +EV with sharp-book de-vigging, Kelly sizing, a parlay builder, SQLite persistence, and CLV / results tracking.

## Features

| Tab | What it finds | Risk profile |
|---|---|---|
| **Arbitrage** | Guaranteed profit by betting every outcome across different books | Near zero (execution risk) |
| **Middles** | Line gaps between two books where both bets can win | High variance, +EV if the probability is right |
| **+EV** | Soft book odds better than the sharp book's fair price | Medium variance, profit over volume |
| **Builder** | Parlays built from the last scan's +EV bets | High variance |
| **History** | Tracked bets: CLV, W/L results, realized ROI, Brier score | Validation tool |

## Setup

```bash
git clone https://github.com/pavass06/Bet-opportunity.git
cd Bet-opportunity
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Your browser opens automatically (port 5000, falling back to 5050 or 8000; on macOS port 5000 is often taken by AirPlay, so the app switches to 5050).

**API key:** free at [the-odds-api.com](https://the-odds-api.com/) (500 requests/month). Enter it in the UI, or create a `.env` file at the project root:

```
ODDS_API_KEY=your_api_key_here
```

The `.env` file is required for automatic CLV tracking (the background scheduler reads the key at startup).

---

## The theory in short

### Implied probability and the vig

A decimal price `c` implies a probability of `1/c`. On a two-way market a book might show 1.91 / 1.91: 52.4% + 52.4% = **104.8%**. The extra 4.8% is the bookmaker's margin (the *vig*), which is how it wins in the long run.

### EV: expected value

Expected value is the sum of each possible outcome weighted by its probability. For a 1 unit stake:

| Event | Probability | Net result |
|---|---|---|
| Bet wins | `p` | `+(odds − 1)` |
| Bet loses | `1 − p` | `−1` |

```
EV = p × (odds − 1) − (1 − p)  =  p × odds − 1
```

A bet is +EV when **`p × odds > 1`**, i.e. when the price is above the fair price `1/p`. Example: odds 2.20 and a true probability of 50% give EV = +0.10 per unit staked. For a stake `B`, everything scales by `B`.

A +EV bet can still lose: EV is an average over many bets. The whole difficulty is knowing `p`.

### How `p` is estimated: the sharp book

Nobody knows the true probability. Instead, a very accurate book is used as the reference (Pinnacle by default, or Betfair Exchange / Matchbook):

1. Remove its vig (proportional method: divide each implied probability by their sum).
2. This gives the **fair odds**.
3. Compare against soft books (DraftKings, FanDuel, Winamax, Unibet, etc.).

```
edge % = (soft_odds / fair_odds − 1) × 100
```

This is *value betting*. The assumption is that the sharp book is right and the soft book is wrong.

### Kelly criterion

EV tells you **whether** to bet, Kelly tells you **how much**. It maximizes the compound growth of the bankroll:

```
f* = (p × b − q) / b      with b = odds − 1 and q = 1 − p
```

This is the EV per unit (`p×b − q`) divided by `b`: for the same edge, longer odds are riskier, so the stake is smaller.

Why not just maximize EV? Because it would tell you to stake your whole bankroll, which leads to ruin: a bankroll grows by **multiplication**, not addition. Kelly maximizes the geometric growth rate:

```
g(f) = (1 + f·b)^p × (1 − f)^q          (equivalent to maximizing p·ln(1+f·b) + q·ln(1−f))
```

This curve is bell-shaped: under-betting costs little growth, over-betting (beyond `2f*`) loses money despite a positive edge. Since `p` is only an estimate, **fractional Kelly** is used: ½, **¼ (default)** or 1/10.

### Arbitrage

No assumption on `p`. If the sum of the implied probabilities of the best price on each outcome is **below 100%**, you stake every outcome in proportion and win whatever happens.

Example: 2.10 on team 1 at book A, 2.10 on team 2 at book B → `1/2.1 + 1/2.1 = 95.2%` → about 5% guaranteed profit.

Practical risks: odds move before the second leg is placed, rules differ between books, and winning accounts get limited. Exchanges charge a commission, which the app deducts (net and gross ROI are both shown).

### Middle

Two books offer different lines on the same market, e.g. Team X **−2.5** at A and Team Y **+4.5** at B. If X wins by 3 or 4 points, both bets win. Outside that window only one wins and you lose the vig (~5%) on the other.

```
EV = P(middle) × double_win − (1 − P(middle)) × single_loss
```

`P(middle)` comes from historical margin distributions per sport (`PROBABILITY_PER_INTEGER` in `config.py`). In the NFL, **key numbers** (3, 7, 10, 6, 14…) are very frequent margins: a middle spanning them is worth much more than one of the same width. Profile: small frequent loss, rare big win, profitable only if the estimated probability is right.

### CLV (Closing Line Value)

Compare the price you took with Pinnacle's **closing** price just before the event starts:

```
CLV % = (taken_odds / closing_odds − 1) × 100
```

The closing line is the best public estimate of the true probability. A positive average CLV over a few dozen bets points to a real edge, whereas realized ROI needs thousands of bets to be reliable.

### Parlays (Builder)

Odds and probabilities multiply, **and so do the margins**. A parlay is only worthwhile if every leg is +EV. The Builder uses a single book per ticket, excludes two legs from the same match (correlation), and sorts by compound edge.

---

## Tracking and validation

- Every detected +EV bet is saved to SQLite (`data/edge_scanner.db`), deduplicated per `(event, market, outcome, book)` and per day.
- An APScheduler job (every 30 min) fetches Pinnacle's closing odds for events starting within the hour and computes CLV.
- The **History** tab lets you record W/L by hand and shows: actual vs expected win rate, flat-stake realized ROI, and the **Brier score** (`AVG((1/fair_odds − result)²)`, good if < 0.25).
- `/export` downloads the full history as CSV.

Assumption: there is no push/void state; a draw (soccer h2h) on the selected outcome counts as a loss.

## API usage

A full scan of 11 sports uses 12 requests (1 for the sports list + 1 per sport). The free tier (500/month) allows about 40 full scans. The EU region is always included so that Pinnacle is available as the sharp reference.

## Configuration (UI)

Regions (US, US2, UK, EU, AU), sports, stake, exchange commission, minimum middle gap, minimum +EV edge, sharp reference book, Kelly fraction, bankroll, decimal/American odds, dark/light theme.

## Tech stack

Python 3.11+, Flask, vanilla HTML/CSS/JS, SQLite, APScheduler, The Odds API.

## Roadmap

- Telegram alerts
- UI auto-refresh
- Near-arbs (sum < 103%)
- Shin de-vigging method
- Odds freshness filters and a confidence score
- Polymarket / Kalshi as reference sources

## Disclaimer

For educational and research purposes. Sports betting involves risk of loss, probability estimates can be wrong, and bookmakers may limit winning accounts. Never stake more than you can afford to lose.

## License

MIT. Based on an original open source project, see `LICENSE`.

"""SQLite persistence layer for Edge Scanner."""

from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/edge_scanner.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plus_ev_opportunity (
    id                  TEXT PRIMARY KEY,
    detected_at         TEXT NOT NULL,
    event               TEXT NOT NULL,
    sport               TEXT NOT NULL,
    market              TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    soft_book           TEXT NOT NULL,
    soft_odds           REAL NOT NULL,
    fair_odds           REAL NOT NULL,
    edge_percent        REAL NOT NULL,
    ev_per_100          REAL,
    commence_time       TEXT,
    closing_odds        REAL,
    clv_percent         REAL,
    closing_fetched_at  TEXT,
    result              INTEGER,
    result_set_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_commence ON plus_ev_opportunity(commence_time);
CREATE INDEX IF NOT EXISTS idx_detected ON plus_ev_opportunity(detected_at);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)
        # Migrate older databases created before the result columns existed.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(plus_ev_opportunity)")}
        if "result" not in existing:
            conn.execute("ALTER TABLE plus_ev_opportunity ADD COLUMN result INTEGER")
        if "result_set_at" not in existing:
            conn.execute("ALTER TABLE plus_ev_opportunity ADD COLUMN result_set_at TEXT")


def save_plus_ev_opportunities(opportunities: list[dict]) -> int:
    """Persist +EV opps, one entry per (event, market, outcome, book) per day."""
    if not opportunities:
        return 0
    today = dt.date.today().isoformat()
    saved = 0
    with _conn() as conn:
        for opp in opportunities:
            bet = opp.get("bet", {})
            sharp = opp.get("sharp", {})
            event = opp.get("event") or ""
            market = opp.get("market") or ""
            outcome = (bet.get("outcome") or "").strip()
            soft_book = bet.get("soft_book") or ""
            # One detection per combination per calendar day
            exists = conn.execute(
                """SELECT 1 FROM plus_ev_opportunity
                   WHERE event = ? AND market = ? AND outcome = ? AND soft_book = ?
                   AND DATE(detected_at) = ?""",
                (event, market, outcome, soft_book, today),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO plus_ev_opportunity
                   (id, detected_at, event, sport, market, outcome, soft_book,
                    soft_odds, fair_odds, edge_percent, ev_per_100, commence_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    opp.get("id"),
                    dt.datetime.utcnow().isoformat() + "Z",
                    event,
                    opp.get("sport") or "",
                    market,
                    outcome,
                    soft_book,
                    bet.get("soft_odds"),
                    sharp.get("fair_odds"),
                    opp.get("edge_percent"),
                    opp.get("ev_per_100"),
                    opp.get("commence_time"),
                ),
            )
            saved += 1
    return saved


def get_pending_closing() -> list[dict]:
    """Return opps needing closing odds, for events starting within ±90 min of now."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM plus_ev_opportunity
               WHERE closing_odds IS NULL
               AND commence_time IS NOT NULL
               AND commence_time >= datetime('now', '-30 minutes')
               AND commence_time <= datetime('now', '+90 minutes')
               ORDER BY commence_time""",
        ).fetchall()
    return [dict(r) for r in rows]


def update_closing_odds(opp_id: str, closing_odds: float) -> Optional[float]:
    """Update closing odds and compute CLV. Returns CLV%."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT soft_odds FROM plus_ev_opportunity WHERE id = ?", (opp_id,)
        ).fetchone()
        if not row or not row["soft_odds"] or not closing_odds:
            return None
        clv = round((row["soft_odds"] / closing_odds - 1) * 100, 2)
        conn.execute(
            """UPDATE plus_ev_opportunity
               SET closing_odds = ?, clv_percent = ?, closing_fetched_at = ?
               WHERE id = ?""",
            (closing_odds, clv, dt.datetime.utcnow().isoformat() + "Z", opp_id),
        )
    return clv


def set_result(opp_id: str, result: Optional[int]) -> bool:
    """Set the manual result of a bet. result: 1=win, 0=loss, None=clear."""
    if result not in (0, 1, None):
        return False
    set_at = dt.datetime.utcnow().isoformat() + "Z" if result is not None else None
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE plus_ev_opportunity SET result = ?, result_set_at = ? WHERE id = ?",
            (result, set_at, opp_id),
        )
    return cur.rowcount > 0


def get_performance_summary() -> dict:
    """Realized performance over bets with a manual result (flat 1-unit stake)."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT
               SUM(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END)              AS resolved,
               SUM(CASE WHEN result = 1 THEN 1 ELSE 0 END)                      AS wins,
               AVG(CASE WHEN result IS NOT NULL THEN 1.0 / fair_odds END)       AS avg_pred_prob,
               AVG(CASE WHEN result IS NOT NULL
                        THEN (1.0 / fair_odds - result) * (1.0 / fair_odds - result) END)
                                                                               AS brier,
               SUM(CASE WHEN result = 1 THEN soft_odds - 1
                        WHEN result = 0 THEN -1 ELSE 0 END)                     AS profit_units
               FROM plus_ev_opportunity
               WHERE fair_odds IS NOT NULL AND fair_odds > 0"""
        ).fetchone()
    resolved = (row["resolved"] or 0) if row else 0
    wins = (row["wins"] or 0) if row else 0
    profit_units = (row["profit_units"] or 0.0) if row else 0.0
    return {
        "resolved": resolved,
        "wins": wins,
        "win_rate": round(wins / resolved * 100, 1) if resolved else None,
        "expected_win_rate": round(row["avg_pred_prob"] * 100, 1)
        if resolved and row["avg_pred_prob"] is not None else None,
        "brier": round(row["brier"], 4) if resolved and row["brier"] is not None else None,
        "profit_units": round(profit_units, 2),
        "roi_percent": round(profit_units / resolved * 100, 2) if resolved else None,
    }


def get_history(limit: int = 500) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM plus_ev_opportunity ORDER BY detected_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_clv_summary() -> dict:
    with _conn() as conn:
        row = conn.execute(
            """SELECT
               COUNT(*)                                                AS total,
               COUNT(closing_odds)                                     AS with_clv,
               ROUND(AVG(clv_percent), 2)                             AS avg_clv,
               ROUND(AVG(CASE WHEN clv_percent > 0 THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                                       AS pct_positive_clv,
               ROUND(AVG(edge_percent), 2)                            AS avg_edge
               FROM plus_ev_opportunity"""
        ).fetchone()
    return dict(row) if row else {}


def export_csv() -> str:
    rows = get_history(limit=100_000)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()

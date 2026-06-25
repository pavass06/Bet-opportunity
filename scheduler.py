"""Background job: fetch Pinnacle closing odds for tracked +EV opportunities."""

from __future__ import annotations

import logging
import os
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from config import markets_for_sport
from db import get_pending_closing, update_closing_odds
from scanner import ScannerError, fetch_odds_for_sport

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _pinnacle_closing_odds(api_key: str, sport: str, event_name: str, market: str, outcome: str) -> Optional[float]:
    """Return the current Pinnacle price for a specific event/market/outcome."""
    try:
        events = fetch_odds_for_sport(api_key, sport, markets_for_sport(sport), ["eu"])
    except ScannerError as exc:
        logger.warning("Closing odds fetch failed for %s: %s", sport, exc)
        return None

    target = event_name.lower()
    outcome_norm = outcome.strip().lower()

    for game in events:
        name = f"{game.get('away_team', '')} vs {game.get('home_team', '')}".lower()
        if name != target:
            continue
        for book in game.get("bookmakers", []):
            if book.get("key") != "pinnacle":
                continue
            for mkt in book.get("markets", []):
                if mkt.get("key") != market:
                    continue
                for oc in mkt.get("outcomes", []):
                    if (oc.get("name") or "").strip().lower() == outcome_norm:
                        price = oc.get("price")
                        return float(price) if price else None
    return None


def _run_closing_job(api_key: str) -> None:
    pending = get_pending_closing()
    if not pending:
        return
    logger.info("Closing odds job: %d pending opportunities", len(pending))
    for opp in pending:
        closing = _pinnacle_closing_odds(
            api_key,
            opp["sport"],
            opp["event"],
            opp["market"],
            opp["outcome"],
        )
        if closing:
            clv = update_closing_odds(opp["id"], closing)
            logger.info(
                "CLV %s: %s @ %.2f → closing %.2f → CLV %.2f%%",
                opp["event"], opp["outcome"], opp["soft_odds"], closing, clv or 0,
            )


def start_scheduler() -> bool:
    """Start background scheduler. Returns True if started, False if no API key."""
    global _scheduler
    if _scheduler:
        return True
    api_key = os.getenv("ODDS_API_KEY") or os.getenv("THEODDSAPI_API_KEY")
    if not api_key:
        logger.info("No API key in env — closing odds scheduler disabled")
        return False
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_run_closing_job, "interval", minutes=30, args=[api_key], id="closing_odds")
    _scheduler.start()
    logger.info("Scheduler started — closing odds fetched every 30 min")
    return True


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

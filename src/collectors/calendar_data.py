"""이벤트·캘린더 수집기 — yfinance.calendar 활용.

수집 항목:
  - 다음 실적 발표일 (Earnings Date)
  - EPS·매출 컨센서스 (예상 범위)
  - 배당 락일 (Ex-Dividend Date)
  - 배당 지급일 (Dividend Date)
  - 분할/병합 등 기업행동 (Actions)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import yfinance as yf

from src.utils.logger import logger
from src.utils.markets import to_yfinance_symbol


def fetch_calendar(symbol: str) -> dict[str, Any]:
    """yfinance.calendar — 다음 실적/배당 일정 + 컨센서스."""
    ysym = to_yfinance_symbol(symbol)
    try:
        t = yf.Ticker(ysym)
        cal = t.calendar or {}
    except Exception as e:
        logger.debug(f"yf.calendar 실패 ({ysym}): {e}")
        return {}

    earnings_dates = cal.get("Earnings Date") or []
    next_earnings = earnings_dates[0] if earnings_dates else None

    return {
        "next_earnings_date": next_earnings,
        "eps_high": _safe(cal.get("Earnings High")),
        "eps_low": _safe(cal.get("Earnings Low")),
        "eps_avg": _safe(cal.get("Earnings Average")),
        "revenue_high": _safe(cal.get("Revenue High")),
        "revenue_low": _safe(cal.get("Revenue Low")),
        "revenue_avg": _safe(cal.get("Revenue Average")),
        "ex_div_date": cal.get("Ex-Dividend Date"),
        "div_pay_date": cal.get("Dividend Date"),
    }


def days_until(target: date | None) -> int | None:
    """오늘부터 target까지 일수. 과거면 음수."""
    if not target:
        return None
    today = datetime.now().date()
    return (target - today).days


def _safe(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


__all__ = ["fetch_calendar", "days_until"]

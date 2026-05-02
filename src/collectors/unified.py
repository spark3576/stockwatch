"""통합 수집기 — 시장 자동 감지 후 적절한 수집기 호출."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.collectors.krx_collector import fetch_history_krx, fetch_info_krx
from src.collectors.yfinance_collector import fetch_history, fetch_info
from src.utils.logger import logger
from src.utils.markets import detect_market, normalize_symbol


def collect_history(symbol: str, days: int = 365) -> tuple[pd.DataFrame, str]:
    """심볼 자동 감지 → OHLCV. 반환: (DataFrame, market_code)."""
    market = detect_market(symbol)
    nsym = normalize_symbol(symbol)
    logger.info(f"수집 시작: {nsym} ({market}, {days}일)")

    if market == "KR":
        df = fetch_history_krx(nsym, days=days)
        if df.empty:
            logger.info(f"  pykrx 비어있음 → yfinance 폴백 ({nsym})")
            df = fetch_history(nsym, days=days)
    else:
        df = fetch_history(nsym, days=days)

    if df.empty:
        logger.warning(f"  데이터 없음: {nsym}")
    else:
        logger.info(f"  → {len(df)}개 일봉 ({df.index.min().date()} ~ {df.index.max().date()})")
    return df, market


def collect_info(symbol: str) -> dict[str, Any]:
    market = detect_market(symbol)
    nsym = normalize_symbol(symbol)
    if market == "KR":
        info = fetch_info_krx(nsym)
        if info["name"] is None:
            info = fetch_info(nsym)
    else:
        info = fetch_info(nsym)
    info["symbol"] = nsym
    info["market"] = market
    return info


__all__ = ["collect_history", "collect_info"]

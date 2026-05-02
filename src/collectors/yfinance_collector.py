"""yfinance 기반 글로벌 주가 수집기 (US/JP/UK/DE/KR-fallback)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from src.utils.logger import logger
from src.utils.markets import detect_market, market_info, to_yfinance_symbol


def fetch_history(symbol: str, days: int = 365) -> pd.DataFrame:
    """주가 일봉 OHLCV 조회.

    반환 DataFrame:
        index: DatetimeIndex (date)
        columns: open, high, low, close, volume
    """
    ysym = to_yfinance_symbol(symbol)
    end = datetime.now()
    start = end - timedelta(days=days)
    logger.debug(f"yfinance fetch: {ysym} ({start.date()} ~ {end.date()})")

    df = yf.download(
        ysym,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        # KR 티커는 .KS → .KQ fallback
        if ysym.endswith(".KS"):
            alt = ysym[:-3] + ".KQ"
            logger.debug(f"  → fallback to {alt}")
            df = yf.download(
                alt,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        if df is None or df.empty:
            return pd.DataFrame()

    # MultiIndex column 정규화
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Adj Close": "adj_close",
        }
    )
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].dropna(subset=["close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return df


def fetch_info(symbol: str) -> dict[str, Any]:
    """종목 메타데이터 (이름/섹터 등). 일부는 None일 수 있음."""
    ysym = to_yfinance_symbol(symbol)
    try:
        t = yf.Ticker(ysym)
        info = t.info or {}
    except Exception as e:
        logger.warning(f"info fetch 실패 ({ysym}): {e}")
        info = {}
    market = detect_market(symbol)
    mi = market_info(market)
    return {
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency") or mi.currency,
        "market": market,
    }


__all__ = ["fetch_history", "fetch_info"]

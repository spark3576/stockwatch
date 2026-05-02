"""한국 KRX 데이터 수집 (pykrx 우선, yfinance 폴백)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.utils.logger import logger


def fetch_history_krx(symbol: str, days: int = 365) -> pd.DataFrame:
    """pykrx로 KR 일봉 조회. 실패 시 빈 DataFrame."""
    try:
        from pykrx import stock as pkstock
    except ImportError:
        logger.warning("pykrx 미설치 — yfinance 폴백 사용")
        return pd.DataFrame()

    end = datetime.now()
    start = end - timedelta(days=days)
    fmt = "%Y%m%d"
    try:
        df = pkstock.get_market_ohlcv_by_date(
            start.strftime(fmt), end.strftime(fmt), symbol
        )
    except Exception as e:
        logger.warning(f"pykrx 실패 ({symbol}): {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
    )
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].dropna(subset=["close"])
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df


def fetch_info_krx(symbol: str) -> dict[str, Any]:
    """KR 종목 이름 (pykrx)."""
    try:
        from pykrx import stock as pkstock
        name = pkstock.get_market_ticker_name(symbol)
    except Exception as e:
        logger.debug(f"pykrx info 실패 ({symbol}): {e}")
        name = None
    return {
        "name": name,
        "sector": None,
        "industry": None,
        "currency": "KRW",
        "market": "KR",
    }


__all__ = ["fetch_history_krx", "fetch_info_krx"]

"""시장 지수 수집기 — 베타/상대수익률 계산용.

5개 시장의 대표 지수:
  KR: KOSPI (^KS11)
  US: S&P 500 (^GSPC)
  JP: Nikkei 225 (^N225)
  UK: FTSE 100 (^FTSE)
  DE: DAX (^GDAXI)

성능: 동일 시장 다종목 분석시 중복 호출 방지를 위해 in-memory 캐시.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.utils.logger import logger

MARKET_INDEX: dict[str, dict[str, str]] = {
    "KR": {"symbol": "^KS11", "name": "KOSPI"},
    "US": {"symbol": "^GSPC", "name": "S&P 500"},
    "JP": {"symbol": "^N225", "name": "Nikkei 225"},
    "UK": {"symbol": "^FTSE", "name": "FTSE 100"},
    "DE": {"symbol": "^GDAXI", "name": "DAX"},
}

# 무위험 이자율 추정 (연 %, 샤프 비율 계산용) — 대략적인 국채/예금 기준
RISK_FREE_RATE: dict[str, float] = {
    "KR": 0.035,
    "US": 0.045,
    "JP": 0.005,
    "UK": 0.040,
    "DE": 0.030,
}

# 모듈 레벨 캐시 (분석 세션 내 재사용)
_INDEX_CACHE: dict[str, pd.DataFrame] = {}


def fetch_market_index(market_code: str, days: int = 400) -> pd.DataFrame:
    """시장 지수 일봉 OHLCV. 캐시 적중시 즉시 반환."""
    market_code = market_code.upper()
    cache_key = f"{market_code}:{days}"
    if cache_key in _INDEX_CACHE:
        return _INDEX_CACHE[cache_key]

    info = MARKET_INDEX.get(market_code)
    if not info:
        return pd.DataFrame()

    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        df = yf.download(
            info["symbol"],
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as e:
        logger.warning(f"시장 지수 ({info['symbol']}) 수집 실패: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].dropna(subset=["close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"

    _INDEX_CACHE[cache_key] = df
    logger.debug(f"시장 지수 캐시: {info['symbol']} ({len(df)}일)")
    return df


def market_index_name(market_code: str) -> str:
    return MARKET_INDEX.get(market_code.upper(), {}).get("name", "?")


def risk_free_rate(market_code: str) -> float:
    return RISK_FREE_RATE.get(market_code.upper(), 0.03)


__all__ = ["fetch_market_index", "market_index_name", "risk_free_rate", "MARKET_INDEX"]

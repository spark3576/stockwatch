"""시장 식별/메타데이터 유틸."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketInfo:
    code: str               # KR / US / JP / UK / DE
    name: str
    timezone: str
    currency: str
    suffix: str             # yfinance suffix


_MARKETS: dict[str, MarketInfo] = {
    "KR": MarketInfo("KR", "한국 (KOSPI/KOSDAQ)", "Asia/Seoul", "KRW", ".KS"),
    "US": MarketInfo("US", "미국 (NASDAQ/NYSE)", "America/New_York", "USD", ""),
    "JP": MarketInfo("JP", "일본 (TSE)", "Asia/Tokyo", "JPY", ".T"),
    "UK": MarketInfo("UK", "영국 (LSE)", "Europe/London", "GBP", ".L"),
    "DE": MarketInfo("DE", "독일 (Xetra)", "Europe/Berlin", "EUR", ".DE"),
}


def detect_market(symbol: str) -> str:
    """종목 코드/티커에서 시장 자동 감지.

    - 6자리 숫자(앞뒤 공백 제거 후) → KR
    - .T 끝 → JP
    - .L 끝 → UK
    - .DE 끝 → DE
    - 그 외 알파벳 → US
    """
    s = symbol.strip().upper()
    if re.fullmatch(r"\d{6}", s):
        return "KR"
    if s.endswith(".T"):
        return "JP"
    if s.endswith(".L"):
        return "UK"
    if s.endswith(".DE"):
        return "DE"
    if s.endswith(".KS") or s.endswith(".KQ"):
        return "KR"
    return "US"


def market_info(code: str) -> MarketInfo:
    return _MARKETS[code.upper()]


def all_markets() -> list[MarketInfo]:
    return list(_MARKETS.values())


def to_yfinance_symbol(symbol: str) -> str:
    """국내 6자리 코드는 yfinance에선 .KS/.KQ 필요. 단순화: 일단 .KS 시도."""
    s = symbol.strip().upper()
    market = detect_market(s)
    if market == "KR" and re.fullmatch(r"\d{6}", s):
        # KOSPI/KOSDAQ 구분이 어려운 경우 .KS로 시도, 실패시 .KQ
        return f"{s}.KS"
    return s


def normalize_symbol(symbol: str) -> str:
    """저장용 정규화: 한국은 6자리, 글로벌은 그대로."""
    s = symbol.strip().upper()
    if s.endswith(".KS") or s.endswith(".KQ"):
        return s.split(".")[0]
    return s


__all__ = [
    "MarketInfo",
    "detect_market",
    "market_info",
    "all_markets",
    "to_yfinance_symbol",
    "normalize_symbol",
]

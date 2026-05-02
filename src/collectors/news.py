"""뉴스 수집기 — yfinance.news 활용.

각 뉴스: title, publisher, published_at, link, summary(있을 때)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from src.utils.logger import logger
from src.utils.markets import to_yfinance_symbol


def fetch_news(symbol: str, max_items: int = 10, days: int = 3) -> list[dict]:
    """최근 N일 뉴스 (최대 max_items건). 시간 역순.

    반환 dict 키: title, publisher, published_at(ISO), link, summary
    """
    ysym = to_yfinance_symbol(symbol)
    try:
        t = yf.Ticker(ysym)
        raw = t.news or []
    except Exception as e:
        logger.warning(f"yfinance.news 실패 ({ysym}): {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items: list[dict] = []
    for n in raw:
        # yfinance 새 포맷 (2024+): {'id': ..., 'content': {...}}
        # 구포맷: 평면 dict
        c = n.get("content") if isinstance(n.get("content"), dict) else n

        title = c.get("title") or ""
        if not title:
            continue

        # 시간 파싱
        pub_str = c.get("pubDate") or c.get("providerPublishTime") or ""
        pub_dt = _parse_pub(pub_str)
        if pub_dt and pub_dt < cutoff:
            continue

        # provider/publisher
        provider = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher")
        provider = provider or "?"

        # 링크
        link = ""
        if c.get("canonicalUrl"):
            link = c["canonicalUrl"].get("url", "") if isinstance(c["canonicalUrl"], dict) else c.get("canonicalUrl", "")
        if not link:
            link = c.get("link", "") or ""

        # 요약
        summary = c.get("summary") or c.get("description") or ""

        items.append({
            "title": title,
            "publisher": provider,
            "published_at": pub_dt.isoformat() if pub_dt else pub_str,
            "link": link,
            "summary": summary[:500] if summary else "",
        })
        if len(items) >= max_items:
            break

    return items


def _parse_pub(s: str) -> datetime | None:
    if not s:
        return None
    if isinstance(s, (int, float)):
        try:
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        except Exception:
            return None
    try:
        # ISO 형태 (예: 2026-05-01T11:27:21Z)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        # 유닉스 타임스탬프 문자열
        return datetime.fromtimestamp(int(s), tz=timezone.utc)
    except Exception:
        return None


__all__ = ["fetch_news"]

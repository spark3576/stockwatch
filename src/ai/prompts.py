"""AI 시그널 프롬프트 빌더.

각 시그널마다 Claude(cokacdir cron 세션)에게 보낼 데이터+지시문을 구성.
"역할 부여" 대신 "데이터 처리 작업"으로 프레이밍 — Claude Code 통과.
"""
from __future__ import annotations

import json
from typing import Any


def build_fact_hunter_prompt(
    name: str, symbol: str, market: str, price: float, currency: str,
    change_5d_pct: float, news: list[dict],
) -> str:
    """팩트헌터 — 최근 72시간 뉴스 분석."""
    news_lines = []
    for i, n in enumerate(news[:10], 1):
        title = n.get("title", "?")[:200]
        pub = (n.get("published_at") or "?").split("T")[0]
        publisher = n.get("publisher", "?")
        summary = n.get("summary", "")[:300]
        line = f"[{i}] {pub} | {publisher} | {title}"
        if summary:
            line += f"\n    요약: {summary}"
        news_lines.append(line)
    news_text = "\n".join(news_lines) if news_lines else "(뉴스 없음)"

    return f"""다음은 주식 종목 분석 데이터 처리 작업입니다. 입력 JSON 형식으로 결과를 출력해주세요.

== 입력 데이터 ==
종목: {name}
심볼: {symbol} ({market})
현재 가격: {price:,.2f} {currency}
최근 5일 변동: {change_5d_pct:+.1f}%

뉴스 ({len(news)}건, 최근 72시간):
{news_text}

== 출력 형식 ==
다음 JSON 스키마로 결과를 출력해주세요. JSON 외 다른 텍스트는 포함하지 마세요.

{{
  "summary": "한국어 한 줄 요약 (40자 이내)",
  "checks": [
    {{"name": "호재 뉴스 강도", "verdict": "↑|↓|△", "reason": "근거 1줄"}},
    {{"name": "악재 뉴스 강도", "verdict": "↑|↓|△", "reason": "근거 1줄"}},
    {{"name": "사실 검증", "verdict": "↑|↓|△", "reason": "조작·날짜 변경 의심 여부"}},
    {{"name": "시장 반응 일치도", "verdict": "↑|↓|△", "reason": "뉴스가 가격에 반영됐는지"}},
    {{"name": "단기 전망 (1주)", "verdict": "↑|↓|△", "reason": "근거 1줄"}},
    {{"name": "장기 전망 (1개월)", "verdict": "↑|↓|△", "reason": "근거 1줄"}}
  ]
}}

판정 기준:
- ↑ : 명확한 호재 / 매수 우호 신호
- ↓ : 명확한 악재 / 매도 우려 신호
- △ : 중립 / 정보 부족 / 양방향 혼재

뉴스가 5건 미만이거나 종목과 직접 관련 없는 일반 뉴스라면 모든 항목 △ 처리.
"""


def build_why_engine_prompt(
    name: str, symbol: str, market: str,
    today_change_pct: float, change_3d_pct: float,
    today_volume_ratio: float,
    market_change_pct: float | None,
    sector_change_pct: float | None,
    news: list[dict],
) -> str:
    """Why 엔진 — 가격 변동 원인 추적."""
    news_lines = []
    for i, n in enumerate(news[:6], 1):
        title = n.get("title", "?")[:200]
        pub = (n.get("published_at") or "?").split("T")[0]
        news_lines.append(f"[{i}] {pub} | {title}")
    news_text = "\n".join(news_lines) if news_lines else "(뉴스 없음)"

    market_str = f"{market_change_pct:+.1f}%" if market_change_pct is not None else "?"
    sector_str = f"{sector_change_pct:+.1f}%" if sector_change_pct is not None else "?"

    return f"""다음은 주식 가격 변동 원인 분석 데이터 처리 작업입니다.

== 입력 데이터 ==
종목: {name} ({symbol}, {market})
당일 가격 변동: {today_change_pct:+.2f}%
3일 누적 변동: {change_3d_pct:+.2f}%
당일 거래량 / 5일 평균: {today_volume_ratio:.2f}x
시장 지수 당일: {market_str}
섹터 ETF 당일: {sector_str}

최근 뉴스 ({len(news)}건):
{news_text}

== 출력 형식 ==
다음 JSON으로 결과를 출력해주세요.

{{
  "summary": "왜 움직였는지 한 줄 (40자 이내)",
  "primary_cause": "news|market|sector|technical|unknown",
  "checks": [
    {{"name": "변동 크기", "verdict": "↑|↓|△", "reason": "유의미한 변동인지"}},
    {{"name": "뉴스 원인", "verdict": "↑|↓|△", "reason": "뉴스로 설명되는지"}},
    {{"name": "시장 동조", "verdict": "↑|↓|△", "reason": "시장 전체와 같은 방향인지"}},
    {{"name": "섹터 동조", "verdict": "↑|↓|△", "reason": "섹터와 같은 방향인지"}},
    {{"name": "거래량 동반", "verdict": "↑|↓|△", "reason": "유의미한 거래량 동반"}},
    {{"name": "추세 일관성", "verdict": "↑|↓|△", "reason": "단기 추세 유지/전환"}}
  ]
}}

판정:
- ↑ : 변동이 명확한 원인으로 설명됨 / 추세 강화
- ↓ : 변동이 부정적 원인 / 추세 약화
- △ : 원인 불명확 / 영향 미미

가격 변동이 1% 미만이면 모든 항목 △ 처리.
"""


def build_global_macro_prompt(
    name: str, symbol: str, market: str, sector: str | None,
    market_index_change_5d: float | None,
    fomc_d_day: int | None, cpi_d_day: int | None,
    related_news: list[dict],
) -> str:
    """글로벌 팩트헌터 — 거시·섹터 이슈 영향."""
    news_lines = []
    for i, n in enumerate(related_news[:8], 1):
        title = n.get("title", "?")[:200]
        pub = (n.get("published_at") or "?").split("T")[0]
        news_lines.append(f"[{i}] {pub} | {title}")
    news_text = "\n".join(news_lines) if news_lines else "(뉴스 없음)"

    market_str = f"{market_index_change_5d:+.1f}%" if market_index_change_5d is not None else "?"

    return f"""다음은 주식 종목의 거시·섹터 영향 분석 데이터 처리 작업입니다.

== 입력 데이터 ==
종목: {name} ({symbol}, {market})
섹터: {sector or "?"}
시장 지수 5일 변동: {market_str}
FOMC 다음 회의: D-{fomc_d_day if fomc_d_day is not None else "?"}
다음 CPI 발표: D-{cpi_d_day if cpi_d_day is not None else "?"}

관련 뉴스 ({len(related_news)}건):
{news_text}

== 출력 형식 ==
{{
  "summary": "거시·섹터 환경 한 줄 (50자 이내)",
  "checks": [
    {{"name": "글로벌 시장 트렌드", "verdict": "↑|↓|△", "reason": "전반적 위험선호/회피"}},
    {{"name": "섹터 강도", "verdict": "↑|↓|△", "reason": "본 종목 섹터의 단기 흐름"}},
    {{"name": "환율·금리 영향", "verdict": "↑|↓|△", "reason": "해당 시장 통화·금리 영향"}},
    {{"name": "지정학 리스크", "verdict": "↑|↓|△", "reason": "전쟁·제재·정책 리스크"}},
    {{"name": "매크로 이벤트 임박", "verdict": "↑|↓|△", "reason": "FOMC/CPI/실적 시즌 임팩트"}},
    {{"name": "동종 글로벌 비교", "verdict": "↑|↓|△", "reason": "타 시장 동종업계 동향"}}
  ]
}}

판정:
- ↑ : 종목에 우호적 거시 환경
- ↓ : 종목에 부정적 거시 환경
- △ : 중립 / 영향 적음
"""


__all__ = ["build_fact_hunter_prompt", "build_why_engine_prompt", "build_global_macro_prompt"]

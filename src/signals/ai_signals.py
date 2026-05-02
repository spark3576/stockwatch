"""AI 시그널 3종 — 팩트헌터 / Why엔진 / 글로벌 팩트헌터.

설계: Python 시그널은 ai_signals 캐시 테이블에서 결과를 읽기만 함.
실제 AI 분석은 cokacdir cron Claude 세션이 수행 → DB에 저장.

캐시 미스 시 placeholder 결과 반환 (모두 △, "AI 분석 대기" 메시지).
"""
from __future__ import annotations

import pandas as pd

from src.db.manager import DB
from src.signals.base import Signal, SignalResult


class _AISignalBase(Signal):
    """AI 시그널 공통 베이스. ai_signals 테이블에서 결과 조회."""

    db_key: str = ""           # 'fact_hunter' / 'why_engine' / 'global_macro'
    placeholder_checks: list[str] = []
    max_age_hours: int = 24

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        db = DB()
        cached = db.get_latest_ai_signal(
            symbol=symbol, market=market, signal_type=self.db_key,
            max_age_hours=self.max_age_hours,
        )
        if cached:
            payload = cached.get("payload") or {}
            return SignalResult(
                signal_type=self.name,
                score_up=cached["score_up"],
                score_down=cached["score_down"],
                score_neut=cached["score_neut"],
                summary=cached.get("summary") or "분석 완료",
                details={
                    "checks": payload.get("checks", []),
                    "generated_at": cached.get("generated_at"),
                    "ai_payload": {k: v for k, v in payload.items() if k != "checks"},
                },
            )

        # 캐시 미스: placeholder
        placeholder = [
            {"name": n, "verdict": "△", "reason": "AI 분석 대기 (다음 cron 시 자동 갱신)"}
            for n in self.placeholder_checks
        ]
        return SignalResult(
            signal_type=self.name,
            score_neut=len(placeholder),
            summary="🕒 AI 분석 대기",
            details={"checks": placeholder, "cached": False},
        )


class FactHunter(_AISignalBase):
    name = "팩트헌터"
    db_key = "fact_hunter"
    placeholder_checks = [
        "호재 뉴스 강도", "악재 뉴스 강도", "사실 검증",
        "시장 반응 일치도", "단기 전망 (1주)", "장기 전망 (1개월)",
    ]


class WhyEngine(_AISignalBase):
    name = "Why 엔진"
    db_key = "why_engine"
    placeholder_checks = [
        "변동 크기", "뉴스 원인", "시장 동조",
        "섹터 동조", "거래량 동반", "추세 일관성",
    ]


class GlobalMacro(_AISignalBase):
    name = "글로벌 팩트헌터"
    db_key = "global_macro"
    placeholder_checks = [
        "글로벌 시장 트렌드", "섹터 강도", "환율·금리 영향",
        "지정학 리스크", "매크로 이벤트 임박", "동종 글로벌 비교",
    ]


__all__ = ["FactHunter", "WhyEngine", "GlobalMacro"]

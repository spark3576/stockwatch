"""통합 종합 카드 — 5개 시그널 결과를 1개의 카드로 합산.

기능:
  - 5개 시그널의 ↑/↓/△ 점수 합산
  - 시그널별 핵심 강점/약점 자동 추출 (다양성 보장)
  - 리스크 점수 계산 (0~100, 변동성+부채+MDD+PER 종합)
  - 룰 기반 한줄 요약 생성 (AI 없음)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.signals.base import SignalResult


@dataclass
class CompositeCard:
    """5개 시그널 통합 카드 (DB 저장 단위)."""
    symbol: str
    market: str
    name: str
    issued_at: datetime
    issue_price: float
    currency: str

    signals: list[SignalResult]

    total_up: int = 0
    total_down: int = 0
    total_neut: int = 0
    overall_verdict: str = ""           # 🟢 강한 상승 / 🟡 혼조 / 🔴 하락
    overall_emoji: str = "🟡"

    strengths: list[dict] = field(default_factory=list)   # 핵심 ↑ 체크 (다양성)
    weaknesses: list[dict] = field(default_factory=list)  # 핵심 ↓ 체크

    risk_score: int = 0                 # 0~100
    risk_level: str = ""                # 낮음/보통/높음/매우 높음
    risk_factors: list[str] = field(default_factory=list)

    summary_oneliner: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "name": self.name,
            "issued_at": self.issued_at.isoformat(),
            "issue_price": self.issue_price,
            "currency": self.currency,
            "scores": {
                "up": self.total_up,
                "down": self.total_down,
                "neut": self.total_neut,
            },
            "verdict": self.overall_verdict,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "summary": self.summary_oneliner,
            "signals": [s.to_dict() for s in self.signals],
        }


def build_card(
    symbol: str,
    market: str,
    name: str,
    issue_price: float,
    currency: str,
    signals: list[SignalResult],
) -> CompositeCard:
    """시그널 리스트로부터 통합 카드 생성."""
    card = CompositeCard(
        symbol=symbol, market=market, name=name,
        issued_at=datetime.now(),
        issue_price=issue_price, currency=currency,
        signals=signals,
    )

    # 1. 점수 합산 (체크 수에 자동 스케일 — 비율 기반)
    card.total_up = sum(s.score_up for s in signals)
    card.total_down = sum(s.score_down for s in signals)
    card.total_neut = sum(s.score_neut for s in signals)
    total_checks = card.total_up + card.total_down + card.total_neut
    net = card.total_up - card.total_down
    # 비율: -1.0 ~ +1.0 (체크 수에 무관)
    net_ratio = (net / total_checks) if total_checks > 0 else 0.0
    # 결정성 (decisiveness): △가 적을수록 명확한 신호
    decisive = ((card.total_up + card.total_down) / total_checks) if total_checks > 0 else 0.0

    # 비율 기반 + 결정성 보정
    if net_ratio >= 0.40:
        card.overall_verdict = "강한 상승"
        card.overall_emoji = "🟢🟢"
    elif net_ratio >= 0.20:
        card.overall_verdict = "상승 우위"
        card.overall_emoji = "🟢"
    elif net_ratio >= 0.08 and decisive >= 0.5:
        card.overall_verdict = "약한 상승"
        card.overall_emoji = "🟢"
    elif net_ratio <= -0.40:
        card.overall_verdict = "강한 하락"
        card.overall_emoji = "🔴🔴"
    elif net_ratio <= -0.20:
        card.overall_verdict = "하락 우위"
        card.overall_emoji = "🔴"
    elif net_ratio <= -0.08 and decisive >= 0.5:
        card.overall_verdict = "약한 하락"
        card.overall_emoji = "🔴"
    else:
        card.overall_verdict = "혼조 / 방향성 불분명"
        card.overall_emoji = "🟡"

    # 2. 강점/약점 추출
    all_checks: list[dict] = []
    for sig in signals:
        for chk in sig.details.get("checks", []):
            all_checks.append({**chk, "signal": sig.signal_type})

    ups = [c for c in all_checks if c["verdict"] == "↑"]
    downs = [c for c in all_checks if c["verdict"] == "↓"]

    card.strengths = _pick_diverse(ups, n=5)
    card.weaknesses = _pick_diverse(downs, n=5)

    # 3. 리스크 점수
    card.risk_score, card.risk_factors = _compute_risk(signals)
    if card.risk_score >= 70:
        card.risk_level = "매우 높음"
    elif card.risk_score >= 50:
        card.risk_level = "높음"
    elif card.risk_score >= 30:
        card.risk_level = "보통"
    else:
        card.risk_level = "낮음"

    # 4. 한줄 요약
    card.summary_oneliner = _build_oneliner(card)

    return card


def _pick_diverse(checks: list[dict], n: int = 5) -> list[dict]:
    """시그널 타입별로 다양성 보장 + N개 선택."""
    seen_sigs: set[str] = set()
    result: list[dict] = []
    # 1차 패스: 시그널별 1개씩
    for c in checks:
        sig = c["signal"]
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            result.append(c)
            if len(result) >= n:
                return result
    # 2차 패스: 나머지
    for c in checks:
        if c not in result:
            result.append(c)
            if len(result) >= n:
                return result
    return result


def _compute_risk(signals: list[SignalResult]) -> tuple[int, list[str]]:
    """0~100 리스크 점수 + 리스크 요인 리스트."""
    score = 0
    factors: list[str] = []

    for sig in signals:
        for chk in sig.details.get("checks", []):
            name = chk.get("name", "")
            reason = chk.get("reason", "")

            # --- 퀀트 팩터 ---
            if "연환산 변동성" in name:
                m = re.search(r"60일 (\d+)%", reason)
                if m:
                    vol = int(m.group(1))
                    if vol >= 60:
                        score += 25
                        factors.append(f"변동성 {vol}% (매우 높음)")
                    elif vol >= 45:
                        score += 15
                        factors.append(f"변동성 {vol}% (높음)")
                    elif vol >= 35:
                        score += 8
            elif "최대 낙폭" in name:
                m = re.search(r"-(\d+\.\d+)%", reason)
                if m:
                    mdd = float(m.group(1))
                    if mdd >= 35:
                        score += 25
                        factors.append(f"MDD -{mdd:.0f}% (큰 손실 경험)")
                    elif mdd >= 20:
                        score += 12
                        factors.append(f"MDD -{mdd:.0f}%")
            elif name == "베타":
                m = re.search(r"(\d+\.\d+)", reason)
                if m:
                    beta = float(m.group(1))
                    if beta >= 1.8:
                        score += 12
                        factors.append(f"베타 {beta:.2f} (시장 변동성 1.8x↑)")
                    elif beta >= 1.4:
                        score += 6
            elif "VaR 95%" in name:
                m = re.search(r"-([\d.]+)%", reason)
                if m:
                    var = float(m.group(1))
                    if var >= 4:
                        score += 12
                        factors.append(f"VaR -{var:.1f}%")

            # --- 재무 분석 ---
            elif name == "부채비율 (D/E)":
                m = re.search(r"(\d+)%", reason)
                if m:
                    de = int(m.group(1))
                    if de >= 200:
                        score += 20
                        factors.append(f"부채비율 {de}% (위험)")
                    elif de >= 100:
                        score += 10
                        factors.append(f"부채비율 {de}% (높음)")
            elif name == "PER (TTM)":
                m = re.search(r"^(\d+\.\d+)", reason)
                if m:
                    per = float(m.group(1))
                    if per >= 60:
                        score += 12
                        factors.append(f"PER {per:.0f} (버블 위험)")
                    elif per >= 40:
                        score += 6
            elif name == "EV/EBITDA":
                m = re.search(r"^(\d+\.\d+)", reason)
                if m:
                    ev = float(m.group(1))
                    if ev >= 30:
                        score += 8
            # --- 현금흐름 (이익의 질) ---
            elif name == "FCF 수익률":
                m = re.search(r"([\-\+]?\d+\.\d+)%", reason)
                if m:
                    fy = float(m.group(1))
                    if fy < -5:
                        score += 15
                        factors.append(f"FCF 수익률 {fy:+.1f}% (잉여현금 큰 적자)")
                    elif fy < 0:
                        score += 8
                        factors.append(f"FCF 수익률 {fy:+.1f}% (잉여현금 적자)")
            elif name == "OCF vs 순이익":
                m = re.search(r"(\d+\.\d+)배", reason)
                if m:
                    ratio = float(m.group(1))
                    if ratio < 0.3:
                        score += 15
                        factors.append(f"OCF/NI {ratio:.2f} (현금 전환 거의 없음)")
                    elif ratio < 0.7:
                        score += 8
                        factors.append(f"OCF/NI {ratio:.2f} (이익↔현금 괴리)")
            elif name == "FCF 성장 (YoY)":
                m = re.search(r"([\-\+]?\d+\.\d+)%", reason)
                if m:
                    fg = float(m.group(1))
                    if fg < -50:
                        score += 10
                        factors.append(f"FCF {fg:+.0f}% (현금흐름 급감)")

    return min(score, 100), factors


def _build_oneliner(card: CompositeCard) -> str:
    """룰 기반 한줄 요약 (시그널별 강도 + 리스크 종합)."""
    risk = card.risk_score
    total = card.total_up + card.total_down + card.total_neut
    net_ratio = (card.total_up - card.total_down) / total if total > 0 else 0

    # 시그널별 점수 인덱스
    sig_net: dict[str, int] = {}
    for sig in card.signals:
        sig_net[sig.signal_type] = sig.score_up - sig.score_down

    chart = sig_net.get("차트 시그널", 0) + sig_net.get("차트 패턴", 0)
    breakout = sig_net.get("돌파 차트", 0)
    flow = sig_net.get("머니플로우", 0)
    quant = sig_net.get("퀀트 팩터", 0)
    fin = sig_net.get("재무 분석", 0)

    # 강한 강세 (재무+퀀트+기술 모두 우수)
    if net_ratio >= 0.45 and fin >= 5 and quant >= 3 and risk < 35:
        return "🟢🟢 다지표 + 재무 + 알파 모두 우수 — 우량 종목 (위험도 낮음)"
    if net_ratio >= 0.40 and fin >= 5 and risk < 50:
        return "🟢🟢 강한 강세 + 재무 우량 — 매수 후보 (관심 등록)"
    if net_ratio >= 0.35 and quant >= 4:
        return "🟢 시장 초과수익 + 추세 일치 — 모멘텀 매매 후보"
    if net_ratio >= 0.30 and breakout >= 2 and flow >= 2:
        return "🟢 돌파 임박 + 자금 유입 — 진입 시점 모니터링"
    if net_ratio >= 0.25 and risk >= 60:
        return "🟡 강세지만 변동성·재무 위험 — 비중 조절 / 단기 매매"
    if net_ratio >= 0.20:
        return "🟢 상승 우위 — 추세 추종 매매 후보"

    # 강한 약세
    if net_ratio <= -0.40 and fin <= -5:
        return "🔴🔴 다지표 + 재무 모두 부진 — 매수 회피 / 보유 시 손절"
    if net_ratio <= -0.35:
        return "🔴 다지표 약세 — 신규 진입 비추천"
    if net_ratio <= -0.25 and risk >= 60:
        return "🔴 약세 + 위험 누적 — 회피 권장"
    if net_ratio <= -0.15:
        return "🔴 하락 우위 — 모멘텀 약화"

    # 특수 케이스
    if risk >= 70:
        return "⚠️ 위험도 매우 높음 — 더 많은 정보 없이는 부적합"
    if fin >= 6 and chart < 0:
        return "🟡 재무는 우량하나 기술적 약세 — 가치 투자 관점만 유효"
    if quant >= 4 and fin <= -2:
        return "🟡 단기 모멘텀 강하나 재무 부실 — 추격매수 신중히"

    return "🟡 혼조세 — 추가 시그널·뉴스 확인 필요"


def detect_card_changes(prev_card_dict: dict, curr_card: "CompositeCard") -> list[dict]:
    """이전 카드(dict) vs 현재 카드(객체) 비교 → 의미있는 변화 추출.

    감지 항목:
      1. 종합 판정 변경 (verdict)
      2. 리스크 레벨 변경
      3. 개별 시그널 net 점수 변동 (절대값 ≥ 3)
      4. 가격 변동 (이전 발행가 대비)
    """
    changes: list[dict] = []

    # 1. 종합 판정
    prev_verdict = prev_card_dict.get("verdict") or ""
    curr_verdict = curr_card.overall_verdict
    if prev_verdict and prev_verdict != curr_verdict:
        # 방향 평가
        prev_dir = _verdict_direction(prev_verdict)
        curr_dir = _verdict_direction(curr_verdict)
        if prev_dir != curr_dir:
            severity = "major"
        else:
            severity = "minor"
        changes.append({
            "type": "verdict",
            "severity": severity,
            "from": prev_verdict,
            "to": curr_verdict,
        })

    # 2. 리스크 레벨
    prev_risk = prev_card_dict.get("risk_level") or ""
    curr_risk = curr_card.risk_level
    risk_order = {"낮음": 0, "보통": 1, "높음": 2, "매우 높음": 3}
    if prev_risk and prev_risk != curr_risk:
        delta = risk_order.get(curr_risk, 0) - risk_order.get(prev_risk, 0)
        if abs(delta) >= 1:
            changes.append({
                "type": "risk",
                "from": prev_risk,
                "to": curr_risk,
                "direction": "up" if delta > 0 else "down",
            })

    # 3. 시그널별 net 점수 (≥3 변동)
    prev_signals = {s.get("signal_type"): s for s in prev_card_dict.get("signals", [])}
    for sig in curr_card.signals:
        prev_s = prev_signals.get(sig.signal_type)
        if not prev_s:
            continue
        prev_net = (prev_s.get("score_up", 0) or 0) - (prev_s.get("score_down", 0) or 0)
        curr_net = sig.score_up - sig.score_down
        delta = curr_net - prev_net
        if abs(delta) >= 3:
            changes.append({
                "type": "signal",
                "signal_name": sig.signal_type,
                "delta": delta,
                "prev": f"↑{prev_s.get('score_up',0)} ↓{prev_s.get('score_down',0)}",
                "curr": f"↑{sig.score_up} ↓{sig.score_down}",
            })

    # 4. 가격 변동 (≥5%)
    prev_price = prev_card_dict.get("issue_price")
    curr_price = curr_card.issue_price
    if prev_price and curr_price and prev_price > 0:
        pct = (curr_price / prev_price - 1) * 100
        if abs(pct) >= 5:
            changes.append({
                "type": "price",
                "prev": prev_price,
                "curr": curr_price,
                "pct": pct,
            })

    return changes


def _verdict_direction(verdict: str) -> str:
    """판정 → 방향 (up/down/neutral)."""
    if "상승" in verdict:
        return "up"
    if "하락" in verdict:
        return "down"
    return "neutral"


__all__ = ["CompositeCard", "build_card", "detect_card_changes"]

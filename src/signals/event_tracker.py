"""이벤트 추적 시그널 — 임박한 실적/배당/매크로 이벤트.

8개 체크:
  1. 실적 발표 임박도 (D-day까지 거리)
  2. EPS 컨센서스 범위 (애널리스트 예상)
  3. 매출 컨센서스 범위
  4. 배당 락일 임박도
  5. 배당 지급일 임박도
  6. (US) FOMC 임박 (하드코딩된 일정)
  7. (US) CPI/PPI 임박 (월간 발표)
  8. 종합 이벤트 위험도 (≤7일 내 주요 이벤트 합산)

데이터 소스:
  - yfinance.calendar (실적·배당)
  - 하드코딩 매크로 캘린더 (FOMC ~8회/년, CPI 매월)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from src.collectors.calendar_data import days_until, fetch_calendar
from src.signals.base import Signal, SignalResult


# 2026년 FOMC 회의 일정 (실제 공식 일정, 매년 갱신 필요)
FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]

# CPI는 매월 둘째 주 화/수
def _next_cpi_date() -> date:
    """다음 CPI 발표 추정 (매월 둘째 주 수요일 근사)."""
    today = datetime.now().date()
    year, month = today.year, today.month
    # 이번 달 둘째 주 수요일
    d = date(year, month, 1)
    # 첫 수요일 찾기
    while d.weekday() != 2:  # 0=Mon, 2=Wed
        d += timedelta(days=1)
    second_wed = d + timedelta(days=7)
    if second_wed >= today:
        return second_wed
    # 다음 달
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    d = date(year, month, 1)
    while d.weekday() != 2:
        d += timedelta(days=1)
    return d + timedelta(days=7)


def _v_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _v_dn(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _v_n(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class EventTracker(Signal):
    name = "이벤트 추적"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        cal = fetch_calendar(symbol)
        checks: list[dict] = []
        up = down = neut = 0

        def add(check: dict) -> None:
            nonlocal up, down, neut
            if check["verdict"] == "↑":
                up += 1
            elif check["verdict"] == "↓":
                down += 1
            else:
                neut += 1
            checks.append(check)

        # 1: 실적 발표 임박도
        next_earn = cal.get("next_earnings_date")
        d_earn = days_until(next_earn) if next_earn else None
        if d_earn is None:
            add(_v_n("실적 발표 일정", "데이터 없음"))
        elif d_earn < 0:
            # 최근 실적 (지난 30일)
            if d_earn >= -30:
                add(_v_n("실적 발표 일정", f"{abs(d_earn)}일 전 실적 발표 ({next_earn})"))
            else:
                add(_v_n("실적 발표 일정", f"다음 실적 미정 (마지막 {next_earn})"))
        elif d_earn <= 3:
            add(_v_dn("실적 발표 임박", f"D-{d_earn} ({next_earn}) — 변동성 폭발 예상"))
        elif d_earn <= 7:
            add(_v_n("실적 발표 임박", f"D-{d_earn} ({next_earn}) — 1주일 이내 주의"))
        elif d_earn <= 14:
            add(_v_n("실적 발표 예정", f"D-{d_earn} ({next_earn})"))
        elif d_earn <= 30:
            add(_v_n("실적 발표 예정", f"D-{d_earn} ({next_earn}) — 1개월 이내"))
        else:
            add(_v_n("실적 발표 일정", f"D-{d_earn} ({next_earn}) — 멀리"))

        # 2: EPS 컨센서스 범위
        eps_low = cal.get("eps_low")
        eps_high = cal.get("eps_high")
        eps_avg = cal.get("eps_avg")
        if eps_low and eps_high and eps_avg:
            range_pct = ((eps_high - eps_low) / abs(eps_avg)) * 100 if eps_avg != 0 else 0
            if range_pct < 10:
                add(_v_up("EPS 컨센서스",
                         f"평균 {eps_avg:.2f} (범위 {eps_low:.2f}~{eps_high:.2f}, ±{range_pct/2:.1f}% 합치)"))
            elif range_pct < 25:
                add(_v_n("EPS 컨센서스",
                        f"평균 {eps_avg:.2f} (범위 {eps_low:.2f}~{eps_high:.2f}, ±{range_pct/2:.1f}% 분산)"))
            else:
                add(_v_dn("EPS 컨센서스",
                         f"평균 {eps_avg:.2f} (범위 {eps_low:.2f}~{eps_high:.2f}, ±{range_pct/2:.1f}% 큰 분산 — 불확실성)"))
        else:
            add(_v_n("EPS 컨센서스", "데이터 없음"))

        # 3: 매출 컨센서스
        rev_low = cal.get("revenue_low")
        rev_high = cal.get("revenue_high")
        rev_avg = cal.get("revenue_avg")
        if rev_low and rev_high and rev_avg:
            range_pct = ((rev_high - rev_low) / abs(rev_avg)) * 100 if rev_avg != 0 else 0
            avg_str = _format_large_number(rev_avg)
            if range_pct < 8:
                add(_v_up("매출 컨센서스", f"평균 {avg_str} (±{range_pct/2:.1f}% 합치)"))
            elif range_pct < 20:
                add(_v_n("매출 컨센서스", f"평균 {avg_str} (±{range_pct/2:.1f}% 분산)"))
            else:
                add(_v_dn("매출 컨센서스", f"평균 {avg_str} (±{range_pct/2:.1f}% 큰 분산)"))
        else:
            add(_v_n("매출 컨센서스", "데이터 없음"))

        # 4: 배당 락일 임박도
        ex_div = cal.get("ex_div_date")
        d_exdiv = days_until(ex_div) if ex_div else None
        if d_exdiv is None:
            add(_v_n("배당 락일", "무배당 또는 데이터 없음"))
        elif 0 < d_exdiv <= 7:
            add(_v_up("배당 락일 임박", f"D-{d_exdiv} ({ex_div}) — 매수자 권리 기간"))
        elif 0 < d_exdiv <= 30:
            add(_v_n("배당 락일", f"D-{d_exdiv} ({ex_div})"))
        elif d_exdiv > 30:
            add(_v_n("배당 락일", f"D-{d_exdiv} ({ex_div}) — 멀리"))
        else:
            add(_v_n("배당 락일", f"{abs(d_exdiv)}일 전 ({ex_div})"))

        # 5: 배당 지급일
        pay_div = cal.get("div_pay_date")
        d_pay = days_until(pay_div) if pay_div else None
        if d_pay is None:
            add(_v_n("배당 지급일", "데이터 없음"))
        elif 0 < d_pay <= 30:
            add(_v_n("배당 지급일", f"D-{d_pay} ({pay_div})"))
        elif d_pay < 0:
            add(_v_n("배당 지급일", f"{abs(d_pay)}일 전 ({pay_div})"))
        else:
            add(_v_n("배당 지급일", f"D-{d_pay} ({pay_div})"))

        # 6: FOMC 임박 (US/글로벌 영향)
        next_fomc = _next_macro_date(FOMC_DATES_2026)
        d_fomc = days_until(next_fomc) if next_fomc else None
        if d_fomc is None:
            add(_v_n("FOMC", "일정 미입력"))
        elif d_fomc <= 3:
            add(_v_dn("FOMC 임박", f"D-{d_fomc} ({next_fomc}) — 시장 변동성 ↑"))
        elif d_fomc <= 7:
            add(_v_n("FOMC 임박", f"D-{d_fomc} ({next_fomc})"))
        elif d_fomc <= 14:
            add(_v_n("FOMC 예정", f"D-{d_fomc} ({next_fomc})"))
        else:
            add(_v_n("FOMC", f"D-{d_fomc} ({next_fomc})"))

        # 7: CPI 임박 (US 인플레이션 발표)
        next_cpi = _next_cpi_date()
        d_cpi = days_until(next_cpi)
        if d_cpi is None:
            add(_v_n("CPI", "일정 미정"))
        elif d_cpi <= 3:
            add(_v_dn("CPI 임박", f"D-{d_cpi} ({next_cpi}) — 인플레 노출"))
        elif d_cpi <= 7:
            add(_v_n("CPI 임박", f"D-{d_cpi} ({next_cpi})"))
        else:
            add(_v_n("CPI", f"D-{d_cpi} ({next_cpi})"))

        # 8: 종합 이벤트 위험도 (≤7일 내 임박 이벤트 카운트)
        imminent = 0
        if d_earn is not None and 0 <= d_earn <= 7:
            imminent += 2  # 실적은 가중치 2
        if d_exdiv is not None and 0 < d_exdiv <= 7:
            imminent += 1
        if d_fomc is not None and 0 <= d_fomc <= 7:
            imminent += 1
        if d_cpi is not None and 0 <= d_cpi <= 7:
            imminent += 1

        if imminent >= 3:
            add(_v_dn("종합 이벤트 위험", f"7일 내 주요 이벤트 합산 가중 {imminent} — 변동성 매우 클 가능"))
        elif imminent >= 1:
            add(_v_n("종합 이벤트 위험", f"7일 내 이벤트 가중 {imminent} — 주의"))
        else:
            add(_v_up("종합 이벤트 위험", "7일 내 주요 이벤트 없음 — 안정 구간"))

        # 종합
        net = up - down
        if net >= 3:
            summary = "이벤트 안정 (단기 무리스크)"
        elif net <= -3:
            summary = "이벤트 위험 임박 (변동성 주의)"
        elif up >= 1 and down >= 1:
            summary = "혼조 — 일부 이벤트 임박"
        else:
            summary = "이벤트 중립"

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary,
            details={
                "checks": checks,
                "next_earnings": str(next_earn) if next_earn else None,
                "next_fomc": str(next_fomc) if next_fomc else None,
                "next_cpi": str(next_cpi) if next_cpi else None,
            },
        )


def _next_macro_date(dates: list[date]) -> date | None:
    """주어진 매크로 일정 중 다음 일자."""
    today = datetime.now().date()
    future = [d for d in dates if d >= today]
    return future[0] if future else None


def _format_large_number(v: float) -> str:
    """큰 숫자 표기 (조/억/M/B)."""
    abs_v = abs(v)
    if abs_v >= 1e12:
        return f"{v/1e12:.1f}조"
    if abs_v >= 1e9:
        return f"{v/1e9:.1f}B"
    if abs_v >= 1e8:
        return f"{v/1e8:.0f}억"
    if abs_v >= 1e6:
        return f"{v/1e6:.1f}M"
    return f"{v:,.0f}"


__all__ = ["EventTracker"]

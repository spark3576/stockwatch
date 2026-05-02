"""재무 분석 시그널 — 밸류에이션 + 수익성 + 안정성 + 성장성 + 현금흐름 종합.

16개 체크:
  1.  PER (TTM)               9.  매출 성장률 (YoY)
  2.  Forward PER             10. EPS 성장률 (YoY)
  3.  PBR                     11. 매출 분기 트렌드
  4.  PSR                     12. 배당 (수익률 + 안정성)
  5.  EV/EBITDA               13. OCF 마진 (영업현금/매출)
  6.  ROE                     14. FCF 수익률 (잉여현금/시총)
  7.  영업이익률              15. OCF vs 순이익 (이익의 질)
  8.  부채비율 (D/E)          16. FCF 성장률 (YoY)

데이터 소스 (자동 폴백):
  yfinance .info → yfinance financials/cashflow → pykrx (KR)
누락된 데이터는 △ 처리 + 출처 표시.
"""
from __future__ import annotations

import pandas as pd

from src.collectors.fundamentals import fetch_fundamentals
from src.signals.base import Signal, SignalResult
from src.utils.logger import logger


def _v_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _v_dn(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _v_n(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class FinancialSignal(Signal):
    name = "재무 분석"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        fund = fetch_fundamentals(symbol)
        if not fund or all(v is None for k, v in fund.items() if k in (
            "trailing_pe", "pbr", "roe", "operating_margin"
        )):
            logger.warning(f"  재무분석: 데이터 거의 없음 ({symbol})")
            return SignalResult(self.name, score_neut=10, summary="재무 데이터 부족")

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

        # 1: PER (TTM)
        pe = fund.get("trailing_pe")
        if pe is None:
            add(_v_n("PER (TTM)", "데이터 없음 (적자 또는 미공개)"))
        elif pe < 0:
            add(_v_n("PER (TTM)", f"{pe:.1f} (적자 상태)"))
        elif pe < 10:
            add(_v_up("PER (TTM)", f"{pe:.1f} (저평가, 시장평균 이하)"))
        elif pe < 20:
            add(_v_n("PER (TTM)", f"{pe:.1f} (적정 범위)"))
        elif pe < 30:
            add(_v_n("PER (TTM)", f"{pe:.1f} (다소 고평가)"))
        else:
            add(_v_dn("PER (TTM)", f"{pe:.1f} (고평가)"))

        # 2: Forward PER (미래 추정)
        fpe = fund.get("forward_pe")
        if fpe is None:
            add(_v_n("Forward PER", "추정치 없음"))
        elif fpe < 0:
            add(_v_n("Forward PER", f"{fpe:.1f} (이익 추정 부정)"))
        elif fpe < pe * 0.85 if pe and pe > 0 else False:
            add(_v_up("Forward PER", f"{fpe:.1f} (TTM 대비 개선 — 이익 성장 예상)"))
        elif pe and pe > 0 and fpe > pe * 1.15:
            add(_v_dn("Forward PER", f"{fpe:.1f} (TTM 대비 악화 — 이익 감소 예상)"))
        elif fpe < 15:
            add(_v_up("Forward PER", f"{fpe:.1f} (저평가)"))
        elif fpe > 30:
            add(_v_dn("Forward PER", f"{fpe:.1f} (고평가)"))
        else:
            add(_v_n("Forward PER", f"{fpe:.1f}"))

        # 3: PBR
        pbr = fund.get("pbr")
        if pbr is None:
            add(_v_n("PBR", "데이터 없음"))
        elif pbr < 1:
            add(_v_up("PBR", f"{pbr:.2f} (청산가치 이하 — 저평가)"))
        elif pbr < 2:
            add(_v_n("PBR", f"{pbr:.2f} (적정)"))
        elif pbr < 4:
            add(_v_n("PBR", f"{pbr:.2f} (다소 고평가)"))
        else:
            add(_v_dn("PBR", f"{pbr:.2f} (고평가)"))

        # 4: PSR
        psr = fund.get("psr")
        if psr is None:
            add(_v_n("PSR", "데이터 없음"))
        elif psr < 1:
            add(_v_up("PSR", f"{psr:.2f} (매출 대비 저평가)"))
        elif psr < 3:
            add(_v_n("PSR", f"{psr:.2f} (적정)"))
        elif psr < 8:
            add(_v_n("PSR", f"{psr:.2f} (다소 고평가)"))
        else:
            add(_v_dn("PSR", f"{psr:.2f} (고평가, 성장주 프리미엄 대형)"))

        # 5: EV/EBITDA
        ev = fund.get("ev_ebitda")
        if ev is None:
            add(_v_n("EV/EBITDA", "데이터 없음"))
        elif ev < 0:
            add(_v_n("EV/EBITDA", f"{ev:.1f} (영업현금 적자)"))
        elif ev < 8:
            add(_v_up("EV/EBITDA", f"{ev:.1f} (저평가)"))
        elif ev < 15:
            add(_v_n("EV/EBITDA", f"{ev:.1f} (적정)"))
        elif ev < 25:
            add(_v_n("EV/EBITDA", f"{ev:.1f} (다소 고평가)"))
        else:
            add(_v_dn("EV/EBITDA", f"{ev:.1f} (고평가)"))

        # 6: ROE (소수 → %로 변환)
        roe = fund.get("roe")
        if roe is None:
            add(_v_n("ROE (자기자본수익률)", "데이터 없음"))
        else:
            roe_pct = roe * 100
            if roe_pct >= 20:
                add(_v_up("ROE (자기자본수익률)", f"{roe_pct:.1f}% (우수, 워런 버핏 기준 통과)"))
            elif roe_pct >= 10:
                add(_v_up("ROE (자기자본수익률)", f"{roe_pct:.1f}% (양호)"))
            elif roe_pct >= 5:
                add(_v_n("ROE (자기자본수익률)", f"{roe_pct:.1f}% (평균)"))
            elif roe_pct >= 0:
                add(_v_dn("ROE (자기자본수익률)", f"{roe_pct:.1f}% (부진)"))
            else:
                add(_v_dn("ROE (자기자본수익률)", f"{roe_pct:.1f}% (적자)"))

        # 7: 영업이익률
        opm = fund.get("operating_margin")
        if opm is None:
            add(_v_n("영업이익률", "데이터 없음"))
        else:
            opm_pct = opm * 100
            if opm_pct >= 20:
                add(_v_up("영업이익률", f"{opm_pct:.1f}% (우수)"))
            elif opm_pct >= 10:
                add(_v_up("영업이익률", f"{opm_pct:.1f}% (양호)"))
            elif opm_pct >= 3:
                add(_v_n("영업이익률", f"{opm_pct:.1f}% (평균)"))
            elif opm_pct >= 0:
                add(_v_dn("영업이익률", f"{opm_pct:.1f}% (낮음)"))
            else:
                add(_v_dn("영업이익률", f"{opm_pct:.1f}% (적자)"))

        # 8: 부채비율 (yfinance: 백분율 숫자)
        de = fund.get("debt_to_equity")
        if de is None:
            add(_v_n("부채비율 (D/E)", "데이터 없음"))
        else:
            # 50.0 = 50% = 자본 대비 부채 0.5배
            if de < 50:
                add(_v_up("부채비율 (D/E)", f"{de:.0f}% (안전)"))
            elif de < 100:
                add(_v_n("부채비율 (D/E)", f"{de:.0f}% (보통)"))
            elif de < 200:
                add(_v_dn("부채비율 (D/E)", f"{de:.0f}% (높음)"))
            else:
                add(_v_dn("부채비율 (D/E)", f"{de:.0f}% (위험)"))

        # 9: 매출 성장률 (분기 YoY 우선, 자체 계산 폴백)
        rg = (
            fund.get("revenue_quarterly_growth")
            or fund.get("revenue_quarterly_growth_calc")
            or fund.get("revenue_growth")
        )
        if rg is None:
            add(_v_n("매출 성장 (YoY)", "데이터 없음"))
        else:
            rg_pct = rg * 100
            if rg_pct >= 20:
                add(_v_up("매출 성장 (YoY)", f"{rg_pct:+.1f}% (고성장)"))
            elif rg_pct >= 5:
                add(_v_up("매출 성장 (YoY)", f"{rg_pct:+.1f}% (성장)"))
            elif rg_pct >= -5:
                add(_v_n("매출 성장 (YoY)", f"{rg_pct:+.1f}% (정체)"))
            else:
                add(_v_dn("매출 성장 (YoY)", f"{rg_pct:+.1f}% (감소)"))

        # 10: EPS 성장률 (분기 YoY 우선, 자체 계산 폴백)
        eg = (
            fund.get("earnings_quarterly_growth")
            or fund.get("earnings_quarterly_growth_calc")
            or fund.get("earnings_growth")
        )
        if eg is None:
            add(_v_n("EPS 성장 (YoY)", "데이터 없음"))
        else:
            eg_pct = eg * 100
            if eg_pct >= 30:
                add(_v_up("EPS 성장 (YoY)", f"{eg_pct:+.1f}% (고성장)"))
            elif eg_pct >= 5:
                add(_v_up("EPS 성장 (YoY)", f"{eg_pct:+.1f}% (성장)"))
            elif eg_pct >= -5:
                add(_v_n("EPS 성장 (YoY)", f"{eg_pct:+.1f}% (정체)"))
            else:
                add(_v_dn("EPS 성장 (YoY)", f"{eg_pct:+.1f}% (감소)"))

        # 11: 매출 분기 트렌드 (4분기 흐름)
        qrev = fund.get("quarterly_revenue")
        if qrev and len(qrev) >= 3:
            # 최근 4분기 [Q0, Q1, Q2, Q3] (Q0 = 가장 최근)
            # 최근 3분기 연속 증가/감소 체크
            recent3 = qrev[:3]
            if all(recent3[i] > recent3[i + 1] for i in range(len(recent3) - 1)):
                pct = ((recent3[0] / recent3[-1]) - 1) * 100
                add(_v_up("매출 분기 트렌드",
                         f"3분기 연속 증가 ({pct:+.1f}% 누적)"))
            elif all(recent3[i] < recent3[i + 1] for i in range(len(recent3) - 1)):
                pct = ((recent3[0] / recent3[-1]) - 1) * 100
                add(_v_dn("매출 분기 트렌드",
                         f"3분기 연속 감소 ({pct:+.1f}% 누적)"))
            else:
                # 최근 분기 vs 평균
                avg_prior = sum(qrev[1:]) / len(qrev[1:])
                if avg_prior > 0:
                    delta = ((qrev[0] / avg_prior) - 1) * 100
                    if abs(delta) < 3:
                        add(_v_n("매출 분기 트렌드", f"혼조 (최근 {delta:+.1f}% vs 직전 평균)"))
                    elif delta > 0:
                        add(_v_n("매출 분기 트렌드", f"최근 반등 ({delta:+.1f}%)"))
                    else:
                        add(_v_n("매출 분기 트렌드", f"최근 둔화 ({delta:+.1f}%)"))
                else:
                    add(_v_n("매출 분기 트렌드", "혼조"))
        else:
            add(_v_n("매출 분기 트렌드", "분기 데이터 없음"))

        # 12: 배당 (배당수익률)
        div_yield = fund.get("dividend_yield")
        payout = fund.get("payout_ratio")
        if div_yield is None or div_yield == 0:
            add(_v_n("배당", "무배당 또는 미공개"))
        else:
            dy_pct = div_yield * 100
            payout_str = f", 배당성향 {payout*100:.0f}%" if payout else ""
            if dy_pct >= 4:
                if payout and payout > 1.5:
                    add(_v_n("배당", f"수익률 {dy_pct:.2f}% (고배당, 단 배당성향 {payout*100:.0f}%↑ 지속성 의심)"))
                else:
                    add(_v_up("배당", f"수익률 {dy_pct:.2f}% (고배당){payout_str}"))
            elif dy_pct >= 2:
                add(_v_up("배당", f"수익률 {dy_pct:.2f}% (안정 배당){payout_str}"))
            elif dy_pct >= 0.5:
                add(_v_n("배당", f"수익률 {dy_pct:.2f}% (소액 배당){payout_str}"))
            else:
                add(_v_n("배당", f"수익률 {dy_pct:.2f}% (미미){payout_str}"))

        # 13: OCF 마진 (영업현금 / 매출) — 이익이 진짜 현금으로 들어오는가
        ocf_margin = fund.get("ocf_margin")
        if ocf_margin is None:
            add(_v_n("OCF 마진", "현금흐름 데이터 없음"))
        else:
            ocfm_pct = ocf_margin * 100
            if ocfm_pct >= 25:
                add(_v_up("OCF 마진", f"{ocfm_pct:.1f}% (현금 창출력 우수)"))
            elif ocfm_pct >= 12:
                add(_v_up("OCF 마진", f"{ocfm_pct:.1f}% (양호)"))
            elif ocfm_pct >= 5:
                add(_v_n("OCF 마진", f"{ocfm_pct:.1f}% (평균)"))
            elif ocfm_pct >= 0:
                add(_v_dn("OCF 마진", f"{ocfm_pct:.1f}% (낮음)"))
            else:
                add(_v_dn("OCF 마진", f"{ocfm_pct:.1f}% (영업현금 적자)"))

        # 14: FCF 수익률 (잉여현금 / 시총) — 워런 버핏 핵심 지표
        fcf_yield = fund.get("fcf_yield")
        if fcf_yield is None:
            add(_v_n("FCF 수익률", "잉여현금 데이터 없음"))
        else:
            fy_pct = fcf_yield * 100
            if fy_pct >= 8:
                add(_v_up("FCF 수익률", f"{fy_pct:+.1f}% (저평가 + 현금 창출 우수)"))
            elif fy_pct >= 4:
                add(_v_up("FCF 수익률", f"{fy_pct:+.1f}% (양호)"))
            elif fy_pct >= 1:
                add(_v_n("FCF 수익률", f"{fy_pct:+.1f}% (평균)"))
            elif fy_pct >= 0:
                add(_v_dn("FCF 수익률", f"{fy_pct:+.1f}% (현금 매력 낮음)"))
            else:
                add(_v_dn("FCF 수익률", f"{fy_pct:+.1f}% (잉여현금 적자 — 자금 부담)"))

        # 15: OCF vs 순이익 (이익의 질) — 1.0+ 정상, 0.7- 회계 분식 의심
        ocf_to_ni = fund.get("ocf_to_ni")
        if ocf_to_ni is None:
            add(_v_n("OCF vs 순이익", "데이터 부족"))
        else:
            if ocf_to_ni >= 1.2:
                add(_v_up("OCF vs 순이익",
                         f"{ocf_to_ni:.2f}배 (회계이익보다 현금 더 — 진짜 이익)"))
            elif ocf_to_ni >= 0.9:
                add(_v_up("OCF vs 순이익", f"{ocf_to_ni:.2f}배 (이익↔현금 일치)"))
            elif ocf_to_ni >= 0.7:
                add(_v_n("OCF vs 순이익", f"{ocf_to_ni:.2f}배 (소폭 괴리)"))
            elif ocf_to_ni >= 0.3:
                add(_v_dn("OCF vs 순이익",
                         f"{ocf_to_ni:.2f}배 (회계 vs 현금 큰 괴리 — 분식 의심)"))
            else:
                add(_v_dn("OCF vs 순이익",
                         f"{ocf_to_ni:.2f}배 (이익은 있는데 현금 거의 없음)"))

        # 16: FCF 성장률 (YoY)
        fcf_growth = fund.get("fcf_growth")
        if fcf_growth is None:
            add(_v_n("FCF 성장 (YoY)", "데이터 부족"))
        else:
            fg_pct = fcf_growth * 100
            if fg_pct >= 30:
                add(_v_up("FCF 성장 (YoY)", f"{fg_pct:+.1f}% (현금 흐름 가속)"))
            elif fg_pct >= 5:
                add(_v_up("FCF 성장 (YoY)", f"{fg_pct:+.1f}% (성장)"))
            elif fg_pct >= -5:
                add(_v_n("FCF 성장 (YoY)", f"{fg_pct:+.1f}% (정체)"))
            elif fg_pct >= -30:
                add(_v_dn("FCF 성장 (YoY)", f"{fg_pct:+.1f}% (감소)"))
            else:
                add(_v_dn("FCF 성장 (YoY)", f"{fg_pct:+.1f}% (큰 폭 감소)"))

        # 종합 (16개 체크 기준)
        net = up - down
        if net >= 8:
            summary = "재무 우량 (저평가+성장+수익성+현금)"
        elif net >= 4:
            summary = "재무 양호"
        elif net <= -8:
            summary = "재무 부실"
        elif net <= -4:
            summary = "재무 약세"
        else:
            summary = "재무 중립"

        # 누락 데이터 카운트 (감리용)
        missing_count = sum(1 for c in checks if "데이터 없음" in c.get("reason", ""))

        details = {
            "checks": checks,
            "data_sources": fund.get("_sources", []),
            "missing_count": missing_count,
            "summary_metrics": {
                "PER": fund.get("trailing_pe"),
                "PBR": fund.get("pbr"),
                "PSR": fund.get("psr"),
                "ROE_%": (fund["roe"] * 100) if fund.get("roe") is not None else None,
                "OPM_%": (fund["operating_margin"] * 100) if fund.get("operating_margin") is not None else None,
                "D/E_%": fund.get("debt_to_equity"),
                "Rev_YoY_%": (rg * 100) if rg is not None else None,
                "EPS_YoY_%": (eg * 100) if eg is not None else None,
                "Div_yield_%": (fund["dividend_yield"] * 100) if fund.get("dividend_yield") is not None else None,
                "OCF": fund.get("operating_cash_flow"),
                "FCF": fund.get("free_cash_flow"),
                "OCF_margin_%": (ocf_margin * 100) if ocf_margin is not None else None,
                "FCF_yield_%": (fcf_yield * 100) if fcf_yield is not None else None,
                "OCF_to_NI": fund.get("ocf_to_ni"),
                "FCF_growth_%": (fcf_growth * 100) if fcf_growth is not None else None,
                "MarketCap": fund.get("market_cap"),
                "sector": fund.get("sector"),
            },
        }

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, details=details,
        )


__all__ = ["FinancialSignal"]

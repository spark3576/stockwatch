"""재무 지표 수집기 — 다중 소스 통합 (yfinance .info + 재무제표 + pykrx).

소스 우선순위:
  1. yfinance .info (가장 빠름, 모든 시장)
  2. yfinance financials (income/balance/cashflow에서 직접 계산)
  3. pykrx get_market_fundamental (KR 전용, .info보다 정확)

누락된 값은 자동으로 다른 소스에서 보강.

값 단위:
  - roe, profit_margin, *_growth, dividend_yield → 소수 (0.15 = 15%)
  - debt_to_equity → 백분율 숫자 (50.0 = 50%)
  - trailing_pe, pbr, psr 등 → 배수
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from src.utils.logger import logger
from src.utils.markets import detect_market, to_yfinance_symbol


# 모듈 캐시 (분석 세션 내 동일 종목 반복 호출 방지)
_FUND_CACHE: dict[str, dict[str, Any]] = {}


def fetch_fundamentals(symbol: str) -> dict[str, Any]:
    """재무 지표 통합 조회 (다중 소스 자동 보강).

    반환 키:
      - 밸류에이션: trailing_pe, forward_pe, pbr, psr, ev_ebitda, peg
      - 수익성: roe, roa, profit_margin, operating_margin, gross_margin
      - 안정성: debt_to_equity, current_ratio, quick_ratio
      - 성장성: revenue_growth, earnings_growth (분기 YoY)
      - 배당: dividend_yield, payout_ratio, dps
      - 분기 트렌드: quarterly_revenue (4분기), quarterly_eps (4분기)
      - 규모: market_cap, enterprise_value
      - 메타데이터 + 데이터 출처 정보 (sources)
    """
    ysym = to_yfinance_symbol(symbol)
    market = detect_market(symbol)
    if ysym in _FUND_CACHE:
        return _FUND_CACHE[ysym]

    sources: list[str] = []

    # ─── 소스 1: yfinance .info (기본) ──────────────────
    info = _fetch_yf_info(ysym)
    if info:
        sources.append("yf.info")
    fund = _info_to_fund(info)

    # ─── 소스 2: yfinance financials (재무제표 직접) ────
    ticker = yf.Ticker(ysym)
    computed = _compute_from_financials(ticker, fund.get("market_cap"))
    if computed:
        sources.append("yf.financials")
    # 보강: fund의 None인 값을 computed에서 채우기
    for k, v in computed.items():
        if v is not None and fund.get(k) is None:
            fund[k] = v

    # ─── 소스 3: pykrx (KR 전용) ────────────────────────
    if market == "KR":
        krx = _fetch_pykrx_fundamentals(symbol)
        if krx:
            sources.append("pykrx")
            # pykrx는 KR에서 더 정확 → 항상 우선 사용
            for k, v in krx.items():
                if v is not None:
                    fund[k] = v

    # ─── 분기 트렌드 (yfinance quarterly) ───────────────
    qt = _quarterly_trend(ticker)
    if qt:
        sources.append("yf.quarterly")
        fund.update(qt)

    # ─── 현금흐름 (Phase 1.5+) ──────────────────────────
    cf = _cashflow_metrics(ticker, fund.get("market_cap"), fund.get("shares_outstanding"))
    if cf:
        sources.append("yf.cashflow")
        fund.update(cf)

    # 데이터 출처 표시
    fund["_sources"] = sources

    _FUND_CACHE[ysym] = fund
    return fund


# ─────────────────────────────────────────────────────────────────────────────
# 현금흐름 (Cash Flow) — OCF / FCF / CAPEX
# ─────────────────────────────────────────────────────────────────────────────

def _cashflow_metrics(ticker, market_cap: float | None, shares: float | None) -> dict[str, Any]:
    """현금흐름 지표 추출 + 계산.

    반환:
      - operating_cash_flow (연간)
      - free_cash_flow (연간)
      - capex (연간, 음수)
      - ocf_margin (OCF / Revenue, 소수)
      - fcf_yield (FCF / Market Cap, 소수)
      - ocf_to_ni (OCF / Net Income, 배수 — 1.0+ 정상)
      - fcf_growth (잉여현금 YoY, 소수)
      - quarterly_ocf, quarterly_fcf (4분기 리스트)
    """
    out: dict[str, Any] = {}

    try:
        cf = ticker.cashflow                    # 연간
        income = ticker.income_stmt
    except Exception as e:
        logger.debug(f"yf.cashflow 호출 실패: {e}")
        return out

    if cf is None or cf.empty:
        return out

    cols = list(cf.columns)
    latest = cols[0]
    prior = cols[1] if len(cols) >= 2 else None

    # 핵심 추출
    ocf = _row(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"], latest)
    fcf = _row(cf, ["Free Cash Flow"], latest)
    capex = _row(cf, ["Capital Expenditure", "Capital Expenditure Reported"], latest)

    # FCF가 직접 없으면 OCF + CAPEX (CAPEX는 음수로 저장됨)
    if fcf is None and ocf is not None and capex is not None:
        fcf = ocf + capex   # capex 음수이므로 OCF에 더하면 OCF - |CAPEX|

    out["operating_cash_flow"] = ocf
    out["free_cash_flow"] = fcf
    out["capex"] = capex

    # OCF Margin = OCF / Revenue
    if income is not None and not income.empty:
        revenue = _row(income, ["Total Revenue", "Revenue"], latest)
        net_income = _row(income, ["Net Income", "Net Income Common Stockholders"], latest)
        if ocf is not None and revenue and revenue > 0:
            out["ocf_margin"] = ocf / revenue
        # OCF / Net Income (이익의 질)
        if ocf is not None and net_income and net_income > 0:
            out["ocf_to_ni"] = ocf / net_income

    # FCF Yield = FCF / Market Cap
    if fcf is not None and market_cap and market_cap > 0:
        out["fcf_yield"] = fcf / market_cap

    # FCF YoY 성장률 (전년 대비)
    if prior is not None:
        prior_fcf = _row(cf, ["Free Cash Flow"], prior)
        if prior_fcf is None:
            prior_ocf = _row(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"], prior)
            prior_capex = _row(cf, ["Capital Expenditure", "Capital Expenditure Reported"], prior)
            if prior_ocf is not None and prior_capex is not None:
                prior_fcf = prior_ocf + prior_capex
        if fcf is not None and prior_fcf is not None and prior_fcf != 0:
            out["fcf_growth"] = (fcf - prior_fcf) / abs(prior_fcf)

    # 분기 추이
    try:
        qcf = ticker.quarterly_cashflow
    except Exception:
        qcf = None
    if qcf is not None and not qcf.empty:
        qcols = list(qcf.columns)[:4]
        q_ocf = []
        q_fcf = []
        for c in qcols:
            v_ocf = _row(qcf, ["Operating Cash Flow", "Total Cash From Operating Activities"], c)
            v_fcf = _row(qcf, ["Free Cash Flow"], c)
            v_capex = _row(qcf, ["Capital Expenditure", "Capital Expenditure Reported"], c)
            if v_fcf is None and v_ocf is not None and v_capex is not None:
                v_fcf = v_ocf + v_capex
            if v_ocf is not None:
                q_ocf.append(v_ocf)
            if v_fcf is not None:
                q_fcf.append(v_fcf)
        if q_ocf:
            out["quarterly_ocf"] = q_ocf
        if q_fcf:
            out["quarterly_fcf"] = q_fcf

    return out


# ─────────────────────────────────────────────────────────────────────────────
# 소스 1: yfinance .info
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_yf_info(ysym: str) -> dict:
    try:
        info = yf.Ticker(ysym).info or {}
    except Exception as e:
        logger.warning(f"yfinance .info 실패 ({ysym}): {e}")
        info = {}
    # KR 종목 .KS → .KQ 폴백
    if not info and ysym.endswith(".KS"):
        try:
            info = yf.Ticker(ysym[:-3] + ".KQ").info or {}
        except Exception:
            pass
    return info


def _info_to_fund(info: dict) -> dict[str, Any]:
    # yfinance ≥ 0.2.40 부터 dividendYield를 백분율(3.14 = 3.14%)로 반환.
    # 일부 종목은 여전히 소수(0.0314)로 줌 → 휴리스틱 정규화.
    dy = _normalize_yield(info.get("dividendYield"))
    payout = _safe(info.get("payoutRatio"))
    # payoutRatio도 0~1 소수가 정상이지만 가끔 백분율로 들어옴 (>2면 백분율로 가정)
    if payout is not None and payout > 2:
        payout = payout / 100

    return {
        "trailing_pe": _safe(info.get("trailingPE")),
        "forward_pe": _safe(info.get("forwardPE")),
        "pbr": _safe(info.get("priceToBook")),
        "psr": _safe(info.get("priceToSalesTrailing12Months")),
        "ev_ebitda": _safe(info.get("enterpriseToEbitda")),
        "peg": _safe(info.get("trailingPegRatio") or info.get("pegRatio")),
        "roe": _safe(info.get("returnOnEquity")),
        "roa": _safe(info.get("returnOnAssets")),
        "profit_margin": _safe(info.get("profitMargins")),
        "operating_margin": _safe(info.get("operatingMargins")),
        "gross_margin": _safe(info.get("grossMargins")),
        "debt_to_equity": _safe(info.get("debtToEquity")),
        "current_ratio": _safe(info.get("currentRatio")),
        "quick_ratio": _safe(info.get("quickRatio")),
        "revenue_growth": _safe(info.get("revenueGrowth")),
        "earnings_growth": _safe(info.get("earningsGrowth")),
        "earnings_quarterly_growth": _safe(info.get("earningsQuarterlyGrowth")),
        "revenue_quarterly_growth": _safe(info.get("revenueQuarterlyGrowth")),
        "dividend_yield": dy,
        "payout_ratio": payout,
        "dps": _safe(info.get("dividendRate")),
        "market_cap": _safe(info.get("marketCap")),
        "enterprise_value": _safe(info.get("enterpriseValue")),
        "shares_outstanding": _safe(info.get("sharesOutstanding")),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "country": info.get("country"),
        "name": info.get("shortName") or info.get("longName"),
        "beta_yf": _safe(info.get("beta")),
    }


def _normalize_yield(v: Any) -> float | None:
    """배당수익률 단위 정규화 → 항상 소수 (0.0314 = 3.14%) 반환.

    yfinance 0.2.40+: dividendYield가 백분율 (3.14 = 3.14%) 으로 반환.
    구버전: 소수 (0.0314 = 3.14%).
    휴리스틱: 0.15 초과면 백분율로 가정 (현실 배당수익률 15%+ 매우 희귀).
    """
    f = _safe(v)
    if f is None or f == 0:
        return f
    if f > 0.15:  # 15% 초과면 백분율로 가정 → /100
        return f / 100
    return f  # 이미 소수


# ─────────────────────────────────────────────────────────────────────────────
# 소스 2: yfinance financials → 직접 계산
# ─────────────────────────────────────────────────────────────────────────────

def _compute_from_financials(ticker, market_cap: float | None) -> dict[str, Any]:
    """income_stmt / balance_sheet에서 PER/PBR/ROE/마진 직접 계산."""
    out: dict[str, Any] = {}
    try:
        income = ticker.income_stmt        # 연간 (4년)
        balance = ticker.balance_sheet
    except Exception as e:
        logger.debug(f"yf.financials 호출 실패: {e}")
        return out

    if income is None or income.empty:
        return out

    # 가장 최근 컬럼 = 최근 회계연도
    latest_col = income.columns[0]
    revenue = _row(income, ["Total Revenue", "Revenue"], latest_col)
    net_income = _row(income, ["Net Income", "Net Income Common Stockholders"], latest_col)
    operating_income = _row(income, ["Operating Income", "EBIT"], latest_col)
    gross_profit = _row(income, ["Gross Profit"], latest_col)

    if balance is not None and not balance.empty:
        bal_col = balance.columns[0]
        equity = _row(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest"], bal_col)
        total_debt = _row(balance, ["Total Debt", "Net Debt"], bal_col)
        current_assets = _row(balance, ["Current Assets"], bal_col)
        current_liab = _row(balance, ["Current Liabilities"], bal_col)
    else:
        equity = total_debt = current_assets = current_liab = None

    # PER = Market Cap / Net Income
    if market_cap and net_income and net_income > 0:
        out["trailing_pe"] = market_cap / net_income
    # PBR = Market Cap / Equity
    if market_cap and equity and equity > 0:
        out["pbr"] = market_cap / equity
    # PSR = Market Cap / Revenue
    if market_cap and revenue and revenue > 0:
        out["psr"] = market_cap / revenue
    # ROE = Net Income / Equity (소수)
    if net_income and equity and equity > 0:
        out["roe"] = net_income / equity
    # 영업이익률 (소수)
    if operating_income and revenue and revenue > 0:
        out["operating_margin"] = operating_income / revenue
    # 순이익률
    if net_income and revenue and revenue > 0:
        out["profit_margin"] = net_income / revenue
    # 매출총이익률
    if gross_profit and revenue and revenue > 0:
        out["gross_margin"] = gross_profit / revenue
    # D/E (백분율)
    if total_debt and equity and equity > 0:
        out["debt_to_equity"] = (total_debt / equity) * 100
    # 유동비율
    if current_assets and current_liab and current_liab > 0:
        out["current_ratio"] = current_assets / current_liab

    return out


def _row(df: pd.DataFrame, candidates: list[str], col) -> float | None:
    """DataFrame에서 행 찾기 (이름 후보 여러 개)."""
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            v = df.loc[name, col]
            try:
                f = float(v)
                if f != f:
                    return None
                return f
            except (TypeError, ValueError):
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 소스 3: pykrx (KR 전용)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_pykrx_fundamentals(symbol: str) -> dict[str, Any]:
    """pykrx get_market_fundamental — PER/PBR/EPS/BPS/DIV/DPS."""
    try:
        from pykrx import stock as pkstock
    except ImportError:
        return {}

    # 최근 영업일 데이터 찾기 (오늘부터 7일 전까지)
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = pkstock.get_market_fundamental(date, date, symbol)
            if df is not None and not df.empty:
                row = df.iloc[0]
                per = float(row.get("PER", 0))
                pbr = float(row.get("PBR", 0))
                div = float(row.get("DIV", 0))
                return {
                    "trailing_pe": per if per > 0 else None,
                    "pbr": pbr if pbr > 0 else None,
                    "eps": float(row.get("EPS", 0)) or None,
                    "bps": float(row.get("BPS", 0)) or None,
                    "dividend_yield": (div / 100) if div > 0 else None,
                    "dps": float(row.get("DPS", 0)) or None,
                }
        except Exception as e:
            logger.debug(f"pykrx fundamental {date} 실패: {e}")
            continue
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# 분기 트렌드 (4분기 매출/이익 흐름)
# ─────────────────────────────────────────────────────────────────────────────

def _quarterly_trend(ticker) -> dict[str, Any]:
    """최근 4분기 매출/순이익 추이 + 분기 YoY 자동 계산."""
    try:
        qi = ticker.quarterly_income_stmt
    except Exception:
        return {}
    if qi is None or qi.empty:
        return {}

    cols = list(qi.columns)[:5]  # 최근 5분기 (YoY 계산용)
    revenue_q = []
    netinc_q = []
    for c in cols:
        rev = _row(qi, ["Total Revenue", "Revenue"], c)
        ni = _row(qi, ["Net Income", "Net Income Common Stockholders"], c)
        if rev is not None:
            revenue_q.append(rev)
        if ni is not None:
            netinc_q.append(ni)

    out: dict[str, Any] = {}
    if revenue_q:
        out["quarterly_revenue"] = revenue_q[:4]
        # 분기 YoY (최근분기 vs 4분기전)
        if len(revenue_q) >= 5 and revenue_q[4] != 0:
            out["revenue_quarterly_growth_calc"] = (revenue_q[0] / revenue_q[4]) - 1
    if netinc_q:
        out["quarterly_net_income"] = netinc_q[:4]
        if len(netinc_q) >= 5 and netinc_q[4] != 0:
            out["earnings_quarterly_growth_calc"] = (netinc_q[0] / netinc_q[4]) - 1
    return out


def _safe(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe(v: Any) -> float | None:
    """숫자형 안전 변환. NaN/None/문자열 등은 None."""
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


__all__ = ["fetch_fundamentals"]

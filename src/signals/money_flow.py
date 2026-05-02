"""머니플로우 시그널 — 수급/자금흐름 종합 (사진의 8시그널 중 하나).

8개 체크:
  1. OBV 5일 추세 (단기 수급)
  2. OBV 20일 추세 (장기 수급)
  3. MFI 14일 (거래량 가중 RSI)
  4. A/D Line 5일 추세
  5. VWAP vs 종가 (기관 평균 매물대 비교)
  6. 상승일/하락일 거래량 비율 (5일)
  7. 거래대금 추세 (5일 vs 20일)
  8. (KR) 외인+기관 순매수 (5일 누적) / 그 외 시장은 △
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.signals.base import Signal, SignalResult
from src.signals.indicators import compute_all
from src.utils.logger import logger


def _v_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _v_dn(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _v_n(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class MoneyFlowSignal(Signal):
    name = "머니플로우"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        if df.empty or len(df) < 20:
            return SignalResult(self.name, score_neut=8, summary="데이터 부족")

        b = compute_all(df)
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

        last = -1

        # 1: OBV 5일 추세
        if len(b.obv_v) >= 6:
            now = float(b.obv_v.iloc[last])
            prev5 = float(b.obv_v.iloc[-6])
            change = now - prev5
            base = abs(prev5) if prev5 != 0 else (abs(now) if now != 0 else 1)
            pct = (change / base) * 100
            if change > base * 0.02:
                add(_v_up("OBV 5일 추세", f"+{pct:.1f}% (단기 매수 누적)"))
            elif change < -base * 0.02:
                add(_v_dn("OBV 5일 추세", f"{pct:+.1f}% (단기 매도 누적)"))
            else:
                add(_v_n("OBV 5일 추세", f"{pct:+.1f}% (정체)"))
        else:
            add(_v_n("OBV 5일 추세", "-"))

        # 2: OBV 20일 추세 (장기)
        if len(b.obv_v) >= 21:
            now = float(b.obv_v.iloc[last])
            prev20 = float(b.obv_v.iloc[-21])
            change = now - prev20
            base = abs(prev20) if prev20 != 0 else (abs(now) if now != 0 else 1)
            pct = (change / base) * 100
            if change > base * 0.05:
                add(_v_up("OBV 20일 추세", f"+{pct:.1f}% (장기 매집세)"))
            elif change < -base * 0.05:
                add(_v_dn("OBV 20일 추세", f"{pct:+.1f}% (장기 분배세)"))
            else:
                add(_v_n("OBV 20일 추세", f"{pct:+.1f}% (방향성 모호)"))
        else:
            add(_v_n("OBV 20일 추세", "-"))

        # 3: MFI 14일
        mfi_v = float(b.mfi14.iloc[last])
        if mfi_v > 80:
            add(_v_dn("MFI", f"{mfi_v:.0f} (자금 과유입 — 단기 조정 우려)"))
        elif mfi_v < 20:
            add(_v_up("MFI", f"{mfi_v:.0f} (자금 과유출 — 반등 가능)"))
        elif mfi_v > 60:
            add(_v_up("MFI", f"{mfi_v:.0f} (자금 유입 우세)"))
        elif mfi_v < 40:
            add(_v_dn("MFI", f"{mfi_v:.0f} (자금 유출 우세)"))
        else:
            add(_v_n("MFI", f"{mfi_v:.0f} (중립)"))

        # 4: A/D Line 5일 추세 (Accumulation/Distribution)
        ad = _accumulation_distribution(df)
        if len(ad) >= 6:
            now = float(ad.iloc[last])
            prev = float(ad.iloc[-6])
            base = abs(prev) if prev != 0 else (abs(now) if now != 0 else 1)
            pct = ((now - prev) / base) * 100
            if (now - prev) > base * 0.03:
                add(_v_up("A/D Line", f"+{pct:.1f}% (매집 우세)"))
            elif (now - prev) < -base * 0.03:
                add(_v_dn("A/D Line", f"{pct:+.1f}% (분배 우세)"))
            else:
                add(_v_n("A/D Line", f"{pct:+.1f}% (균형)"))
        else:
            add(_v_n("A/D Line", "-"))

        # 5: VWAP vs 종가 (20일 rolling VWAP — 단기 평균 매물대)
        vwap_v = float(b.vwap_v.iloc[last]) if not pd.isna(b.vwap_v.iloc[last]) else 0
        close_v = float(b.close.iloc[last])
        if vwap_v > 0:
            diff_pct = (close_v / vwap_v - 1) * 100
            if diff_pct > 3:
                add(_v_up("VWAP(20일) vs 종가",
                         f"종가가 VWAP {vwap_v:,.2f} 대비 {diff_pct:+.1f}% (단기 매물대 위)"))
            elif diff_pct < -3:
                add(_v_dn("VWAP(20일) vs 종가",
                         f"종가가 VWAP {vwap_v:,.2f} 대비 {diff_pct:+.1f}% (단기 매물대 아래)"))
            else:
                add(_v_n("VWAP(20일) vs 종가",
                        f"VWAP {vwap_v:,.2f} 대비 {diff_pct:+.1f}% (근접)"))
        else:
            add(_v_n("VWAP(20일) vs 종가", "데이터 부족"))

        # 6: 상승일/하락일 거래량 비율 (5일)
        if len(df) >= 6 and "volume" in df.columns:
            recent = df.tail(5).copy()
            recent["chg"] = recent["close"].diff()
            up_vol = float(recent[recent["chg"] > 0]["volume"].sum())
            dn_vol = float(recent[recent["chg"] < 0]["volume"].sum())
            if dn_vol > 0:
                ratio = up_vol / dn_vol
                if ratio > 1.5:
                    add(_v_up("매수일/매도일 거래량", f"{ratio:.2f}x (매수일 거래량 우세)"))
                elif ratio < 0.67:
                    add(_v_dn("매수일/매도일 거래량", f"{ratio:.2f}x (매도일 거래량 우세)"))
                else:
                    add(_v_n("매수일/매도일 거래량", f"{ratio:.2f}x (균형)"))
            elif up_vol > 0:
                add(_v_up("매수일/매도일 거래량", "5일 모두 상승 (매도일 없음)"))
            else:
                add(_v_n("매수일/매도일 거래량", "데이터 부족"))
        else:
            add(_v_n("매수일/매도일 거래량", "-"))

        # 7: 거래대금 추세 (5일 평균 vs 20일 평균)
        if len(df) >= 21 and "volume" in df.columns:
            v = df["volume"].astype(float)
            c = df["close"].astype(float)
            value = v * c  # 거래대금 (간이)
            avg5 = float(value.tail(5).mean())
            avg20 = float(value.tail(20).mean())
            if avg20 > 0:
                ratio = avg5 / avg20
                if ratio > 1.3:
                    add(_v_up("거래대금 추세", f"5일 평균 {ratio:.2f}x (관심 증가)"))
                elif ratio < 0.7:
                    add(_v_dn("거래대금 추세", f"5일 평균 {ratio:.2f}x (관심 감소)"))
                else:
                    add(_v_n("거래대금 추세", f"5일 평균 {ratio:.2f}x"))
            else:
                add(_v_n("거래대금 추세", "-"))
        else:
            add(_v_n("거래대금 추세", "-"))

        # 8: (KR) 외인+기관 순매수 / 그 외는 △
        if market == "KR":
            net_inv = _kr_foreign_institutional_flow(symbol, days=5)
            if net_inv is None:
                add(_v_n("외인+기관 순매수", "pykrx 데이터 없음"))
            else:
                total = net_inv["foreign"] + net_inv["institution"]
                # 시가총액 대비 비율로 판단 어려우니 단순 부호만
                if total > 0:
                    add(_v_up("외인+기관 순매수",
                             f"5일 외인 {net_inv['foreign']/1e8:+.1f}억 + 기관 {net_inv['institution']/1e8:+.1f}억 (순매수)"))
                elif total < 0:
                    add(_v_dn("외인+기관 순매수",
                             f"5일 외인 {net_inv['foreign']/1e8:+.1f}억 + 기관 {net_inv['institution']/1e8:+.1f}억 (순매도)"))
                else:
                    add(_v_n("외인+기관 순매수", "5일 균형"))
        else:
            add(_v_n("외인+기관 순매수", f"{market} 시장은 데이터 미지원"))

        # 종합
        net = up - down
        if net >= 5:
            summary = "강한 자금 유입 (수급 우호)"
        elif net >= 2:
            summary = "자금 유입 우세"
        elif net <= -5:
            summary = "강한 자금 유출 (수급 악화)"
        elif net <= -2:
            summary = "자금 유출 우세"
        else:
            summary = "수급 중립 / 혼조"

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, details={"checks": checks},
        )


def _accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    """A/D Line 계산. 매수 압력의 누적."""
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    v = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0] * len(c), index=c.index)
    rng = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / rng                 # Money Flow Multiplier
    mfv = mfm.fillna(0) * v                          # Money Flow Volume
    return mfv.cumsum()


def _kr_foreign_institutional_flow(symbol: str, days: int = 5) -> dict | None:
    """pykrx — 외인+기관 누적 순매수 금액 (5일)."""
    try:
        from pykrx import stock as pkstock
    except ImportError:
        return None

    try:
        # 최근 영업일 N일치
        end = datetime.now()
        start = end - timedelta(days=days * 3)  # 영업일 마진
        df = pkstock.get_market_trading_value_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), symbol,
        )
        if df is None or df.empty:
            return None
        # 최근 N개 거래일
        recent = df.tail(days)
        # 컬럼명: '기관합계', '외국인합계', '개인', '전체' (양수=매수, 음수=매도, 순매수)
        foreign = float(recent.get("외국인합계", recent.get("외국인", pd.Series([0]))).sum())
        institution = float(recent.get("기관합계", recent.get("기관", pd.Series([0]))).sum())
        return {"foreign": foreign, "institution": institution}
    except Exception as e:
        logger.debug(f"pykrx flow 실패 ({symbol}): {e}")
        return None


__all__ = ["MoneyFlowSignal"]

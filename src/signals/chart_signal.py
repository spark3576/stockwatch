"""차트 시그널 — 18개 기술적 지표 종합 체크.

체크 항목:
  1~4.  종가 vs 5/20/60/120일 이평선
  5.    단기 정배열 (5>20)
  6.    중기 정배열 (20>60)
  7.    MACD 위치 (히스토그램 양/음)
  8.    MACD 모멘텀 (히스토그램 증가/감소)
  9.    ADX (추세 강도, 25 이상이면 강함)
  10.   RSI 추세
  11.   볼린저 %B (밴드 내 위치)
  12.   스토캐스틱 (과매수/과매도)
  13.   Williams %R
  14.   CCI (±100 밖)
  15.   MFI (자금흐름)
  16.   일목균형표 구름대 위치
  17.   OBV 추세 (5일)
  18.   거래량 (5일 평균 대비)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.signals.base import Signal, SignalResult
from src.signals.indicators import IndicatorBundle, compute_all
from src.utils.logger import logger


def _verdict_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _verdict_down(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _verdict_neut(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class ChartSignal(Signal):
    name = "차트 시그널"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        if df.empty or len(df) < 130:
            logger.warning(f"  차트시그널: 데이터 부족 ({len(df)} < 130)")
            return SignalResult(
                signal_type=self.name, score_neut=18, summary="데이터 부족"
            )

        b = compute_all(df)
        last = -1
        close = float(b.close.iloc[last])

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

        # 1~4: 종가 vs 4개 이평선
        for period, ma in [(5, b.sma5), (20, b.sma20), (60, b.sma60), (120, b.sma120)]:
            ma_v = float(ma.iloc[last]) if not pd.isna(ma.iloc[last]) else None
            if ma_v is None:
                add(_verdict_neut(f"종가 vs {period}일선", "데이터 부족"))
            else:
                pct = (close / ma_v - 1) * 100
                base_msg = f"종가 {close:,.2f} ({pct:+.1f}%) vs MA{period} {ma_v:,.2f}"
                if close > ma_v * 1.001:
                    add(_verdict_up(f"종가 vs {period}일선", base_msg))
                elif close < ma_v * 0.999:
                    add(_verdict_down(f"종가 vs {period}일선", base_msg))
                else:
                    add(_verdict_neut(f"종가 vs {period}일선", f"근접 (MA{period} {ma_v:,.2f})"))

        # 5: 단기 정배열 (5>20)
        ma5_v, ma20_v = float(b.sma5.iloc[last]), float(b.sma20.iloc[last])
        if ma5_v > ma20_v:
            add(_verdict_up("단기 정배열(5>20)", "정배열"))
        else:
            add(_verdict_down("단기 정배열(5>20)", "역배열"))

        # 6: 중기 정배열 (20>60)
        ma60_v = float(b.sma60.iloc[last])
        if ma20_v > ma60_v:
            add(_verdict_up("중기 정배열(20>60)", "정배열"))
        else:
            add(_verdict_down("중기 정배열(20>60)", "역배열"))

        # 7: MACD 위치
        macd_hist = float(b.macd_df["hist"].iloc[last])
        if macd_hist > 0:
            add(_verdict_up("MACD 위치", f"히스토그램 +{macd_hist:.2f} (강세)"))
        elif macd_hist < 0:
            add(_verdict_down("MACD 위치", f"히스토그램 {macd_hist:.2f} (약세)"))
        else:
            add(_verdict_neut("MACD 위치", "0 부근"))

        # 8: MACD 모멘텀 (5일 전 대비)
        if len(b.macd_df) >= 6:
            prev_hist = float(b.macd_df["hist"].iloc[-6])
            if macd_hist > prev_hist + abs(prev_hist) * 0.1:
                add(_verdict_up("MACD 모멘텀", f"증가 {prev_hist:.2f}→{macd_hist:.2f}"))
            elif macd_hist < prev_hist - abs(prev_hist) * 0.1:
                add(_verdict_down("MACD 모멘텀", f"감소 {prev_hist:.2f}→{macd_hist:.2f}"))
            else:
                add(_verdict_neut("MACD 모멘텀", "정체"))
        else:
            add(_verdict_neut("MACD 모멘텀", "-"))

        # 9: ADX 추세 강도
        adx_v = float(b.adx14.iloc[last])
        if adx_v >= 25:
            # 추세 방향은 종가가 20일선 위/아래로 판단
            if close > ma20_v:
                add(_verdict_up("ADX 추세강도", f"강한 상승추세 ADX {adx_v:.0f}"))
            else:
                add(_verdict_down("ADX 추세강도", f"강한 하락추세 ADX {adx_v:.0f}"))
        else:
            add(_verdict_neut("ADX 추세강도", f"약한 추세 ADX {adx_v:.0f}"))

        # 10: RSI
        rsi_v = float(b.rsi14.iloc[last])
        prev_rsi = float(b.rsi14.iloc[-5]) if len(b.rsi14) >= 5 else rsi_v
        if rsi_v > 70:
            add(_verdict_down("RSI", f"과매수 {rsi_v:.1f}"))
        elif rsi_v < 30:
            add(_verdict_up("RSI", f"과매도 {rsi_v:.1f}"))
        elif rsi_v > prev_rsi + 3 and rsi_v > 50:
            add(_verdict_up("RSI", f"상승 {prev_rsi:.0f}→{rsi_v:.1f}"))
        elif rsi_v < prev_rsi - 3 and rsi_v < 50:
            add(_verdict_down("RSI", f"하락 {prev_rsi:.0f}→{rsi_v:.1f}"))
        else:
            add(_verdict_neut("RSI", f"횡보 {rsi_v:.1f}"))

        # 11: 볼린저 %B (0=하단, 1=상단, 0.5=중간)
        pct_b = float(b.bb["pct_b"].iloc[last]) if not pd.isna(b.bb["pct_b"].iloc[last]) else 0.5
        if pct_b > 1.0:
            add(_verdict_down("볼린저 %B", f"상단 돌파 {pct_b:.2f} (과열)"))
        elif pct_b > 0.8:
            add(_verdict_up("볼린저 %B", f"상단권 {pct_b:.2f} (강세)"))
        elif pct_b < 0:
            add(_verdict_up("볼린저 %B", f"하단 이탈 {pct_b:.2f} (반등 가능)"))
        elif pct_b < 0.2:
            add(_verdict_down("볼린저 %B", f"하단권 {pct_b:.2f} (약세)"))
        else:
            add(_verdict_neut("볼린저 %B", f"중간 {pct_b:.2f}"))

        # 12: 스토캐스틱
        k = float(b.stoch["k"].iloc[last])
        d = float(b.stoch["d"].iloc[last])
        if k > 80 and d > 80:
            add(_verdict_down("스토캐스틱", f"과매수 K{k:.0f}/D{d:.0f}"))
        elif k < 20 and d < 20:
            add(_verdict_up("스토캐스틱", f"과매도 K{k:.0f}/D{d:.0f}"))
        elif k > d:
            add(_verdict_up("스토캐스틱", f"K({k:.0f}) > D({d:.0f}) 골든"))
        else:
            add(_verdict_down("스토캐스틱", f"K({k:.0f}) < D({d:.0f}) 데드"))

        # 13: Williams %R
        wr = float(b.williams.iloc[last])
        if wr > -20:
            add(_verdict_down("Williams %R", f"과매수 {wr:.0f}"))
        elif wr < -80:
            add(_verdict_up("Williams %R", f"과매도 {wr:.0f}"))
        else:
            add(_verdict_neut("Williams %R", f"중립 {wr:.0f}"))

        # 14: CCI
        cci_v = float(b.cci20.iloc[last])
        if cci_v > 100:
            add(_verdict_up("CCI", f"강세 {cci_v:.0f} (>+100)"))
        elif cci_v < -100:
            add(_verdict_down("CCI", f"약세 {cci_v:.0f} (<-100)"))
        else:
            add(_verdict_neut("CCI", f"중립 {cci_v:.0f}"))

        # 15: MFI
        mfi_v = float(b.mfi14.iloc[last])
        if mfi_v > 80:
            add(_verdict_down("MFI(자금흐름)", f"과매수 {mfi_v:.0f}"))
        elif mfi_v < 20:
            add(_verdict_up("MFI(자금흐름)", f"과매도 {mfi_v:.0f}"))
        elif mfi_v > 50:
            add(_verdict_up("MFI(자금흐름)", f"매수 우세 {mfi_v:.0f}"))
        else:
            add(_verdict_down("MFI(자금흐름)", f"매도 우세 {mfi_v:.0f}"))

        # 16: 일목 구름대
        span_a = b.ichi["span_a"].iloc[last]
        span_b = b.ichi["span_b"].iloc[last]
        if not (pd.isna(span_a) or pd.isna(span_b)):
            cloud_top = max(float(span_a), float(span_b))
            cloud_bot = min(float(span_a), float(span_b))
            if close > cloud_top:
                add(_verdict_up("일목 구름대", f"구름 위 (상단 {cloud_top:,.2f})"))
            elif close < cloud_bot:
                add(_verdict_down("일목 구름대", f"구름 아래 (하단 {cloud_bot:,.2f})"))
            else:
                add(_verdict_neut("일목 구름대", f"구름 안 ({cloud_bot:,.2f}~{cloud_top:,.2f})"))
        else:
            add(_verdict_neut("일목 구름대", "데이터 부족"))

        # 17: OBV 추세 (5일 변화) — 누적 거래량 방향성
        if len(b.obv_v) >= 6:
            obv_now = float(b.obv_v.iloc[last])
            obv_prev = float(b.obv_v.iloc[-6])
            obv_change = obv_now - obv_prev
            base = abs(obv_prev) if obv_prev != 0 else (abs(obv_now) if obv_now != 0 else 1)
            obv_pct = (obv_change / base) * 100
            threshold = base * 0.02
            if obv_change > threshold:
                add(_verdict_up("OBV 누적거래량", f"5일 +{obv_pct:.1f}% (매수 누적)"))
            elif obv_change < -threshold:
                add(_verdict_down("OBV 누적거래량", f"5일 {obv_pct:+.1f}% (매도 누적)"))
            else:
                add(_verdict_neut("OBV 누적거래량", f"5일 {obv_pct:+.1f}% (정체)"))
        else:
            add(_verdict_neut("OBV 누적거래량", "-"))

        # 18: 거래량 (5일 평균)
        if len(b.volume) >= 6 and float(b.volume.iloc[-6:-1].mean()) > 0:
            avg5 = float(b.volume.iloc[-6:-1].mean())
            last_vol = float(b.volume.iloc[last])
            ratio = last_vol / avg5
            if ratio > 1.5:
                add(_verdict_up("거래량", f"5일평균의 {ratio:.1f}x (급증)"))
            elif ratio < 0.6:
                add(_verdict_down("거래량", f"5일평균의 {ratio:.1f}x (위축)"))
            else:
                add(_verdict_neut("거래량", f"5일평균의 {ratio:.1f}x"))
        else:
            add(_verdict_neut("거래량", "-"))

        # 종합 판정
        net = up - down
        if net >= 8:
            summary = "강한 상승 신호 (다지표 일치)"
        elif net >= 4:
            summary = "상승 우위"
        elif net >= 1:
            summary = "약한 상승"
        elif net <= -8:
            summary = "강한 하락 신호"
        elif net <= -4:
            summary = "하락 우위"
        elif net <= -1:
            summary = "약한 하락"
        else:
            summary = "혼조 / 방향성 불분명"

        return SignalResult(
            signal_type=self.name,
            score_up=up,
            score_down=down,
            score_neut=neut,
            summary=summary,
            details={
                "close": close,
                "rsi": round(rsi_v, 2),
                "adx": round(adx_v, 2),
                "macd_hist": round(macd_hist, 4),
                "pct_b": round(pct_b, 3),
                "checks": checks,
            },
        )


__all__ = ["ChartSignal"]

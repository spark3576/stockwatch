"""차트 패턴 시그널 — 캔들 패턴 + 추세선 교차 + 다이버전스.

체크 항목 (8개):
  1. 망치 / 슈팅스타 (단일 캔들 반전)
  2. 도지 (장중 의사결정 부재)
  3. 엔걸핑 (이중 캔들 반전)
  4. 모닝/이브닝 스타 (3중 캔들 반전)
  5. 5/20일 골든·데드 크로스
  6. 20/60일 골든·데드 크로스
  7. MACD 시그널선 골든·데드 크로스
  8. 가격-RSI 다이버전스
"""
from __future__ import annotations

import pandas as pd

from src.signals.base import Signal, SignalResult
from src.signals.indicators import compute_all
from src.utils.logger import logger


def _verdict_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _verdict_down(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _verdict_neut(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class ChartPattern(Signal):
    name = "차트 패턴"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        if df.empty or len(df) < 130:
            return SignalResult(signal_type=self.name, score_neut=8, summary="데이터 부족")

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

        o = df["open"].astype(float)
        h = df["high"].astype(float)
        l = df["low"].astype(float)
        c = df["close"].astype(float)

        # 1: 망치 / 슈팅스타 (최근 1봉)
        last_o, last_c, last_h, last_l = float(o.iloc[-1]), float(c.iloc[-1]), float(h.iloc[-1]), float(l.iloc[-1])
        body = abs(last_c - last_o)
        upper_shadow = last_h - max(last_o, last_c)
        lower_shadow = min(last_o, last_c) - last_l
        rng = last_h - last_l
        if rng > 0 and body / rng < 0.3:
            if lower_shadow > body * 2 and upper_shadow < body:
                # 하락 추세 끝에 망치면 반전 신호
                trend_5d = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0
                if trend_5d < -3:
                    add(_verdict_up("망치 캔들", f"하락추세({trend_5d:.1f}%) 끝 망치 — 반전 가능"))
                else:
                    add(_verdict_neut("망치 캔들", "망치 형태"))
            elif upper_shadow > body * 2 and lower_shadow < body:
                trend_5d = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0
                if trend_5d > 3:
                    add(_verdict_down("슈팅스타", f"상승추세({trend_5d:+.1f}%) 끝 슈팅스타 — 반전 가능"))
                else:
                    add(_verdict_neut("슈팅스타", "슈팅스타 형태"))
            else:
                add(_verdict_neut("망치/슈팅스타", "해당 없음"))
        else:
            add(_verdict_neut("망치/슈팅스타", "해당 없음"))

        # 2: 도지 (시가≈종가)
        if rng > 0 and body / rng < 0.1:
            add(_verdict_neut("도지", "결정 보류 (방향성 불분명)"))
        else:
            add(_verdict_neut("도지", "해당 없음"))

        # 3: 엔걸핑 (전봉을 다음봉이 완전히 감쌈)
        if len(c) >= 2:
            p_o, p_c = float(o.iloc[-2]), float(c.iloc[-2])
            # 강세 엔걸핑: 전봉 음봉 + 현봉 양봉이 전봉 완전 포함
            if p_c < p_o and last_c > last_o and last_o < p_c and last_c > p_o:
                add(_verdict_up("엔걸핑", "강세 엔걸핑 — 반전 매수신호"))
            elif p_c > p_o and last_c < last_o and last_o > p_c and last_c < p_o:
                add(_verdict_down("엔걸핑", "약세 엔걸핑 — 반전 매도신호"))
            else:
                add(_verdict_neut("엔걸핑", "해당 없음"))
        else:
            add(_verdict_neut("엔걸핑", "-"))

        # 4: 모닝/이브닝 스타 (3봉 패턴)
        if len(c) >= 3:
            o1, c1 = float(o.iloc[-3]), float(c.iloc[-3])
            o2, c2 = float(o.iloc[-2]), float(c.iloc[-2])
            o3, c3 = float(o.iloc[-1]), float(c.iloc[-1])
            body1 = abs(c1 - o1)
            body2 = abs(c2 - o2)
            body3 = abs(c3 - o3)
            # 모닝스타: 큰 음봉 → 작은봉(갭다운) → 큰 양봉(첫봉 중심 회복)
            if c1 < o1 and body1 > body2 * 2 and c3 > o3 and body3 > body2 * 2 and c3 > (o1 + c1) / 2:
                add(_verdict_up("모닝스타", "3봉 반전 매수 신호"))
            elif c1 > o1 and body1 > body2 * 2 and c3 < o3 and body3 > body2 * 2 and c3 < (o1 + c1) / 2:
                add(_verdict_down("이브닝스타", "3봉 반전 매도 신호"))
            else:
                add(_verdict_neut("모닝/이브닝 스타", "해당 없음"))
        else:
            add(_verdict_neut("모닝/이브닝 스타", "-"))

        # 5: 5/20 골든·데드 크로스
        gd_5_20 = self._cross_event(b.sma5, b.sma20, lookback=5)
        if gd_5_20 == "golden":
            add(_verdict_up("5/20 크로스", "5일선이 20일선 상향 돌파 (단기 골든)"))
        elif gd_5_20 == "dead":
            add(_verdict_down("5/20 크로스", "5일선이 20일선 하향 돌파 (단기 데드)"))
        else:
            ma5_v, ma20_v = float(b.sma5.iloc[-1]), float(b.sma20.iloc[-1])
            add(_verdict_neut("5/20 크로스", f"교차 없음 (MA5 {ma5_v:,.2f} / MA20 {ma20_v:,.2f})"))

        # 6: 20/60 골든·데드 크로스
        gd_20_60 = self._cross_event(b.sma20, b.sma60, lookback=10)
        if gd_20_60 == "golden":
            add(_verdict_up("20/60 크로스", "중기 골든크로스 발생 (10일내)"))
        elif gd_20_60 == "dead":
            add(_verdict_down("20/60 크로스", "중기 데드크로스 발생 (10일내)"))
        else:
            add(_verdict_neut("20/60 크로스", "교차 없음"))

        # 7: MACD 시그널선 크로스
        macd_line = b.macd_df["macd"]
        signal_line = b.macd_df["signal"]
        gd_macd = self._cross_event(macd_line, signal_line, lookback=5)
        if gd_macd == "golden":
            add(_verdict_up("MACD 크로스", "MACD가 시그널 상향 돌파 (5일내)"))
        elif gd_macd == "dead":
            add(_verdict_down("MACD 크로스", "MACD가 시그널 하향 돌파 (5일내)"))
        else:
            add(_verdict_neut("MACD 크로스", "교차 없음"))

        # 8: 가격-RSI 다이버전스 (최근 20일 저점/고점 비교)
        diverge = self._rsi_divergence(c, b.rsi14, lookback=20)
        if diverge == "bullish":
            add(_verdict_up("RSI 다이버전스", "강세 다이버전스 (가격↓ RSI↑)"))
        elif diverge == "bearish":
            add(_verdict_down("RSI 다이버전스", "약세 다이버전스 (가격↑ RSI↓)"))
        else:
            add(_verdict_neut("RSI 다이버전스", "해당 없음"))

        # 종합
        net = up - down
        if net >= 4:
            summary = "강한 반전·추세 신호"
        elif net >= 1:
            summary = "약한 상승 패턴"
        elif net <= -4:
            summary = "강한 하락 패턴"
        elif net <= -1:
            summary = "약한 하락 패턴"
        else:
            summary = "특별한 패턴 없음"

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, details={"checks": checks},
        )

    @staticmethod
    def _cross_event(line_a: pd.Series, line_b: pd.Series, lookback: int = 5) -> str | None:
        """최근 lookback일 내 a가 b를 교차한 이벤트.
        'golden' = a가 b를 상향 돌파, 'dead' = 하향 돌파, None = 교차 없음.
        """
        if len(line_a) < lookback + 2 or len(line_b) < lookback + 2:
            return None
        for i in range(1, lookback + 1):
            try:
                a_now, a_prev = float(line_a.iloc[-i]), float(line_a.iloc[-i - 1])
                b_now, b_prev = float(line_b.iloc[-i]), float(line_b.iloc[-i - 1])
            except (IndexError, ValueError):
                continue
            if pd.isna(a_now) or pd.isna(b_now) or pd.isna(a_prev) or pd.isna(b_prev):
                continue
            if a_prev <= b_prev and a_now > b_now:
                return "golden"
            if a_prev >= b_prev and a_now < b_now:
                return "dead"
        return None

    @staticmethod
    def _rsi_divergence(close: pd.Series, rsi: pd.Series, lookback: int = 20) -> str | None:
        """가격-RSI 다이버전스 단순 검출."""
        if len(close) < lookback + 2:
            return None
        c = close.tail(lookback)
        r = rsi.tail(lookback)
        # 가격 저점 두 개 (최근 절반 / 이전 절반)
        h1, h2 = c.iloc[: lookback // 2], c.iloc[lookback // 2:]
        try:
            price_low_a = float(h1.min())
            price_low_b = float(h2.min())
            rsi_low_a = float(r.iloc[: lookback // 2].min())
            rsi_low_b = float(r.iloc[lookback // 2:].min())
            price_high_a = float(h1.max())
            price_high_b = float(h2.max())
            rsi_high_a = float(r.iloc[: lookback // 2].max())
            rsi_high_b = float(r.iloc[lookback // 2:].max())
        except Exception:
            return None
        # 강세: 가격 더 낮은 저점 + RSI 더 높은 저점
        if price_low_b < price_low_a * 0.99 and rsi_low_b > rsi_low_a * 1.05:
            return "bullish"
        # 약세: 가격 더 높은 고점 + RSI 더 낮은 고점
        if price_high_b > price_high_a * 1.01 and rsi_high_b < rsi_high_a * 0.95:
            return "bearish"
        return None


__all__ = ["ChartPattern"]

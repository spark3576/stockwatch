"""돌파 시그널 — 박스권/신고가/이평선 돌파 + 거래량 동반 검증.

체크 항목 (8개):
  1. 52주 신고가 거리 (돌파 임박/돌파/멀리)
  2. 52주 신저가 거리
  3. 20일 박스권 상단 돌파
  4. 20일 박스권 하단 이탈
  5. 200일선 돌파/이탈 (장기 추세 변화)
  6. 갭상승 (전일 고가 < 오늘 시가)
  7. 갭하락 (전일 저가 > 오늘 시가)
  8. 돌파 거래량 동반 (3일평균 1.5배 이상)
"""
from __future__ import annotations

import pandas as pd

from src.signals.base import Signal, SignalResult
from src.signals.indicators import compute_all, sma


def _v_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _v_dn(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _v_n(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class BreakoutSignal(Signal):
    name = "돌파 차트"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        if df.empty or len(df) < 60:
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

        c = df["close"].astype(float)
        h = df["high"].astype(float)
        l = df["low"].astype(float)
        o = df["open"].astype(float) if "open" in df.columns else c
        v = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0] * len(c), index=c.index)
        last = float(c.iloc[-1])

        # 1: 52주 신고가
        hl52 = b.hl52
        if hl52["high_52w"]:
            from_high = hl52["from_high_pct"]
            if from_high >= -0.3:
                add(_v_up("52주 신고가", f"신고가 갱신 또는 근접 ({from_high:+.2f}%)"))
            elif from_high >= -3:
                add(_v_up("52주 신고가", f"신고가까지 {from_high:.1f}% — 돌파 임박"))
            elif from_high >= -10:
                add(_v_n("52주 신고가", f"신고가까지 {from_high:.1f}%"))
            else:
                add(_v_n("52주 신고가", f"신고가까지 {from_high:.1f}% — 멀리"))

            # 2: 52주 신저가
            from_low = hl52["from_low_pct"]
            if from_low <= 0.3:
                add(_v_dn("52주 신저가", f"신저가 부근 ({from_low:+.2f}%)"))
            elif from_low <= 3:
                add(_v_dn("52주 신저가", f"신저가에서 {from_low:.1f}% — 약세 지속"))
            else:
                add(_v_n("52주 신저가", f"신저가에서 {from_low:.1f}% 위"))
        else:
            add(_v_n("52주 신고가", "데이터 부족"))
            add(_v_n("52주 신저가", "데이터 부족"))

        # 3: 20일 박스권 상단
        # 4: 20일 박스권 하단
        if len(c) >= 21:
            box_high = float(h.iloc[-21:-1].max())
            box_low = float(l.iloc[-21:-1].min())
            high_pct = (last / box_high - 1) * 100
            low_pct = (last / box_low - 1) * 100

            # 상단
            if last > box_high * 1.001:
                add(_v_up("박스권 상단", f"20일 고점 {box_high:,.2f} 돌파 ({high_pct:+.1f}%)"))
            elif last >= box_high * 0.98:
                add(_v_n("박스권 상단", f"20일 고점 {box_high:,.2f}까지 {high_pct:+.1f}% (임박)"))
            else:
                add(_v_n("박스권 상단", f"20일 고점 {box_high:,.2f}까지 {high_pct:+.1f}%"))

            # 하단
            if last < box_low * 0.999:
                add(_v_dn("박스권 하단", f"20일 저점 {box_low:,.2f} 이탈 ({low_pct:+.1f}%)"))
            elif last <= box_low * 1.02:
                add(_v_n("박스권 하단", f"20일 저점 {box_low:,.2f}에서 {low_pct:+.1f}% (위험)"))
            else:
                add(_v_n("박스권 하단", f"20일 저점에서 {low_pct:+.1f}% 위 (안전)"))
        else:
            add(_v_n("박스권 상단", "데이터 부족"))
            add(_v_n("박스권 하단", "데이터 부족"))

        # 5: 200일선 돌파/이탈 (있으면)
        sma200 = sma(c, 200)
        if not pd.isna(sma200.iloc[-1]):
            ma200 = float(sma200.iloc[-1])
            ma200_5d = float(sma200.iloc[-6]) if len(sma200) >= 6 else ma200
            prev = float(c.iloc[-2])
            if prev < ma200 and last > ma200:
                add(_v_up("200일선 돌파", f"200일선 {ma200:,.2f} 상향 돌파"))
            elif prev > ma200 and last < ma200:
                add(_v_dn("200일선 이탈", f"200일선 {ma200:,.2f} 하향 이탈"))
            elif last > ma200 and ma200 > ma200_5d:
                add(_v_up("200일선 위치", f"200일선 위 + 200일선 상승"))
            elif last < ma200:
                add(_v_dn("200일선 위치", f"200일선({ma200:,.2f}) 아래"))
            else:
                add(_v_n("200일선 위치", f"200일선({ma200:,.2f}) 부근"))
        else:
            add(_v_n("200일선", "데이터 부족"))

        # 6: 갭상승, 7: 갭하락
        if len(c) >= 2:
            prev_high = float(h.iloc[-2])
            prev_low = float(l.iloc[-2])
            today_open = float(o.iloc[-1])
            if today_open > prev_high * 1.005:
                add(_v_up("갭상승", f"전일 고가 {prev_high:,.2f} → 오늘 시가 {today_open:,.2f}"))
                add(_v_n("갭하락", "해당 없음"))
            elif today_open < prev_low * 0.995:
                add(_v_n("갭상승", "해당 없음"))
                add(_v_dn("갭하락", f"전일 저가 {prev_low:,.2f} → 오늘 시가 {today_open:,.2f}"))
            else:
                add(_v_n("갭상승", "해당 없음"))
                add(_v_n("갭하락", "해당 없음"))
        else:
            add(_v_n("갭상승", "-"))
            add(_v_n("갭하락", "-"))

        # 8: 돌파 거래량 동반
        if len(v) >= 4 and float(v.iloc[-4:-1].mean()) > 0:
            avg3 = float(v.iloc[-4:-1].mean())
            today_vol = float(v.iloc[-1])
            ratio = today_vol / avg3
            today_change = (last / float(c.iloc[-2]) - 1) * 100 if len(c) >= 2 else 0
            if ratio >= 1.5 and today_change > 1.5:
                add(_v_up("거래량 폭발", f"3일평균 {ratio:.1f}x + 가격 {today_change:+.1f}%"))
            elif ratio >= 1.5 and today_change < -1.5:
                add(_v_dn("거래량 폭발", f"3일평균 {ratio:.1f}x + 가격 {today_change:.1f}% (매도 폭주)"))
            else:
                add(_v_n("거래량 폭발", f"3일평균 {ratio:.1f}x"))
        else:
            add(_v_n("거래량 폭발", "-"))

        # 종합 (체크 갯수가 일정하지 않을 수 있음 — 아래 정렬 단계에서 정규화)
        # 체크가 9개로 늘어났을 수 있어 8개로 자르거나 그대로 보고
        net = up - down
        if net >= 4:
            summary = "강한 돌파 신호"
        elif net >= 2:
            summary = "약한 돌파 가능성"
        elif net <= -4:
            summary = "강한 이탈 신호"
        elif net <= -2:
            summary = "약한 이탈 가능성"
        else:
            summary = "박스권 / 의미있는 돌파 없음"

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, details={"checks": checks},
        )


__all__ = ["BreakoutSignal"]

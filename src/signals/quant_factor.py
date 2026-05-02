"""퀀트 팩터 시그널 — 통계적 위험·수익 지표 종합.

10개 체크:
  1. 1M 수익률 (vs 시장)
  2. 3M 수익률 (vs 시장)
  3. 6M 수익률 (vs 시장)
  4. 12M 수익률 (vs 시장)
  5. 모멘텀 종합 점수 (가중평균)
  6. 베타 (vs 시장지수)
  7. 연환산 변동성 (60일 vs 252일)
  8. 샤프 비율 (위험조정 수익률)
  9. 최대 낙폭(MDD) (1년)
  10. VaR 95% (하루 최악의 5%일 손실)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.collectors.market_index import (
    fetch_market_index, market_index_name, risk_free_rate,
)
from src.signals.base import Signal, SignalResult
from src.utils.logger import logger


def _v_up(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↑", "reason": reason}


def _v_dn(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "↓", "reason": reason}


def _v_n(name: str, reason: str) -> dict:
    return {"name": name, "verdict": "△", "reason": reason}


class QuantFactor(Signal):
    name = "퀀트 팩터"

    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult:
        if df.empty or len(df) < 60:
            return SignalResult(self.name, score_neut=10, summary="데이터 부족")

        close = df["close"].astype(float)
        returns = close.pct_change().dropna()

        # 시장 지수 수집 (캐시)
        idx_df = fetch_market_index(market, days=400)
        idx_close = idx_df["close"].astype(float) if not idx_df.empty else pd.Series(dtype=float)
        idx_returns = idx_close.pct_change().dropna() if not idx_close.empty else pd.Series(dtype=float)
        idx_name = market_index_name(market)

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

        # 1~4: 기간별 수익률 (vs 시장)
        period_specs = [(20, "1M"), (60, "3M"), (120, "6M"), (240, "12M")]
        period_returns: dict[str, dict] = {}

        for days, label in period_specs:
            if len(close) < days + 1:
                add(_v_n(f"{label} 수익률", "데이터 부족"))
                continue

            stock_ret = (close.iloc[-1] / close.iloc[-(days + 1)] - 1) * 100

            mkt_ret = None
            if len(idx_close) >= days + 1:
                try:
                    mkt_ret = (idx_close.iloc[-1] / idx_close.iloc[-(days + 1)] - 1) * 100
                except IndexError:
                    mkt_ret = None

            if mkt_ret is not None:
                diff = stock_ret - mkt_ret
                msg = f"{stock_ret:+.1f}% (시장 {idx_name} {mkt_ret:+.1f}%, 차이 {diff:+.1f}%p)"
                # 알파(시장 초과수익) 임계: 기간 길수록 큰 폭 요구
                threshold = {"1M": 3, "3M": 5, "6M": 8, "12M": 12}[label]
                if diff > threshold:
                    add(_v_up(f"{label} 수익률 vs 시장", msg))
                elif diff < -threshold:
                    add(_v_dn(f"{label} 수익률 vs 시장", msg))
                else:
                    add(_v_n(f"{label} 수익률 vs 시장", msg))
            else:
                # 시장 데이터 없을 때는 절대 수익률만
                threshold = {"1M": 3, "3M": 8, "6M": 12, "12M": 20}[label]
                msg = f"{stock_ret:+.1f}% (시장 비교 불가)"
                if stock_ret > threshold:
                    add(_v_up(f"{label} 수익률", msg))
                elif stock_ret < -threshold:
                    add(_v_dn(f"{label} 수익률", msg))
                else:
                    add(_v_n(f"{label} 수익률", msg))

            period_returns[label] = {"stock": stock_ret, "market": mkt_ret}

        # 5: 모멘텀 종합 점수 (가중평균: 1M*0.1 + 3M*0.2 + 6M*0.3 + 12M*0.4)
        weights = {"1M": 0.1, "3M": 0.2, "6M": 0.3, "12M": 0.4}
        total_w = 0.0
        weighted_sum = 0.0
        market_weighted = 0.0
        for label, w in weights.items():
            if label in period_returns:
                r = period_returns[label]
                if r["stock"] is not None:
                    weighted_sum += r["stock"] * w
                    total_w += w
                if r["market"] is not None:
                    market_weighted += r["market"] * w
        if total_w > 0:
            mom_score = weighted_sum / total_w  # 정규화된 가중수익률 (%)
            mkt_score = market_weighted / total_w if market_weighted else None
            if mkt_score is not None:
                mom_diff = mom_score - mkt_score
                msg = f"가중수익률 {mom_score:+.1f}% (시장 {mkt_score:+.1f}%, 차이 {mom_diff:+.1f}%p)"
                if mom_diff > 5:
                    add(_v_up("모멘텀 종합", msg))
                elif mom_diff < -5:
                    add(_v_dn("모멘텀 종합", msg))
                else:
                    add(_v_n("모멘텀 종합", msg))
            else:
                msg = f"가중수익률 {mom_score:+.1f}%"
                if mom_score > 10:
                    add(_v_up("모멘텀 종합", msg))
                elif mom_score < -10:
                    add(_v_dn("모멘텀 종합", msg))
                else:
                    add(_v_n("모멘텀 종합", msg))
        else:
            add(_v_n("모멘텀 종합", "데이터 부족"))

        # 6: 베타 (시장 동조성)
        if not idx_returns.empty:
            aligned = pd.concat([returns, idx_returns], axis=1, join="inner").dropna()
            aligned.columns = ["stock", "idx"]
            tail = aligned.tail(252) if len(aligned) >= 252 else aligned
            if len(tail) >= 30:
                cov = tail["stock"].cov(tail["idx"])
                var = tail["idx"].var()
                if var > 0:
                    beta = cov / var
                    if beta > 1.3:
                        add(_v_n("베타", f"{beta:.2f} 공격형 (시장보다 변동성 {(beta-1)*100:+.0f}%)"))
                    elif beta < 0.7:
                        add(_v_n("베타", f"{beta:.2f} 방어형 (시장보다 변동성 {(beta-1)*100:+.0f}%)"))
                    else:
                        add(_v_n("베타", f"{beta:.2f} 시장 동조형"))
                else:
                    add(_v_n("베타", "분산 0"))
            else:
                add(_v_n("베타", f"교집합 부족 ({len(tail)}일)"))
        else:
            add(_v_n("베타", "시장 지수 없음"))

        # 7: 연환산 변동성 (60일 단기 vs 252일 장기 비교)
        if len(returns) >= 60:
            short_vol = float(returns.tail(60).std() * np.sqrt(252) * 100)
            long_vol = (
                float(returns.tail(252).std() * np.sqrt(252) * 100)
                if len(returns) >= 252 else short_vol
            )
            ratio = short_vol / long_vol if long_vol > 0 else 1
            msg = f"60일 {short_vol:.0f}% (1년 평균 {long_vol:.0f}%, {ratio:.2f}x)"
            if ratio > 1.3:
                add(_v_dn("연환산 변동성", msg + " — 위험 증가"))
            elif ratio < 0.7:
                add(_v_up("연환산 변동성", msg + " — 안정화"))
            else:
                add(_v_n("연환산 변동성", msg))
        else:
            add(_v_n("연환산 변동성", "데이터 부족"))

        # 8: 샤프 비율
        if len(returns) >= 60:
            yearly = returns.tail(252) if len(returns) >= 252 else returns
            ann_return = float(yearly.mean() * 252)
            ann_vol = float(yearly.std() * np.sqrt(252))
            rf = risk_free_rate(market)
            if ann_vol > 0:
                sharpe = (ann_return - rf) / ann_vol
                msg = f"{sharpe:.2f} (연수익 {ann_return*100:+.1f}%, 변동성 {ann_vol*100:.0f}%, 무위험 {rf*100:.1f}%)"
                if sharpe > 1.0:
                    add(_v_up("샤프 비율", msg + " — 우수"))
                elif sharpe < 0:
                    add(_v_dn("샤프 비율", msg + " — 손실"))
                else:
                    add(_v_n("샤프 비율", msg))
            else:
                add(_v_n("샤프 비율", "변동성 0"))
        else:
            add(_v_n("샤프 비율", "데이터 부족"))

        # 9: 최대 낙폭(MDD) — 1년
        if len(close) >= 60:
            window = close.tail(252) if len(close) >= 252 else close
            roll_max = window.cummax()
            drawdown = (window - roll_max) / roll_max * 100
            mdd = float(drawdown.min())
            mdd_date = drawdown.idxmin().strftime("%Y-%m-%d") if not pd.isna(mdd) else "?"
            msg = f"{mdd:.1f}% ({mdd_date})"
            if mdd > -10:
                add(_v_up("최대 낙폭(MDD)", msg + " — 양호"))
            elif mdd < -25:
                add(_v_dn("최대 낙폭(MDD)", msg + " — 위험"))
            else:
                add(_v_n("최대 낙폭(MDD)", msg))
        else:
            add(_v_n("최대 낙폭(MDD)", "데이터 부족"))

        # 10: VaR 95% (일일 수익률 5분위)
        if len(returns) >= 60:
            sample = returns.tail(252) if len(returns) >= 252 else returns
            var95 = float(sample.quantile(0.05) * 100)
            msg = f"하루 최악 5%일 {var95:+.2f}%"
            if var95 > -2:
                add(_v_up("VaR 95%", msg + " — 양호"))
            elif var95 < -4:
                add(_v_dn("VaR 95%", msg + " — 변동성↑"))
            else:
                add(_v_n("VaR 95%", msg))
        else:
            add(_v_n("VaR 95%", "데이터 부족"))

        # 종합
        net = up - down
        if net >= 4:
            summary = "강한 알파 (시장 초과수익)"
        elif net >= 2:
            summary = "양호한 위험조정 수익"
        elif net <= -4:
            summary = "심한 부진 / 위험 누적"
        elif net <= -2:
            summary = "약세 / 위험 증가"
        else:
            summary = "중립 / 시장 동조"

        return SignalResult(
            signal_type=self.name,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, details={"checks": checks},
        )


__all__ = ["QuantFactor"]

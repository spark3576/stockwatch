"""기술적 지표 통합 계산 모듈.

순수 pandas + ta 라이브러리 활용. 모든 시그널 모듈이 공통으로 사용.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# 추세 지표
# ─────────────────────────────────────────────────────────────────────────────

def sma(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(period, min_periods=1).mean()


def ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD: (macd_line, signal_line, histogram)."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ADX (추세 강도). 0~100, 25 이상이면 강한 추세."""
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down
    tr = pd.concat([
        (high - low),
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_v = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_v.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_v.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0)


# ─────────────────────────────────────────────────────────────────────────────
# 모멘텀 지표
# ─────────────────────────────────────────────────────────────────────────────

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Stochastic %K, %D."""
    lowest = low.rolling(k_period).min()
    highest = high.rolling(k_period).max()
    k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return pd.DataFrame({"k": k, "d": d})


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R: -100~0. -20 위 과매수, -80 아래 과매도."""
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, np.nan)


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index. ±100 밖이면 강한 신호."""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = (tp - sma_tp).abs().rolling(period).mean()
    return ((tp - sma_tp) / (0.015 * mad.replace(0, np.nan))).fillna(0)


def roc(close: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (%)"""
    return ((close / close.shift(period)) - 1) * 100


# ─────────────────────────────────────────────────────────────────────────────
# 변동성 지표
# ─────────────────────────────────────────────────────────────────────────────

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range — 변동성."""
    tr = pd.concat([
        (high - low),
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """볼린저 밴드: middle/upper/lower/%B/bandwidth."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    return pd.DataFrame({
        "mid": mid, "upper": upper, "lower": lower,
        "pct_b": pct_b, "bandwidth": bandwidth,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 거래량 지표
# ─────────────────────────────────────────────────────────────────────────────

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — 누적 거래량 추세."""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
         period: int = 20) -> pd.Series:
    """Volume Weighted Average Price (rolling N일 — 단기 매물대 평균).

    누적 VWAP은 시계열이 길수록 의미 약함 → 20일 rolling 표준."""
    tp = (high + low + close) / 3
    pv = tp * volume
    return pv.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)


def mfi(high: pd.Series, low: pd.Series, close: pd.Series,
        volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index. 0~100, 80 이상 과매수."""
    tp = (high + low + close) / 3
    raw_mf = tp * volume
    delta = tp.diff()
    pos_mf = raw_mf.where(delta > 0, 0).rolling(period).sum()
    neg_mf = raw_mf.where(delta < 0, 0).rolling(period).sum()
    mfr = pos_mf / neg_mf.replace(0, np.nan)
    return (100 - 100 / (1 + mfr)).fillna(50)


# ─────────────────────────────────────────────────────────────────────────────
# 일목균형표 (Ichimoku)
# ─────────────────────────────────────────────────────────────────────────────

def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
    """일목균형표 — 전환선/기준선/선행스팬1/선행스팬2/후행스팬."""
    conv = (high.rolling(9).max() + low.rolling(9).min()) / 2          # 전환선
    base = (high.rolling(26).max() + low.rolling(26).min()) / 2        # 기준선
    span_a = ((conv + base) / 2).shift(26)                              # 선행스팬1
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)  # 선행스팬2
    lagging = close.shift(-26)                                          # 후행스팬
    return pd.DataFrame({
        "conv": conv, "base": base,
        "span_a": span_a, "span_b": span_b,
        "lagging": lagging,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 지지/저항 (단순) + 신고가
# ─────────────────────────────────────────────────────────────────────────────

def support_resistance(high: pd.Series, low: pd.Series, lookback: int = 60,
                       n_levels: int = 3) -> dict:
    """간단한 피봇 기반 지지/저항 추출."""
    h = high.tail(lookback)
    l = low.tail(lookback)
    resistances = sorted(h.nlargest(n_levels * 2).unique(), reverse=True)[:n_levels]
    supports = sorted(l.nsmallest(n_levels * 2).unique())[:n_levels]
    return {"supports": supports, "resistances": resistances}


def high_low_52w(close: pd.Series, lookback_days: int = 252) -> dict:
    """52주(1년) 신고가/신저가 거리 (%)."""
    if len(close) < 5:
        return {"high_52w": None, "low_52w": None, "from_high_pct": None, "from_low_pct": None}
    window = close.tail(lookback_days)
    high_52 = float(window.max())
    low_52 = float(window.min())
    last = float(close.iloc[-1])
    return {
        "high_52w": high_52,
        "low_52w": low_52,
        "from_high_pct": ((last / high_52) - 1) * 100,
        "from_low_pct": ((last / low_52) - 1) * 100,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 통합 계산 — 한번에 모든 지표 계산
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IndicatorBundle:
    """모든 지표 계산 결과 묶음."""
    close: pd.Series
    high: pd.Series
    low: pd.Series
    volume: pd.Series

    # 추세
    sma5: pd.Series
    sma20: pd.Series
    sma60: pd.Series
    sma120: pd.Series
    ema12: pd.Series
    ema26: pd.Series
    macd_df: pd.DataFrame
    adx14: pd.Series

    # 모멘텀
    rsi14: pd.Series
    stoch: pd.DataFrame
    williams: pd.Series
    cci20: pd.Series
    roc12: pd.Series

    # 변동성
    atr14: pd.Series
    bb: pd.DataFrame

    # 거래량
    obv_v: pd.Series
    vwap_v: pd.Series
    mfi14: pd.Series

    # 일목
    ichi: pd.DataFrame

    # 종합
    sr: dict
    hl52: dict


def compute_all(df: pd.DataFrame) -> IndicatorBundle:
    """OHLCV DataFrame → 모든 지표 한번에 계산."""
    close = df["close"].astype(float)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0] * len(close), index=close.index)

    return IndicatorBundle(
        close=close, high=high, low=low, volume=volume,
        sma5=sma(close, 5), sma20=sma(close, 20),
        sma60=sma(close, 60), sma120=sma(close, 120),
        ema12=ema(close, 12), ema26=ema(close, 26),
        macd_df=macd(close), adx14=adx(high, low, close, 14),
        rsi14=rsi(close, 14), stoch=stochastic(high, low, close),
        williams=williams_r(high, low, close, 14),
        cci20=cci(high, low, close, 20), roc12=roc(close, 12),
        atr14=atr(high, low, close, 14), bb=bollinger_bands(close),
        obv_v=obv(close, volume), vwap_v=vwap(high, low, close, volume),
        mfi14=mfi(high, low, close, volume, 14),
        ichi=ichimoku(high, low, close),
        sr=support_resistance(high, low),
        hl52=high_low_52w(close),
    )


__all__ = [
    "sma", "ema", "macd", "adx",
    "rsi", "stochastic", "williams_r", "cci", "roc",
    "atr", "bollinger_bands",
    "obv", "vwap", "mfi",
    "ichimoku", "support_resistance", "high_low_52w",
    "IndicatorBundle", "compute_all",
]

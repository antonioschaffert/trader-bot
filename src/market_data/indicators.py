"""
Technical Indicators Module - Enhanced

Beyond basic RSI/SMA, a pro trader needs:
- ATR (Average True Range): for position sizing and stop placement
- ADX (Average Directional Index): trend strength, critical for regime detection
- Support/Resistance levels: from pivot points and recent swing highs/lows
- Rate of Change (ROC): momentum confirmation
- Keltner Channels: volatility-based bands, better than Bollinger for options
- Volume Profile: relative volume for confirmation
"""

import pandas as pd
import ta

from src.market_data.models import Bar, Indicators


def compute_indicators(bars: list[Bar]) -> Indicators:
    if len(bars) < 15:
        return Indicators()

    df = pd.DataFrame(
        {
            "close": [b.close for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "volume": [b.volume for b in bars],
        }
    )

    result = Indicators()

    if len(df) >= 50:
        result.sma_50 = df["close"].rolling(50).mean().iloc[-1]

    if len(df) >= 20:
        result.sma_20 = df["close"].rolling(20).mean().iloc[-1]
        bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
        result.upper_bollinger = bb.bollinger_hband().iloc[-1]
        result.lower_bollinger = bb.bollinger_lband().iloc[-1]

    rsi_indicator = ta.momentum.RSIIndicator(close=df["close"], window=14)
    rsi_series = rsi_indicator.rsi()
    if not rsi_series.isna().iloc[-1]:
        result.rsi = rsi_series.iloc[-1]

    if bars[-1].vwap:
        result.vwap = bars[-1].vwap

    if len(df) >= 26:
        macd_ind = ta.trend.MACD(close=df["close"], window_slow=26, window_fast=12, window_sign=9)
        macd_val = macd_ind.macd().iloc[-1]
        macd_sig = macd_ind.macd_signal().iloc[-1]
        macd_hist = macd_ind.macd_diff().iloc[-1]
        if not pd.isna(macd_val):
            result.macd = macd_val
            result.macd_signal = macd_sig
            result.macd_histogram = macd_hist

    if len(df) >= 20:
        result.volume_sma_20 = df["volume"].rolling(20).mean().iloc[-1]

    # --- Enhanced Indicators ---

    # ATR (Average True Range) - critical for position sizing and stop placement
    if len(df) >= 14:
        atr_ind = ta.volatility.AverageTrueRange(
            high=df["high"], low=df["low"], close=df["close"], window=14
        )
        atr_val = atr_ind.average_true_range().iloc[-1]
        if not pd.isna(atr_val):
            result.atr_14 = atr_val

    # ADX (Average Directional Index) - trend strength
    if len(df) >= 20:
        adx_ind = ta.trend.ADXIndicator(
            high=df["high"], low=df["low"], close=df["close"], window=14
        )
        adx_val = adx_ind.adx().iloc[-1]
        if not pd.isna(adx_val):
            result.adx = adx_val

    # Keltner Channels - volatility-based bands (ATR-based, better than BB for options)
    if len(df) >= 20:
        kc = ta.volatility.KeltnerChannel(
            high=df["high"], low=df["low"], close=df["close"],
            window=20, window_atr=14
        )
        kc_high = kc.keltner_channel_hband().iloc[-1]
        kc_low = kc.keltner_channel_lband().iloc[-1]
        if not pd.isna(kc_high):
            result.keltner_upper = kc_high
            result.keltner_lower = kc_low

    # Rate of change (10-period)
    if len(df) >= 11:
        result.roc_10 = (
            (df["close"].iloc[-1] - df["close"].iloc[-11]) / df["close"].iloc[-11] * 100
        )

    # Relative Volume (current volume vs 20-day average)
    if result.volume_sma_20 and result.volume_sma_20 > 0 and bars[-1].volume > 0:
        result.relative_volume = bars[-1].volume / result.volume_sma_20

    # Support and Resistance from recent swing points
    if len(df) >= 20:
        result.support, result.resistance = _find_support_resistance(df)

    # EMA 9 for short-term trend
    if len(df) >= 9:
        result.ema_9 = df["close"].ewm(span=9).mean().iloc[-1]

    # EMA 21 for medium-term trend
    if len(df) >= 21:
        result.ema_21 = df["close"].ewm(span=21).mean().iloc[-1]

    return result


def _find_support_resistance(df: pd.DataFrame) -> tuple[float | None, float | None]:
    """
    Find the nearest support and resistance levels using swing highs/lows.
    Looks at the last 20 bars for local peaks and troughs.
    """
    highs = df["high"].values
    lows = df["low"].values
    close = df["close"].iloc[-1]

    # Find swing highs (higher than both neighbors)
    swing_highs = []
    swing_lows = []
    lookback = min(len(df) - 2, 20)

    for i in range(len(df) - lookback, len(df) - 1):
        if i < 1:
            continue
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            swing_lows.append(lows[i])

    # Nearest resistance above current price
    resistance = None
    above = [h for h in swing_highs if h > close]
    if above:
        resistance = min(above)

    # Nearest support below current price
    support = None
    below = [l for l in swing_lows if l < close]
    if below:
        support = max(below)

    return support, resistance


def compute_iv_rank(
    current_iv: float, iv_history: list[float]
) -> float | None:
    if not iv_history:
        return None
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    if iv_max == iv_min:
        return 50.0
    return ((current_iv - iv_min) / (iv_max - iv_min)) * 100


def compute_iv_percentile(current_iv: float, iv_history: list[float]) -> float | None:
    """
    IV Percentile: what % of days had IV lower than today.
    More robust than IV Rank for identifying premium-selling opportunities.
    """
    if not iv_history:
        return None
    count_below = sum(1 for iv in iv_history if iv < current_iv)
    return (count_below / len(iv_history)) * 100

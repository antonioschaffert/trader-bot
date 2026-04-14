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

    return result


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

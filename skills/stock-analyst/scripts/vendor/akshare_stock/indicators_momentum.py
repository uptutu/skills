"""动量/摆动类技术指标：RSI / KDJ / CCI / BIAS。

输入列约定：
    close 必选（RSI / BIAS）
    high/low 必选（KDJ / CCI）
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---- RSI ----------------------------------------------------------------------

def add_rsi(df: pd.DataFrame, *, n: int = 14) -> pd.DataFrame:
    """追加 RSI(n) 列。经典 Wilder 平滑。"""
    out = df.copy()
    close = out["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    out[f"RSI{n}"] = rsi
    return out


# ---- KDJ ----------------------------------------------------------------------

def add_kdj(df: pd.DataFrame, *, n: int = 9, k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
    """追加 KDJ 三列：K / D / J。

    公式：
        RSV = (close - low_n) / (high_n - low_n) * 100
        K = EMA(RSV, α=1/3)  ; D = EMA(K, α=1/3)  ; J = 3K - 2D
    """
    out = df.copy()
    low_n = out["low"].astype(float).rolling(window=n, min_periods=1).min()
    high_n = out["high"].astype(float).rolling(window=n, min_periods=1).max()
    rsv = (out["close"].astype(float) - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    rsv = rsv.fillna(0.0)
    k = rsv.ewm(alpha=1 / k_period, adjust=False).mean()
    d = k.ewm(alpha=1 / d_period, adjust=False).mean()
    j = 3 * k - 2 * d
    out["KDJ_K"] = k
    out["KDJ_D"] = d
    out["KDJ_J"] = j
    return out


# ---- CCI ----------------------------------------------------------------------

def add_cci(df: pd.DataFrame, *, n: int = 14) -> pd.DataFrame:
    """追加 CCI(n) 列。

    公式：
        TP  = (high + low + close) / 3
        MA_TP = TP 的 N 日 SMA
        MD  = |TP - MA_TP| 的 N 日平均
        CCI = (TP - MA_TP) / (0.015 × MD)
    """
    out = df.copy()
    tp = (out["high"].astype(float) + out["low"].astype(float) + out["close"].astype(float)) / 3.0
    ma_tp = tp.rolling(window=n, min_periods=1).mean()
    md = (tp - ma_tp).abs().rolling(window=n, min_periods=1).mean()
    cci = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))
    out[f"CCI{n}"] = cci
    return out


# ---- BIAS ---------------------------------------------------------------------

def add_bias(df: pd.DataFrame, *, n: int = 6) -> pd.DataFrame:
    """追加 BIAS(n) = (close - MA(n)) / MA(n) × 100。"""
    out = df.copy()
    close = out["close"].astype(float)
    ma = close.rolling(window=n, min_periods=1).mean()
    out[f"BIAS{n}"] = (close - ma) / ma.replace(0, np.nan) * 100.0
    return out

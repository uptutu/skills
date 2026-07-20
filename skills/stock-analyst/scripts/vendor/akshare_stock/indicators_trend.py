"""趋势类技术指标：MA / MACD / DMA。

输入列约定：``close`` 必选。所有函数返回新 DataFrame，不修改原 df。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---- 移动平均线 ---------------------------------------------------------------

def add_ma(df: pd.DataFrame, windows: tuple[int, ...] = (5, 10, 20, 60)) -> pd.DataFrame:
    """为收盘价追加 N 日移动平均列 ``MA{n}``。"""
    out = df.copy()
    close = out["close"].astype(float)
    for w in windows:
        out[f"MA{w}"] = close.rolling(window=w, min_periods=1).mean()
    return out


# ---- MACD ---------------------------------------------------------------------

def add_macd(
    df: pd.DataFrame,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """追加 MACD 三列：DIF / DEA / MACD（柱状）。

    算法与国内券商（同花顺/通达信/东方财富）一致：
        EMA(N) 初值 = close[0]
        EMA(N)_t = α × close_t + (1-α) × EMA(N)_{t-1},   α = 2/(N+1)
        DIF  = EMA(fast) - EMA(slow)
        DEA  = EMA(DIF, signal)
        HIST = (DIF - DEA) × 2
    """
    out = df.copy()
    close = out["close"].astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    out["MACD_DIF"] = dif
    out["MACD_DEA"] = dea
    out["MACD_HIST"] = (dif - dea) * 2
    return out


# ---- DMA（平均差 / 平行线差） ------------------------------------------------

def add_dma(df: pd.DataFrame, *, fast: int = 10, slow: int = 50, signal: int = 10) -> pd.DataFrame:
    """追加 DMA 指标：DMA=MA(fast)-MA(slow)，AMA=DMA 的 MA(signal)。"""
    out = df.copy()
    close = out["close"].astype(float)
    ma_fast = close.rolling(window=fast, min_periods=1).mean()
    ma_slow = close.rolling(window=slow, min_periods=1).mean()
    dma = ma_fast - ma_slow
    ama = dma.rolling(window=signal, min_periods=1).mean()
    out["DMA"] = dma
    out["AMA"] = ama
    return out

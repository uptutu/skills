"""形态/波动类指标：BOLL / 枢轴点 / 斐波那契 / 跳空 / 突破。

输入列约定：close 必选；high/low 必选（除 BOLL 仅用 close 外）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---- BOLL 布林带 ---------------------------------------------------------------

def add_boll(df: pd.DataFrame, *, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """追加布林带：BOLL_MID / BOLL_UPPER / BOLL_LOWER。"""
    out = df.copy()
    close = out["close"].astype(float)
    mid = close.rolling(window=n, min_periods=1).mean()
    std = close.rolling(window=n, min_periods=1).std(ddof=0)
    out["BOLL_MID"] = mid
    out["BOLL_UPPER"] = mid + k * std
    out["BOLL_LOWER"] = mid - k * std
    return out


# ---- 枢轴点 -------------------------------------------------------------------

def add_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """追加枢轴点 P/R1/R2/R3/S1/S2/S3（基于昨 high/low/close）。"""
    out = df.copy()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    close = out["close"].astype(float)
    h_prev = high.shift(1)
    l_prev = low.shift(1)
    c_prev = close.shift(1)
    p = (h_prev + l_prev + c_prev) / 3.0
    out["PIVOT_P"] = p
    out["PIVOT_R1"] = 2 * p - l_prev
    out["PIVOT_S1"] = 2 * p - h_prev
    out["PIVOT_R2"] = p + (h_prev - l_prev)
    out["PIVOT_S2"] = p - (h_prev - l_prev)
    out["PIVOT_R3"] = h_prev + 2 * (p - l_prev)
    out["PIVOT_S3"] = l_prev - 2 * (h_prev - p)
    return out


# ---- 斐波那契回调 -------------------------------------------------------------

def add_fibonacci(df: pd.DataFrame, *, lookback: int = 60) -> pd.DataFrame:
    """追加斐波那契回调位 0/236/382/500/618/786/100（基于最近 lookback 日 high/low）。"""
    out = df.copy()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    hh = high.rolling(window=lookback, min_periods=1).max()
    ll = low.rolling(window=lookback, min_periods=1).min()
    rng = hh - ll
    out["FIB_0"] = hh
    out["FIB_236"] = hh - 0.236 * rng
    out["FIB_382"] = hh - 0.382 * rng
    out["FIB_500"] = hh - 0.500 * rng
    out["FIB_618"] = hh - 0.618 * rng
    out["FIB_786"] = hh - 0.786 * rng
    out["FIB_100"] = ll
    return out


# ---- 跳空缺口 -----------------------------------------------------------------

def add_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """追加跳空缺口检测列 GAP_TYPE：0=无 / 1=上跳 / -1=下跳。"""
    out = df.copy()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    close = out["close"].astype(float)
    prev_close = close.shift(1)

    gap_up = low > prev_high
    gap_down = high < prev_low
    out["GAP_TYPE"] = gap_up.astype(int) - gap_down.astype(int)

    if "open" in out.columns:
        open_ = out["open"].astype(float)
        gap_pct = (open_ / prev_close - 1.0) * 100.0
    else:
        gap_pct = pd.Series(0.0, index=out.index)
    out["GAP_SIZE"] = gap_pct * out["GAP_TYPE"].abs()
    return out


# ---- Donchian 突破信号 --------------------------------------------------------

def add_breakout(df: pd.DataFrame, *, n: int = 20) -> pd.DataFrame:
    """追加 N 日 Donchian 突破信号：BREAKOUT_UP=1 当日 high>前 N 日最高。"""
    out = df.copy()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    prev_high_n = high.shift(1).rolling(window=n, min_periods=1).max()
    prev_low_n = low.shift(1).rolling(window=n, min_periods=1).min()
    out["BREAKOUT_UP"] = (high > prev_high_n).astype(int)
    out["BREAKOUT_DOWN"] = (low < prev_low_n).astype(int)
    return out

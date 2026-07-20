"""成交量类技术指标：OBV / 量比 / MFI / 量价共振。

输入列约定：
    close 必选
    volume 或 amount 二选一（OBV/量比/MFI 用 amount 替代 volume，国内 K 线常缺 volume）
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _amount_col(df: pd.DataFrame) -> str | None:
    """优先 volume，回退 amount。"""
    if "volume" in df.columns:
        return "volume"
    if "amount" in df.columns:
        return "amount"
    return None


# ---- OBV（能量潮） -------------------------------------------------------------

def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """追加 OBV 列：close 上涨时累加 amount，下跌时累减 amount。

    用成交额代替成交量：金额即真实资金流动，机构投资者更准确。
    """
    out = df.copy()
    col = _amount_col(df)
    if col is None:
        return out
    close = out["close"].astype(float)
    amount = out[col].astype(float)
    direction = np.sign(close.diff()).fillna(0.0)
    out["OBV"] = (direction * amount).cumsum()
    return out


# ---- 量比 ---------------------------------------------------------------------

def add_volume_ratio(df: pd.DataFrame, *, n: int = 5) -> pd.DataFrame:
    """追加 VR(n) = 当日 amount / 过去 N 日均 amount。"""
    out = df.copy()
    col = _amount_col(df)
    if col is None:
        return out
    amount = out[col].astype(float)
    avg = amount.rolling(window=n, min_periods=1).mean()
    out[f"VR{n}"] = amount / avg.replace(0, np.nan)
    return out


# ---- MFI（资金流量指标） -------------------------------------------------------

def add_mfi(df: pd.DataFrame, *, n: int = 14) -> pd.DataFrame:
    """追加 MFI(n)：典型价格 × 资金流量的 RSI。"""
    out = df.copy()
    col = _amount_col(df)
    if col is None:
        return out
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    close = out["close"].astype(float)
    amount = out[col].astype(float)
    tp = (high + low + close) / 3.0
    raw_mf = tp * amount
    tp_diff = tp.diff()
    positive = raw_mf.where(tp_diff > 0, 0.0)
    negative = raw_mf.where(tp_diff < 0, 0.0)
    pos_sum = positive.rolling(window=n, min_periods=1).sum()
    neg_sum = negative.rolling(window=n, min_periods=1).sum()
    ratio = pos_sum / neg_sum.replace(0, np.nan)
    out[f"MFI{n}"] = 100 - 100 / (1 + ratio)
    return out


# ---- 量价共振 -----------------------------------------------------------------

def add_volume_price_signal(df: pd.DataFrame) -> pd.DataFrame:
    """追加量价共振信号 VP_SIGNAL：-2/0/2 表示出货/平/健康上涨。"""
    out = df.copy()
    close = out["close"].astype(float)
    price_dir = np.sign(close.diff()).fillna(0.0)
    col = _amount_col(df)
    if col is None:
        sig = pd.Series(0, index=out.index, dtype=int)
        sig[price_dir > 0] = 1
        sig[price_dir < 0] = -1
        out["VP_SIGNAL"] = sig
        return out
    amount = out[col].astype(float)
    amt_avg = amount.rolling(window=5, min_periods=1).mean().shift(1)
    amt_up = amount > amt_avg * 1.05
    amt_down = amount < amt_avg * 0.95
    sig = pd.Series(0, index=out.index, dtype=int)
    sig[price_dir > 0] = 1
    sig[price_dir < 0] = -1
    sig[(price_dir > 0) & amt_up] = 2
    sig[(price_dir < 0) & amt_down] = -1
    sig[(price_dir < 0) & amt_up] = -2
    sig[(price_dir > 0) & amt_down] = 1
    out["VP_SIGNAL"] = sig
    return out

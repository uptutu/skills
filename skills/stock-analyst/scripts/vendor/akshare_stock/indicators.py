"""技术指标聚合入口。

单个指标实现在子模块：
    indicators_trend     MA / MACD / DMA
    indicators_momentum  RSI / KDJ / CCI / BIAS
    indicators_volume    OBV / 量比 / MFI / 量价共振
    indicators_pattern   BOLL / 枢轴点 / 斐波那契 / 跳空 / 突破

信号摘要见 ``signals.py``。
"""
from __future__ import annotations

import pandas as pd

from .indicators_trend import add_dma, add_ma, add_macd
from .indicators_momentum import add_bias, add_cci, add_kdj, add_rsi
from .indicators_volume import (
    add_mfi,
    add_obv,
    add_volume_price_signal,
    add_volume_ratio,
)
from .indicators_pattern import (
    add_boll,
    add_breakout,
    add_fibonacci,
    add_gaps,
    add_pivot,
)
from .signals import latest_signals

__all__ = [
    "add_ma", "add_macd", "add_dma",
    "add_rsi", "add_kdj", "add_cci", "add_bias",
    "add_obv", "add_volume_ratio", "add_mfi", "add_volume_price_signal",
    "add_boll", "add_pivot", "add_fibonacci", "add_gaps", "add_breakout",
    "add_all", "latest_signals",
]


def add_all(df: pd.DataFrame, *, macd_params: tuple[int, int, int] = (12, 26, 9)) -> pd.DataFrame:
    """一次性追加全部 16 类技术指标。"""
    df = add_ma(df)
    df = add_macd(df, fast=macd_params[0], slow=macd_params[1], signal=macd_params[2])
    df = add_kdj(df)
    df = add_boll(df)
    df = add_rsi(df)
    df = add_dma(df)
    df = add_cci(df)
    df = add_bias(df)
    df = add_obv(df)
    df = add_volume_ratio(df)
    df = add_mfi(df)
    df = add_pivot(df)
    df = add_fibonacci(df)
    df = add_gaps(df)
    df = add_breakout(df)
    df = add_volume_price_signal(df)
    return df

"""信号摘要：聚合 4 类信号（趋势 / 动量 / 成交量 / 形态），输出 16 条。"""
from __future__ import annotations

import pandas as pd

from .signals_momentum import momentum_signals
from .signals_pattern import pattern_signals
from .signals_trend import trend_signals
from .signals_volume import volume_signals


def _safe_last(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def latest_signals(df: pd.DataFrame) -> list[str]:
    """基于最新一行的指标值，生成人类可读的信号摘要（4 大类共 16 条）。"""
    if df.empty:
        return ["数据不足"]
    close = _safe_last(df["close"])  # type: ignore[arg-type]
    return (
        trend_signals(df, close)
        + momentum_signals(df, close)
        + volume_signals(df)
        + pattern_signals(df, close)
    )

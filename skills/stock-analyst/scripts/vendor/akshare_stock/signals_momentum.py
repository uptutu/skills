"""信号子模块：动量类信号（RSI / KDJ / BOLL）。"""
from __future__ import annotations

import pandas as pd


def _safe_last(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _next_col(df: pd.DataFrame, prefix: str) -> str | None:
    return next((c for c in df.columns if c.startswith(prefix)), None)


def momentum_signals(df: pd.DataFrame, close: float | None) -> list[str]:
    out: list[str] = []
    rsi_col = _next_col(df, "RSI")
    if rsi_col is not None:
        rsi = _safe_last(df[rsi_col])
        if rsi is None:
            out.append("RSI：数据不足")
        elif rsi >= 70:
            out.append(f"RSI({rsi_col[3:]})={rsi:.1f} 超买")
        elif rsi <= 30:
            out.append(f"RSI({rsi_col[3:]})={rsi:.1f} 超卖")
        else:
            out.append(f"RSI({rsi_col[3:]})={rsi:.1f}")
    else:
        out.append("RSI：数据不足")

    k = _safe_last(df.get("KDJ_K", pd.Series(dtype=float)))
    d = _safe_last(df.get("KDJ_D", pd.Series(dtype=float)))
    j = _safe_last(df.get("KDJ_J", pd.Series(dtype=float)))
    if k is not None and d is not None and j is not None:
        if j >= 100 or k >= 80:
            tag = "超买"
        elif j <= 0 or k <= 20:
            tag = "超卖"
        else:
            tag = "中性"
        out.append(f"KDJ K={k:.1f} D={d:.1f} J={j:.1f} {tag}")
    else:
        out.append("KDJ：数据不足")

    mid = _safe_last(df.get("BOLL_MID", pd.Series(dtype=float)))
    upper = _safe_last(df.get("BOLL_UPPER", pd.Series(dtype=float)))
    lower = _safe_last(df.get("BOLL_LOWER", pd.Series(dtype=float)))
    if mid is not None and upper is not None and lower is not None and close is not None:
        pos = "上轨外" if close > upper else "下轨外" if close < lower else "中轨附近"
        out.append(f"BOLL 上轨={upper:.2f} 中轨={mid:.2f} 下轨={lower:.2f}（{pos}）")
    else:
        out.append("BOLL：数据不足")
    return out

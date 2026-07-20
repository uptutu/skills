"""信号子模块：形态类信号（枢轴点 / 斐波那契 / 跳空 / 突破）。"""
from __future__ import annotations

import pandas as pd


def _safe_last(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def pattern_signals(df: pd.DataFrame, close: float | None) -> list[str]:
    out: list[str] = []
    pivot = _safe_last(df.get("PIVOT_P", pd.Series(dtype=float)))
    r1 = _safe_last(df.get("PIVOT_R1", pd.Series(dtype=float)))
    s1 = _safe_last(df.get("PIVOT_S1", pd.Series(dtype=float)))
    if pivot is not None and r1 is not None and s1 is not None and close is not None:
        pos = "中枢之上" if close > pivot else "中枢之下"
        out.append(f"枢轴点: P={pivot:.2f} R1={r1:.2f} S1={s1:.2f}（{pos}）")
    else:
        out.append("枢轴点：数据不足")

    fib382 = _safe_last(df.get("FIB_382", pd.Series(dtype=float)))
    fib618 = _safe_last(df.get("FIB_618", pd.Series(dtype=float)))
    fib0 = _safe_last(df.get("FIB_0", pd.Series(dtype=float)))
    fib100 = _safe_last(df.get("FIB_100", pd.Series(dtype=float)))
    if all(v is not None for v in (fib382, fib618, fib0, fib100, close)):
        if close >= fib382:
            zone = "强势区（382 上方）"
        elif close >= fib618:
            zone = "回调区（382-618）"
        else:
            zone = "弱势区（618 下方）"
        out.append(f"斐波那契: 顶={fib0:.2f} 底={fib100:.2f} 382={fib382:.2f} 618={fib618:.2f}（{zone}）")
    else:
        out.append("斐波那契：数据不足")

    gap = _safe_last(df.get("GAP_TYPE", pd.Series(dtype=float)))
    gap_size = _safe_last(df.get("GAP_SIZE", pd.Series(dtype=float)))
    if gap is not None and gap != 0:
        direction = "向上跳空" if gap > 0 else "向下跳空"
        size = abs(gap_size) if gap_size is not None else 0
        out.append(f"最近跳空: {direction} {size:+.2f}%")
    else:
        out.append("跳空缺口: 无")

    bo_up = _safe_last(df.get("BREAKOUT_UP", pd.Series(dtype=float)))
    bo_down = _safe_last(df.get("BREAKOUT_DOWN", pd.Series(dtype=float)))
    if bo_up is not None and bo_down is not None:
        if bo_up == 1:
            out.append("突破: ↑ 突破 20 日新高")
        elif bo_down == 1:
            out.append("突破: ↓ 跌破 20 日新低")
        else:
            out.append("突破: 区间内运行")
    else:
        out.append("突破：数据不足")
    return out

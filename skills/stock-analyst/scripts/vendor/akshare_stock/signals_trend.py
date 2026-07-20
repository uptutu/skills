"""信号子模块：趋势类信号（MA / MACD / DMA / CCI / BIAS）。"""
from __future__ import annotations

import pandas as pd


def _safe_last(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _next_col(df: pd.DataFrame, prefix: str) -> str | None:
    return next((c for c in df.columns if c.startswith(prefix)), None)


def trend_signals(df: pd.DataFrame, close: float | None) -> list[str]:
    """MA / MACD / DMA / CCI / BIAS。"""
    out: list[str] = []
    ma5 = _safe_last(df.get("MA5", pd.Series(dtype=float)))
    ma20 = _safe_last(df.get("MA20", pd.Series(dtype=float)))
    if ma5 is not None and ma20 is not None:
        cross = "上穿" if ma5 > ma20 else "下穿"
        tag = "金叉" if ma5 > ma20 else "死叉"
        out.append(f"MA5={ma5:.2f} MA20={ma20:.2f} → MA5 {cross} MA20（{tag}）")
    else:
        out.append("MA 指标：数据不足")

    dif = _safe_last(df.get("MACD_DIF", pd.Series(dtype=float)))
    dea = _safe_last(df.get("MACD_DEA", pd.Series(dtype=float)))
    hist = _safe_last(df.get("MACD_HIST", pd.Series(dtype=float)))
    if dif is not None and dea is not None and hist is not None:
        direction = "多头" if dif > dea else "空头"
        out.append(
            f"MACD DIF={dif:+.3f} DEA={dea:+.3f} 柱={hist:+.3f} ({direction})；"
            f"柱>0=多头动能，<0=空头动能"
        )
    else:
        out.append("MACD：数据不足")

    dma = _safe_last(df.get("DMA", pd.Series(dtype=float)))
    ama = _safe_last(df.get("AMA", pd.Series(dtype=float)))
    if dma is not None and ama is not None:
        out.append(f"DMA={dma:+.2f} AMA={ama:+.2f} ({'多头' if dma > ama else '空头'}趋势)")
    else:
        out.append("DMA：数据不足")

    cci_col = _next_col(df, "CCI")
    if cci_col is not None:
        cci = _safe_last(df[cci_col])
        if cci is None:
            out.append("CCI：数据不足")
        elif cci >= 100:
            out.append(f"CCI({cci_col[3:]})={cci:.1f} 超买（警惕回调）")
        elif cci <= -100:
            out.append(f"CCI({cci_col[3:]})={cci:.1f} 超卖（关注反弹）")
        else:
            out.append(f"CCI({cci_col[3:]})={cci:.1f}")
    else:
        out.append("CCI：数据不足")

    bias_col = _next_col(df, "BIAS")
    if bias_col is not None:
        bias = _safe_last(df[bias_col])
        if bias is None:
            out.append("BIAS：数据不足")
        elif abs(bias) >= 5:
            tag = "超买（短线回调风险）" if bias > 0 else "超卖（短线反弹机会）"
            out.append(f"BIAS({bias_col[4:]})={bias:+.2f}% {tag}")
        else:
            out.append(f"BIAS({bias_col[4:]})={bias:+.2f}%")
    else:
        out.append("BIAS：数据不足")
    return out

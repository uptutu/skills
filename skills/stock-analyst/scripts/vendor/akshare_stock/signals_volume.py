"""信号子模块：成交量类信号（OBV / 量比 / MFI / 量价共振）。"""
from __future__ import annotations

import pandas as pd


_VP_LABELS = {
    2: "价升量增（健康上涨）",
    1: "价升量缩（上涨乏力）",
    -1: "价跌量缩（健康下跌）",
    -2: "价跌量增（出货/恐慌，警惕）",
    0: "平盘/量平",
}


def _safe_last(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _next_col(df: pd.DataFrame, prefix: str) -> str | None:
    return next((c for c in df.columns if c.startswith(prefix)), None)


def volume_signals(df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    obv = _safe_last(df.get("OBV", pd.Series(dtype=float)))
    if obv is not None:
        s = df["OBV"].dropna()
        if len(s) >= 2 and float(s.iloc[-2]) != 0:
            prev = float(s.iloc[-2])
            chg = (obv - prev) / abs(prev) * 100
            out.append(f"OBV={obv/1e8:.2f}亿 ({chg:+.1f}% {'流入' if obv > prev else '流出'})")
        else:
            out.append(f"OBV={obv/1e8:.2f}亿")
    else:
        out.append("OBV：数据不足")

    vr_col = _next_col(df, "VR")
    if vr_col is not None:
        vr = _safe_last(df[vr_col])
        if vr is None:
            out.append("量比：数据不足")
        elif vr >= 2.0:
            out.append(f"量比({vr_col[2:]})={vr:.2f} 显著放量")
        elif vr >= 1.2:
            out.append(f"量比({vr_col[2:]})={vr:.2f} 温和放量")
        elif vr <= 0.5:
            out.append(f"量比({vr_col[2:]})={vr:.2f} 显著缩量")
        elif vr < 1.0:
            out.append(f"量比({vr_col[2:]})={vr:.2f} 缩量")
        else:
            out.append(f"量比({vr_col[2:]})={vr:.2f} 正常")
    else:
        out.append("量比：数据不足")

    mfi_col = _next_col(df, "MFI")
    if mfi_col is not None:
        mfi = _safe_last(df[mfi_col])
        if mfi is None:
            out.append("MFI：数据不足")
        elif mfi >= 80:
            out.append(f"MFI({mfi_col[3:]})={mfi:.1f} 超买（资金流入过旺）")
        elif mfi <= 20:
            out.append(f"MFI({mfi_col[3:]})={mfi:.1f} 超卖（资金流出过旺）")
        else:
            out.append(f"MFI({mfi_col[3:]})={mfi:.1f}")
    else:
        out.append("MFI：数据不足")

    vp = _safe_last(df.get("VP_SIGNAL", pd.Series(dtype=float)))
    if vp is not None:
        out.append(f"量价共振: {_VP_LABELS.get(int(vp), '未知')}")
    else:
        out.append("量价共振：数据不足")
    return out

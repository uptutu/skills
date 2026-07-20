"""财务数据。数据源：akshare 东方财富利润表 + 资产负债表（沙箱可用）。"""
from __future__ import annotations

import logging
from typing import Callable

import pandas as pd

from .retry import call_with_retry

logger = logging.getLogger(__name__)


def _ak():
    import akshare as ak
    return ak


# 利润表 → 关键指标
_PL_KEYS = {
    "TOTAL_OPERATE_INCOME": "revenue",         # 营业总收入
    "OPERATE_INCOME": "revenue",
    "PARENT_NETPROFIT": "net_profit",          # 归母净利润
    "NETPROFIT": "net_profit",
    "BASIC_EPS": "eps",                        # 基本每股收益
    "EPSJB": "eps",
    "TOTAL_PROFIT": "total_profit",
}


def fetch_main_indicators(
    symbol: str,
    *,
    limit: int = 8,
    sleep: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """获取最近 ``limit`` 个报告期的主要财务指标。

    沙箱环境使用 stock_profit_sheet_by_report_em（东方财富利润表）。
    """
    sleeper = sleep or (lambda s: None)
    ak = _ak()

    # 6 位代码转东方财富格式：'SH600519'
    sec = _to_em_symbol(symbol)

    df = call_with_retry(
        lambda: ak.stock_profit_sheet_by_report_em(symbol=sec),
        sleep=sleeper,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    # 列名是英文大写；按 REPORT_DATE 倒序取最近 limit 期
    date_col = "REPORT_DATE" if "REPORT_DATE" in df.columns else df.columns[0]
    df = df.sort_values(date_col, ascending=False).head(limit).reset_index(drop=True)

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date": str(r.get(date_col, ""))[:10],
            "eps": _pick(r, ["BASIC_EPS", "EPSJB", "EPS"]),
            "bps": _pick(r, ["BPS", "PER_NETCASH"]),
            "roe": None,  # 需要资产负债表才计算
            "gross_margin": _pick(r, ["SALE_GROSS_PROFIT_RATE", "GROSS_PROFIT_RATE"]),
            "net_margin": _calc_margin(r),
            "rev_yoy": _pick(r, ["YSTZ", "TOTAL_OPERATE_INCOME_YOY"]),
            "np_yoy": _pick(r, ["SJLTZ", "PARENT_NETPROFIT_YOY"]),
        })
    return pd.DataFrame(rows, columns=[
        "date", "eps", "bps", "roe", "gross_margin",
        "net_margin", "rev_yoy", "np_yoy",
    ])


def _to_em_symbol(symbol: str) -> str:
    s = str(symbol).strip().lower()
    if s.startswith(("sh", "sz")):
        return s.upper()
    if s.startswith("bj"):
        return "BJ" + s[2:]
    if not s.isdigit() or len(s) != 6:
        return s.upper()
    if s.startswith(("60", "68", "90", "11", "13")):
        return "SH" + s
    if s.startswith(("00", "30", "20")):
        return "SZ" + s
    return "BJ" + s


def _pick(row: pd.Series, keys: list[str]) -> float | None:
    for k in keys:
        if k in row.index and pd.notna(row[k]) and row[k] not in ("", "--"):
            try:
                return float(row[k])
            except (ValueError, TypeError):
                continue
    return None


def _calc_margin(row: pd.Series) -> float | None:
    """销售净利率 = 净利润 / 营业总收入 × 100。"""
    rev = _pick(row, ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME"])
    np_ = _pick(row, ["PARENT_NETPROFIT", "NETPROFIT"])
    if rev and np_ and rev > 0:
        return round(np_ / rev * 100, 2)
    return None

"""当前行情。数据源：akshare stock_zh_a_hist_tx（日 K 最后一行作行情代理）。

由于沙箱环境东方财富 push2 接口被屏蔽，无 akshare 实时 tick 接口可用。
本模块通过拉取日 K 线，**最后一行作为当日行情代理**；字段含义与原设计一致，
无来源的字段（PE / 换手率 / 名称）标 None。

用户本地若东方财富可达，可加 ``if em_available: stock_zh_a_spot_em`` 分支。
"""
from __future__ import annotations

import logging
from typing import Callable

import pandas as pd

from . import history
from .retry import call_with_retry

logger = logging.getLogger(__name__)


def _ak():
    import akshare as ak
    return ak


def _to_tx_symbol(symbol: str) -> str:
    s = str(symbol).strip().lower()
    if s.startswith(("sh", "sz", "bj")):
        return s
    if not s.isdigit() or len(s) != 6:
        raise ValueError(f"非法代码：{symbol}")
    if s.startswith(("60", "68", "90", "11", "13")):
        return f"sh{s}"
    if s.startswith(("00", "30", "20")):
        return f"sz{s}"
    return f"bj{s}"


def fetch_spot(symbol: str, *, sleep: Callable[[float], None] | None = None) -> pd.Series:
    """拉取单只股票"当日行情"（日 K 最后一行代理实时 tick）。

    字段映射：
        name     ← None（无 tick 来源）
        price    ← 收盘价 close
        open     ← open
        pre_close← 前一日 close
        high     ← high
        low      ← low
        volume   ← 成交量(手)
        amount   ← 成交额(元)（K 线 amount 为万元 → × 1e4）
        turnover ← None
        pe_ttm   ← None
        pct_change ← (close - pre_close) / pre_close * 100
    """
    sleeper = sleep or (lambda s: None)
    df = call_with_retry(
        lambda: history.fetch_kline(symbol, years=1, adjust="qfq", sleep=sleeper),
        sleep=sleeper,
    )
    if df is None or df.empty or len(df) < 2:
        return pd.Series(dtype=object)
    return derive_spot_from_kline(df)


def derive_spot_from_kline(df: pd.DataFrame) -> pd.Series:
    """从已抓取的 K 线 DataFrame 派生当日行情（避免重复请求）。"""
    if df is None or df.empty or len(df) < 2:
        return pd.Series(dtype=object)
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
    except IndexError:
        return pd.Series(dtype=object)
    close = float(last["close"])
    pre_close = float(prev["close"])
    pct_change = (close / pre_close - 1.0) * 100.0 if pre_close else None
    return pd.Series({
        "name": None,
        "price": close,
        "open": float(last["open"]),
        "pre_close": pre_close,
        "high": float(last["high"]),
        "low": float(last["low"]),
        "volume": float(last.get("volume", 0) or 0),
        "amount": float(last.get("amount", 0) or 0) * 1e4,
        "turnover": None,
        "pe_ttm": None,
        "pct_change": pct_change,
    })


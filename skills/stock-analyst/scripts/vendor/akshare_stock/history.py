"""历史 K 线 + 历史统计。数据源：akshare stock_zh_a_hist_tx（腾讯源）。"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Callable

import pandas as pd

from .retry import call_with_retry

logger = logging.getLogger(__name__)


def _ak():
    import akshare as ak
    return ak


# 腾讯源 stock_zh_a_hist_tx 的 adjust 参数合法值
_VALID_ADJUST = ("", "qfq", "hfq")


def fetch_kline(
    symbol: str,
    *,
    years: int = 3,
    adjust: str = "",
    sleep: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """拉取日 K 线（默认不复权 + 东方财富源；含成交量列）。

    优先使用东方财富源 ``stock_zh_a_hist``（含 volume/amount/turnover），
    失败时回退到腾讯源 ``stock_zh_a_hist_tx``（无 volume，仅 amount）。

    adjust 取值：
        ""   不复权（默认；与券商 APP/同花顺 K 线界面默认一致；计算 MACD 等
             技术指标时与券商数字一致）
        "qfq" 前复权（适合长期趋势分析；价格基数随除权除息下调）
        "hfq" 后复权（适合回测历史收益）
    """
    if adjust not in _VALID_ADJUST:
        raise ValueError(
            f"adjust 非法：{adjust!r}，应为 {''.join(repr(a) for a in _VALID_ADJUST)}"
        )
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=years * 365)).strftime("%Y%m%d")
    sleeper = sleep or (lambda s: None)

    ak = _ak()
    # 优先：东方财富源（含 volume/amount，OBV/量比/MFI 可用）
    df = None
    try:
        df = call_with_retry(
            lambda: ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start, end_date=end, adjust=adjust or "",
            ),
            sleep=sleeper,
        )
    except ConnectionError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("EM 源失败，回退到腾讯源: %s", exc)

    # 回退：腾讯源（无 volume 但有 amount；OBV/量比/MFI 用 amount 仍能计算）
    if df is None or df.empty:
        if str(symbol).startswith(("sh", "sz", "bj")):
            tx_symbol = symbol
        else:
            if str(symbol).startswith(("60", "68", "90", "11", "13")):
                tx_symbol = f"sh{symbol}"
            elif str(symbol).startswith(("00", "30", "20")):
                tx_symbol = f"sz{symbol}"
            else:
                tx_symbol = f"bj{symbol}"
        df = call_with_retry(
            lambda: ak.stock_zh_a_hist_tx(symbol=tx_symbol, adjust=adjust,
                                           start_date=start, end_date=end),
            sleep=sleeper,
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "date", "open", "high", "low", "close",
                "volume", "amount", "amplitude", "pct_change", "turnover",
            ])
        # 腾讯源字段
        rename = {
            "date": "date", "open": "open", "high": "high", "low": "low",
            "close": "close", "amount": "amount",
            "change_percent": "pct_change", "turnover_rate": "turnover",
        }
        df = df.rename(columns=rename)
    else:
        # 东方财富源字段
        rename = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount",
            "振幅": "amplitude", "涨跌幅": "pct_change", "换手率": "turnover",
        }
        df = df.rename(columns=rename)

    keep = [c for c in (
        "date", "open", "high", "low", "close",
        "volume", "amount", "amplitude", "pct_change", "turnover",
    ) if c in df.columns]
    df = df[keep].copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def _period_return(df: pd.DataFrame, days: int) -> float | None:
    if len(df) < 2 or days <= 0:
        return None
    sub = df.tail(days + 1)
    if len(sub) < 2:
        return None
    first = sub["close"].iloc[0]
    last = sub["close"].iloc[-1]
    if first == 0 or pd.isna(first):
        return None
    return float((last / first - 1.0) * 100.0)


def summary_stats(df: pd.DataFrame) -> dict:
    empty = {
        "annual_volatility": None,
        "return_1m": None,
        "return_3m": None,
        "return_12m": None,
        "high_52w": None,
        "low_52w": None,
    }
    if df is None or df.empty or "close" not in df.columns:
        return empty

    close = df["close"].astype(float)
    if close.isna().all():
        return empty

    ratio = (close / close.shift(1)).dropna()
    ratio = ratio[ratio > 0]
    if len(ratio) > 1:
        log_ret = ratio.map(math.log)
        vol = float(log_ret.std(ddof=1) * (252 ** 0.5) * 100)
    else:
        vol = None

    ret_1m = _period_return(df, 21)
    ret_3m = _period_return(df, 63)
    ret_12m = _period_return(df, 252)

    last_year = df.tail(252)
    if last_year.empty:
        hi = lo = None
    else:
        hi = float(last_year["high"].max())
        lo = float(last_year["low"].min())

    return {
        "annual_volatility": vol,
        "return_1m": ret_1m,
        "return_3m": ret_3m,
        "return_12m": ret_12m,
        "high_52w": hi,
        "low_52w": lo,
    }

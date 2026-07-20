"""rich 终端渲染。"""
from __future__ import annotations

import sys
from typing import Iterable, Sequence

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# 显式锁定 stdout 与 ``force_terminal=True``,避免在以下场景里 Rich 探测失败
# 而完全不渲染:
#   1. IDE 的"运行"面板、CI 捕获、管道重定向等非 TTY 环境;
#   2. ``akshare_stock.silence.silence()`` 在抓取窗口内曾临时替换过
#      ``sys.stdout``(虽然已经还原,但 Rich 在某些版本下会缓存探测结果)。
# ``soft_wrap=False`` 让面板里的中文不被自动折行成两段,保持可读性。
console = Console(file=sys.stdout, force_terminal=True, soft_wrap=False)


# ---- 小工具 -------------------------------------------------------------------

def _fmt_pct(v: float | None, digits: int = 2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.{digits}f}%"


def _fmt_num(v: float | None, digits: int = 2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{digits}f}"


def _fmt_signed(v: float | None, digits: int = 2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:+.{digits}f}"


def warn(message: str) -> None:
    console.print(f"[bold red]✗[/] {message}")


def info(message: str) -> None:
    console.print(f"[bold cyan]ℹ[/] {message}")


def header(title: str) -> None:
    console.print(Panel.fit(f"[bold cyan]{title}[/]", border_style="cyan"))


# ---- 面板渲染 -----------------------------------------------------------------

def panel_basic(symbol: str, info: dict) -> None:
    if not info:
        warn("未找到基本信息")
        return
    name = info.get("name", symbol)
    rows: list[tuple[str, str]] = [
        ("代码", symbol),
        ("名称", str(name)),
        ("行业", str(info.get("industry", "—"))),
        ("上市日期", str(info.get("list_date", "—"))),
        ("总股本(亿股)", _fmt_num(info.get("total_share"))),
        ("流通股本(亿股)", _fmt_num(info.get("float_share"))),
        ("每股净资产", _fmt_num(info.get("nav_per_share"))),
    ]
    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    for k, v in rows:
        t.add_row(k, v)
    console.print(Panel(t, title="[bold]基本信息[/]", border_style="green"))


def panel_quote(row: pd.Series) -> None:
    if row is None or row.empty:
        warn("未找到当前行情")
        return
    rows: list[tuple[str, str]] = [
        ("名称", str(row.get("name", "—"))),
        ("现价", _fmt_num(row.get("price"))),
        ("今开", _fmt_num(row.get("open"))),
        ("昨收", _fmt_num(row.get("pre_close"))),
        ("最高", _fmt_num(row.get("high"))),
        ("最低", _fmt_num(row.get("low"))),
        ("成交量(手)", _fmt_num(row.get("volume"), 0)),
        ("成交额(元)", _fmt_num(row.get("amount"), 0)),
        ("换手率(%)", _fmt_num(row.get("turnover"))),
        ("市盈率(动)", _fmt_num(row.get("pe_ttm"))),
        ("涨跌幅(%)", _fmt_pct(row.get("pct_change"))),
    ]
    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    for k, v in rows:
        t.add_row(k, v)
    console.print(Panel(t, title="[bold]当前行情[/]", border_style="green"))


def panel_history_stats(stats: dict) -> None:
    rows: list[tuple[str, str]] = [
        ("年化波动率(%)", _fmt_num(stats.get("annual_volatility"))),
        ("近 1 月涨跌幅(%)", _fmt_pct(stats.get("return_1m"))),
        ("近 3 月涨跌幅(%)", _fmt_pct(stats.get("return_3m"))),
        ("近 12 月涨跌幅(%)", _fmt_pct(stats.get("return_12m"))),
        ("52 周最高", _fmt_num(stats.get("high_52w"))),
        ("52 周最低", _fmt_num(stats.get("low_52w"))),
    ]
    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    for k, v in rows:
        t.add_row(k, v)
    console.print(Panel(t, title="[bold]历史统计（近 3 年日线）[/]", border_style="green"))


def panel_signals(signals: Sequence[str]) -> None:
    text = "\n".join(f"• {s}" for s in signals) if signals else "无信号"
    console.print(Panel(text, title="[bold]技术信号摘要[/]", border_style="magenta"))


def table_kline_tail(df: pd.DataFrame, *, n: int = 20) -> None:
    if df is None or df.empty:
        warn("K 线数据为空")
        return
    sub = df.tail(n).copy()
    sub["date"] = sub["date"].dt.strftime("%Y-%m-%d")
    cols = ["date", "open", "high", "low", "close", "volume", "MA5", "MA20", "MACD_HIST"]
    cols = [c for c in cols if c in sub.columns]
    t = Table(title=f"K 线尾部（最近 {len(sub)} 个交易日）", show_lines=False)
    for c in cols:
        t.add_column(c, justify="right" if c != "date" else "left")
    for _, row in sub.iterrows():
        values = []
        for c in cols:
            v = row[c]
            if c == "date":
                values.append(str(v))
            elif c == "volume":
                values.append(_fmt_num(v, 0))
            elif c.startswith("MACD"):
                values.append(_fmt_signed(v))
            else:
                values.append(_fmt_num(v))
        t.add_row(*values)
    console.print(t)


def table_financials(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        warn("财务数据为空")
        return
    label = {"date": "报告期", "eps": "每股收益", "bps": "每股净资产",
             "roe": "ROE(%)", "gross_margin": "毛利率(%)", "net_margin": "净利率(%)",
             "rev_yoy": "营收同比(%)", "np_yoy": "净利同比(%)"}
    pct_cols = {"roe", "gross_margin", "net_margin", "rev_yoy", "np_yoy"}
    t = Table(title="主要财务指标（最近季度）", show_lines=False)
    for c in df.columns:
        t.add_column(label.get(c, c), justify="right" if c != "date" else "left")
    for _, row in df.iterrows():
        values = []
        for c in df.columns:
            v = row[c]
            if c == "date":
                values.append(str(v))
            elif c in pct_cols:
                values.append(_fmt_pct(v))
            else:
                values.append(_fmt_num(v))
        t.add_row(*values)
    console.print(t)


def table_sector(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        warn("板块数据为空")
        return
    t = Table(title="所属板块", show_lines=False)
    for c in ("type", "name", "code"):
        t.add_column({"type": "类型", "name": "名称", "code": "代码"}[c])
    for _, row in df.iterrows():
        t.add_row(str(row.get("type", "")), str(row.get("name", "")), str(row.get("code", "")))
    console.print(t)

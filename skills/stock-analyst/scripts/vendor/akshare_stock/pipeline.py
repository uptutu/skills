"""端到端编排:并行抓取 + 7 面板渲染。

性能:基本信息(4 并发)+ 历史 K 线 + 财务(3 个独立 akshare 调用)全部并行,
总耗时 ≈ max(profile, kline, fin),而非累加。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import pandas as pd

from . import fundamentals, history, indicators, printer, profile, quote
from .json_output import build_payload, emit_json


def _safe(call, label: str):
    """调用单个数据接口;失败仅打印警告并返回 None,不中断整体。"""
    try:
        return call()
    except Exception as exc:  # noqa: BLE001
        printer.warn(f"{label} 拉取失败:{exc}")
        return None


def run(
    symbol: str,
    *,
    topk: int = 10,
    include_sector: bool = True,
    adjust: str = "",
    macd_params: tuple[int, int, int] = (12, 26, 9),
    output_format: Literal["text", "json"] = "text",
) -> int:
    """主流程;返回 0 成功 / 2 代码不存在 / 3 网络问题。

    Parameters
    ----------
    output_format:
        ``"text"``(默认)走原有 7 个 Rich 面板;
        ``"json"`` 跳过所有 ``printer.*`` 渲染,把 7 个数据结构 + warnings
        序列化为单份 JSON 文档写到 stdout。
    """
    # 收集 fetch 阶段的诊断文本(JSON 模式写到顶层 warnings,text 模式照旧
    # 走 printer.warn)。用列表而不是 set 是为了保留失败先后顺序。
    warnings: list[str] = []
    exit_code = 0

    if output_format == "text":
        printer.header(f"A 股个股综合信息  ·  {symbol}")

    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_basic = ex.submit(lambda: profile.fetch_basic(symbol))
        fut_kline = ex.submit(lambda: history.fetch_kline(symbol, years=3, adjust=adjust))
        fut_fin = ex.submit(lambda: fundamentals.fetch_main_indicators(symbol, limit=8))

        try:
            basic = fut_basic.result()
        except ConnectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = f"基本信息 拉取失败:{exc}"
            if output_format == "text":
                printer.warn(msg)
            warnings.append(msg)
            basic = None
        if not basic or not basic.get("name"):
            msg = f"未找到代码 {symbol},请确认是否为 A 股 6 位代码"
            if output_format == "text":
                printer.warn(msg)
            warnings.append(msg)
            if output_format == "json":
                # JSON 模式下仍输出 payload,basic=null 反映真实状态
                payload = build_payload(
                    symbol=symbol, basic=None, spot=None, stats=None,
                    df_ind=None, signals=[], fin=None, sec=None, warnings=warnings,
                )
                print(emit_json(payload))
            return 2
        if output_format == "text":
            printer.panel_basic(symbol, basic)

        df = None
        try:
            df = fut_kline.result()
        except Exception as exc:  # noqa: BLE001
            msg = f"历史 K 线 拉取失败:{exc}"
            if output_format == "text":
                printer.warn(msg)
            warnings.append(msg)

        fin = None
        try:
            fin = fut_fin.result()
        except Exception as exc:  # noqa: BLE001
            msg = f"财务指标 拉取失败:{exc}"
            if output_format == "text":
                printer.warn(msg)
            warnings.append(msg)

    # 当前行情
    if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 2:
        spot = quote.derive_spot_from_kline(df)
    else:
        spot = _safe(lambda: quote.fetch_spot(symbol), "当前行情")
    if isinstance(spot, pd.Series) and not spot.empty:
        if output_format == "text":
            printer.panel_quote(spot)
    else:
        msg = "当前行情为空"
        if output_format == "text":
            printer.warn(msg)
        warnings.append(msg)

    # K 线 + 统计 + 指标
    df_ind: pd.DataFrame | None = None
    signals: list[str] = []
    stats: dict | None = None
    if isinstance(df, pd.DataFrame) and not df.empty:
        stats = history.summary_stats(df)
        df_ind = indicators.add_all(df, macd_params=macd_params)
        signals = indicators.latest_signals(df_ind)
        if output_format == "text":
            printer.panel_history_stats(stats)
            printer.panel_signals(signals)
            printer.table_kline_tail(df_ind, n=20)
    else:
        msg = "历史 K 线为空,跳过统计与技术指标"
        if output_format == "text":
            printer.warn(msg)
        warnings.append(msg)

    # 财务
    if isinstance(fin, pd.DataFrame) and not fin.empty:
        if output_format == "text":
            printer.table_financials(fin)
    else:
        msg = "财务数据为空"
        if output_format == "text":
            printer.warn(msg)
        warnings.append(msg)

    # 板块
    sec: pd.DataFrame | None = None
    if include_sector:
        sec = _safe(lambda: profile.fetch_sector(symbol, topk=topk, _basic=basic), "所属板块")
        if isinstance(sec, pd.DataFrame) and not sec.empty:
            if output_format == "text":
                printer.table_sector(sec)
        else:
            msg = "板块数据为空"
            if output_format == "text":
                printer.warn(msg)
            warnings.append(msg)

    # JSON 模式收尾:组装并打印单份 JSON 文档
    if output_format == "json":
        payload = build_payload(
            symbol=symbol,
            basic=basic,
            spot=spot if isinstance(spot, pd.Series) and not spot.empty else None,
            stats=stats,
            df_ind=df_ind,
            signals=signals,
            fin=fin if isinstance(fin, pd.DataFrame) and not fin.empty else None,
            sec=sec,
            warnings=warnings,
        )
        print(emit_json(payload))

    return exit_code
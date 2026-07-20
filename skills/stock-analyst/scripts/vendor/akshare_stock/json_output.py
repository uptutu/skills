"""JSON 序列化输出模块。

把 ``pipeline.run`` 在抓取阶段收集到的 7 个数据结构(basic / df / fin /
spot / stats / df_ind / signals / sec)+ ``warnings`` 列表序列化为单份
JSON 文档,供 CLI 的 ``--format json`` 选项或第三方脚本直接消费。

设计要点
--------

1. **不修改 ``pipeline.run`` 的现有语义**:仅新增 ``output_format`` kwarg,
   text 模式行为完全不变,JSON 模式跳过所有 Rich 渲染但保留同样的
   抓取顺序与失败处理。

2. **类型归一**:``pd.Timestamp`` → ISO 字符串;``np.integer/floating/bool_``
   → Python 原生类型;``NaN/NaT/inf`` → ``None``。``json.dumps`` 不能
   序列化这些 numpy/pandas 原生类型,因此走 ``pd.DataFrame.to_json``
   路径(自动处理 numpy)+ 顶层手动 ``_jsonify`` 两步走。

3. **K线 49 列全量**:面向机器消费 / 回测,与 ``indicators.add_all`` 的
   添加顺序一致(基础 K线 → 趋势 → 动量 → 成交量 → 形态)。``table_kline_tail``
   只展示 9 列,JSON 全量覆盖更全。

4. **部分失败语义**:任何 fetch 失败仍由 ``_safe`` 兜底,但 ``printer.warn``
   的中文文本同时被回收进 ``warnings`` 列表,JSON 消费者能看到诊断信息
   而无须 parse stderr。
"""
from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd


# K线 + 指标全列(10 + 39 = 49 列)。顺序与 ``indicators.add_all`` 的
# 添加顺序一致,便于机器消费端按时间序列读。
KLINE_JSON_COLUMNS: tuple[str, ...] = (
    # 基础 10 列(history.fetch_kline 输出顺序)
    "date", "open", "high", "low", "close",
    "volume", "amount", "amplitude", "pct_change", "turnover",
    # 趋势 9 列(indicators_trend.add_ma / add_macd / add_dma)
    "MA5", "MA10", "MA20", "MA60",
    "MACD_DIF", "MACD_DEA", "MACD_HIST",
    "DMA", "AMA",
    # 动量 6 列(indicators_momentum.add_rsi / add_kdj / add_cci / add_bias)
    "RSI14", "KDJ_K", "KDJ_D", "KDJ_J", "CCI14", "BIAS6",
    # 成交量 4 列(indicators_volume.add_obv / add_volume_ratio / add_mfi /
    # add_volume_price_signal)
    "OBV", "VR5", "MFI14", "VP_SIGNAL",
    # 形态 19 列(indicators_pattern.add_boll / add_pivot / add_fibonacci /
    # add_gaps / add_breakout)
    "BOLL_MID", "BOLL_UPPER", "BOLL_LOWER",
    "PIVOT_P", "PIVOT_R1", "PIVOT_S1", "PIVOT_R2", "PIVOT_S2",
    "PIVOT_R3", "PIVOT_S3",
    "FIB_0", "FIB_236", "FIB_382", "FIB_500", "FIB_618", "FIB_786", "FIB_100",
    "GAP_TYPE", "GAP_SIZE", "BREAKOUT_UP", "BREAKOUT_DOWN",
)


def _jsonify(value: Any) -> Any:
    """把任意标量值转成 JSON 原生类型:NaN/NaT/inf → ``None``,numpy → Python 原生。"""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def _jsonify_dict(d: dict | None) -> dict[str, Any] | None:
    """对 dict 应用 :func:`_jsonify` 到每个 value;空 dict 返回 ``None``。"""
    if not d:
        return None
    return {k: _jsonify(v) for k, v in d.items()}


def _kline_rows(df_ind: pd.DataFrame | None) -> list[dict[str, Any]] | None:
    """把 ``df_ind``(已含全部指标列)转成 ``list[dict]``,日期 ISO 字符串。

    返回 ``None`` 当输入为 ``None``;空 DataFrame 返回 ``[]``,与"拉取到
    但无数据"语义区分(JSON 消费者据此区分"接口挂了"与"接口正常但当天没数据")。
    """
    if df_ind is None:
        return None
    if df_ind.empty:
        return []
    cols = [c for c in KLINE_JSON_COLUMNS if c in df_ind.columns]
    sub = df_ind[cols].copy()
    if "date" in sub.columns:
        sub["date"] = sub["date"].dt.strftime("%Y-%m-%d")
    # ``pd.DataFrame.to_json`` 会把 numpy 类型转成 JSON 原生类型,
    # NaN 会变成 ``NaN``(非合法 JSON),需用 ``json.loads`` 二次解析
    # 让其变为 Python ``float('nan')``,再走 ``_jsonify`` 过滤掉。
    raw = sub.to_json(orient="records", force_ascii=False)
    rows = json.loads(raw)
    return [{k: _jsonify(v) for k, v in row.items()} for row in rows]


def _dataframe_rows(df: pd.DataFrame | None) -> list[dict[str, Any]] | None:
    """通用 DataFrame → ``list[dict]``。``None`` 输入返回 ``None``。"""
    if df is None:
        return None
    if df.empty:
        return []
    sub = df.copy()
    if "date" in sub.columns and not pd.api.types.is_string_dtype(sub["date"]):
        sub["date"] = pd.to_datetime(sub["date"]).dt.strftime("%Y-%m-%d")
    raw = sub.to_json(orient="records", force_ascii=False)
    rows = json.loads(raw)
    return [{k: _jsonify(v) for k, v in row.items()} for row in rows]


def _series_dict(s: pd.Series | None) -> dict[str, Any] | None:
    """``pd.Series`` → ``dict``;空 Series 或 ``None`` 输入返回 ``None``。"""
    if s is None or len(s) == 0:
        return None
    return {k: _jsonify(v) for k, v in s.to_dict().items()}


def build_payload(
    *,
    symbol: str,
    basic: dict | None,
    spot: pd.Series | None,
    stats: dict | None,
    df_ind: pd.DataFrame | None,
    signals: list[str] | None,
    fin: pd.DataFrame | None,
    sec: pd.DataFrame | None,
    warnings: list[str],
) -> dict[str, Any]:
    """组装最终 JSON payload。

    字段约定(与 rich 7 面板 1:1 对应):

    - ``symbol``:股票代码
    - ``basic``:基本信息 dict(可为 ``None`` 当未找到)
    - ``quote``:当前行情(Series 转 dict,可为 ``None``)
    - ``history_stats``:历史统计(6 字段,可为 ``None``)
    - ``signals``:技术信号文本列表(永远 ``list``,可能为空)
    - ``kline``:K线 + 指标全列,可为 ``None``(fetch 失败)/ ``[]``(空)
    - ``financials``:财务指标,可能 ``None`` / ``[]``
    - ``sector``:所属板块,可能 ``None`` / ``[]``
    - ``warnings``:fetch 阶段诊断文本(原 ``printer.warn`` 内容)
    """
    return {
        "symbol": symbol,
        "basic": basic if basic else None,
        "quote": _series_dict(spot),
        "history_stats": _jsonify_dict(stats) if stats else None,
        "signals": list(signals) if signals else [],
        "kline": _kline_rows(df_ind),
        "financials": _dataframe_rows(fin),
        "sector": _dataframe_rows(sec),
        "warnings": list(warnings),
    }


def emit_json(payload: dict[str, Any]) -> str:
    """序列化为带缩进的 UTF-8 JSON 字符串(``ensure_ascii=False`` 保留中文)。

    自动把 ``NaN`` / ``inf`` 转 ``null`` —— ``json.dumps`` 默认允许 ``NaN``
    输出为字面量 ``NaN``(非合法 JSON),但 :class:`float` 直接传进来时
    不会经过 :func:`_jsonify`,需要 :class:`json.JSONEncoder` 的 ``default``
    钩子兜底。注意:本模块内部 :func:`build_payload` 已经把 NaN 通过
    :func:`_jsonify` 转 ``None``,本兜底仅防止外部调用方传入未归一化的
    payload。
    """

    class _NaNSafeEncoder(json.JSONEncoder):
        def iterencode(self, o, _one_shot=False):
            # 把 NaN/inf 替换成 None 再走标准路径
            import math as _m

            def _clean(v):
                if isinstance(v, float) and (_m.isnan(v) or _m.isinf(v)):
                    return None
                if isinstance(v, dict):
                    return {k: _clean(x) for k, x in v.items()}
                if isinstance(v, (list, tuple)):
                    return [_clean(x) for x in v]
                return v

            return super().iterencode(_clean(o), _one_shot)

    return json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=False,
        cls=_NaNSafeEncoder,
    )
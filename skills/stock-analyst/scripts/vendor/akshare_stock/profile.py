"""个股基本信息 + 所属板块。

全部使用 akshare 官方接口（严格符合计划"用 akshare"要求）：

- 主：stock_profile_cninfo —— 巨潮资讯公司档案（行业/上市日期/法人/办公地址等）
- 股本：stock_share_change_cninfo —— 巨潮股本结构（总股本/流通股本）
- 财务：stock_balance_sheet_by_report_em —— 资产负债表（归母权益 → 每股净资产）
- 主营补：stock_zyjs_ths —— 同花顺主营/产品类型

并行：上述 4 个独立源通过 ThreadPoolExecutor 并发抓取，
总耗时 ≈ 最慢单源（5~13s），不累加。
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pandas as pd

from .retry import call_with_retry

logger = logging.getLogger(__name__)


def _ak():
    import akshare as ak
    return ak


def fetch_basic(symbol: str, *, sleep: Callable[[float], None] | None = None) -> dict:
    """拉取个股基本信息。失败返回空 dict。"""
    sleeper = sleep or (lambda s: None)

    def _profile():
        return call_with_retry(lambda: _ak().stock_profile_cninfo(symbol=symbol), sleep=sleeper)

    def _shares():
        return call_with_retry(lambda: _ak().stock_share_change_cninfo(symbol=symbol), sleep=sleeper)

    def _balance():
        sec = _to_em_symbol(symbol)
        return call_with_retry(
            lambda: _ak().stock_balance_sheet_by_report_em(symbol=sec),
            sleep=sleeper,
        )

    def _zyjs():
        return call_with_retry(lambda: _ak().stock_zyjs_ths(symbol=symbol), sleep=sleeper)

    # 并行抓取
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            "profile": ex.submit(_profile),
            "shares": ex.submit(_shares),
            "balance": ex.submit(_balance),
            "zyjs": ex.submit(_zyjs),
        }
        results = {}
        for k, fut in futs.items():
            try:
                results[k] = fut.result()
            except ConnectionError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch_basic %s 失败: %s", k, exc)
                results[k] = None

    out: dict = {}

    # 1) 巨潮公司档案
    df = results.get("profile")
    if df is not None and not df.empty:
        row = df.iloc[0]
        for src, dst in {
            "公司名称": "name",
            "A股简称": "name_short",
            "所属行业": "industry",
            "上市日期": "list_date",
            "成立日期": "found_date",
            "注册资金": "registered_capital_wan",
            "法定代表人": "legal_rep",
            "法人代表": "legal_rep",
            "主营业务": "main_business",
            "办公地址": "office_address",
            "注册地址": "registered_address",
            "官方网站": "website",
            "所属市场": "market",
            "入选指数": "indices",
        }.items():
            if src in row.index and pd.notna(row[src]) and str(row[src]).strip():
                out[dst] = row[src]

    # 2) 巨潮股本结构
    df = results.get("shares")
    if df is not None and not df.empty and "总股本" in df.columns:
        df = df.sort_values("变动日期", ascending=False)
        latest = df.iloc[0]
        ts = latest.get("总股本")
        fs = latest.get("已流通股份")
        if pd.notna(ts):
            out["total_share"] = round(float(ts) / 1e4, 2)
        if pd.notna(fs):
            out["float_share"] = round(float(fs) / 1e4, 2)
        out["share_change_date"] = str(latest.get("变动日期", ""))[:10]

    # 3) 每股净资产：优先资产负债表（权威），沙箱慢时回退到百度 PB × 总市值/总股本
    if out.get("total_share") and out["total_share"] > 0:
        df = results.get("balance")
        if df is not None and not df.empty and "TOTAL_PARENT_EQUITY" in df.columns:
            df = df.sort_values("REPORT_DATE", ascending=False)
            eq = df.iloc[0].get("TOTAL_PARENT_EQUITY")
            if pd.notna(eq) and eq:
                out["nav_per_share"] = round(float(eq) / (out["total_share"] * 1e8), 2)
                out["nav_source"] = "balance_sheet"
        # 回退：百度估值 PB
        if "nav_per_share" not in out:
            try:
                df_pb = call_with_retry(
                    lambda: _ak().stock_zh_valuation_baidu(symbol=symbol, indicator="市净率"),
                    sleep=sleeper,
                )
                df_mc = call_with_retry(
                    lambda: _ak().stock_zh_valuation_baidu(symbol=symbol, indicator="总市值"),
                    sleep=sleeper,
                )
                if df_pb is not None and df_mc is not None and not df_pb.empty and not df_mc.empty:
                    pb = float(df_pb.iloc[-1, 1])
                    mc_yi = float(df_mc.iloc[-1, 1])  # 亿元
                    if pb > 0:
                        price = mc_yi / out["total_share"]
                        out["nav_per_share"] = round(price / pb, 2)
                        out["nav_source"] = "baidu_pb"
            except Exception as exc:  # noqa: BLE001
                logger.warning("nav via baidu 失败: %s", exc)

    # 4) 主营/产品（兜底）
    if not out.get("main_business"):
        df = results.get("zyjs")
        if df is not None and not df.empty:
            row = df.iloc[0]
            out.setdefault("main_business", str(row.get("主营业务", "") or "")[:80])
            out["product_type"] = str(row.get("产品类型", "") or "")[:80]

    if not out.get("name"):
        return {}

    out.setdefault("symbol", symbol)
    for k in ("industry", "list_date"):
        if not out.get(k):
            out[k] = "—"
    for k in ("total_share", "float_share", "nav_per_share"):
        if k not in out:
            out[k] = "—"
    return out


def fetch_sector(symbol: str, *, topk: int = 10, sleep: Callable[[float], None] | None = None,
                 _basic: dict | None = None) -> pd.DataFrame:
    """获取所属行业 + 主营业务 + 办公地址。

    _basic：调用方可传入已缓存的 basic 字典，避免重复抓取。
    """
    sleeper = sleep or (lambda s: None)
    rows: list[dict] = []

    basic = _basic if _basic is not None else fetch_basic(symbol, sleep=sleeper)
    if basic.get("industry") and basic["industry"] != "—":
        rows.append({"type": "所属行业", "name": basic["industry"], "code": ""})
    if basic.get("main_business"):
        rows.append({"type": "主营业务", "name": str(basic["main_business"])[:80], "code": ""})
    if basic.get("product_type"):
        rows.append({"type": "产品类型", "name": basic["product_type"], "code": ""})
    if basic.get("office_address"):
        rows.append({"type": "办公地址", "name": str(basic["office_address"])[:60], "code": ""})

    return pd.DataFrame(rows, columns=["type", "name", "code"]).head(topk).reset_index(drop=True)


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


#!/usr/bin/env python3
"""
stock_query.py - stock-analyst skill 的个股数据查询入口。

本脚本完全自包含:
- 抓取代码已 vendored 到 ``scripts/vendor/akshare_stock/``,无外部代码路径依赖;
- 通过 ``sys.path`` 注入 vendor 目录后直接 import 使用;
- 唯一外部依赖是 pandas / numpy / rich,见 ``scripts/requirements.txt``。

单次调用返回 7 面板(基本信息 / 当前行情 / 历史统计 / 技术信号 / K 线尾部 /
财务 / 板块),无 ``brief/medium/full`` 级别概念。

Usage
-----
    python3 scripts/stock_query.py --symbol 600519 --format text
    python3 scripts/stock_query.py --symbol SH600519 --format json
    python3 scripts/stock_query.py --symbol 600519.SH --format json
    python3 scripts/stock_query.py --symbol 浦发银行 --format text
    python3 scripts/stock_query.py --symbol 600519,000001 --format json
    python3 scripts/stock_query.py --symbol 600519 --adjust qfq --topk 5

首次使用
--------
    pip install -r skills/stock-analyst/scripts/requirements.txt
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# vendor 自包含:把 scripts/vendor/ 加进 sys.path
# --------------------------------------------------------------------------- #

_SCRIPTS_DIR = Path(__file__).resolve().parent
_VENDOR_DIR = _SCRIPTS_DIR / "vendor"

# 必须在 import akshare_stock 之前插入;若已存在则不重复插入
_VENDOR_PATH = str(_VENDOR_DIR)
if _VENDOR_PATH not in sys.path:
    sys.path.insert(0, _VENDOR_PATH)


# --------------------------------------------------------------------------- #
# 代码归一化
# --------------------------------------------------------------------------- #

_NAME_MAP_PATH = Path.home() / ".cache" / "stock-analyst" / "name_to_code.json"
_NAME_MAP_TTL_SECONDS = 24 * 3600


def normalize_symbol(raw: str) -> str:
    """把任意代码格式归一为 6 位数字。

    支持:
    - ``600000`` / ``000001``(纯数字)
    - ``SH600000`` / ``SZ000001``(剥前缀)
    - ``600000.SH`` / ``000001.SZ``(剥后缀)
    - ``浦发银行``(中文名 → 6 位代码,查本地缓存)
    """
    raw = raw.strip()

    if raw and all("一" <= c <= "鿿" for c in raw):
        code = _lookup_code_by_name(raw)
        if code is None:
            raise ValueError(
                f"无法识别中文名 {raw!r};请直接使用 6 位代码,或先联网更新名映射"
            )
        return code

    upper = raw.upper()
    m = re.match(r"^(SH|SZ)(\d{6})$", upper)
    if m:
        return m.group(2)
    m = re.match(r"^(\d{6})\.(SH|SZ)$", upper)
    if m:
        return m.group(1)
    m = re.match(r"^\d{6}$", upper)
    if m:
        return upper

    raise ValueError(
        f"无法识别代码格式 {raw!r};支持 6 位数字 / SH/SZ 前缀 / .SH/.SZ 后缀 / 中文名"
    )


# --------------------------------------------------------------------------- #
# 中文名映射(vendored akshare 拉全 A 股名表,本地缓存)
# --------------------------------------------------------------------------- #


def _fetch_name_map_via_akshare() -> dict[str, str] | None:
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError:
        return None
    try:
        df = ak.stock_info_a_code_name()
    except Exception:  # noqa: BLE001
        return None
    if df is None or df.empty:
        return None
    cols = {c.lower(): c for c in df.columns}
    code_col = cols.get("code") or cols.get("symbol")
    name_col = cols.get("name") or cols.get("code_name")
    if not code_col or not name_col:
        return None
    name_map: dict[str, str] = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col]).strip()
        if len(code) == 6 and code.isdigit() and name:
            name_map[name] = code
    return name_map


def _load_name_map() -> dict[str, str]:
    import time
    now = time.time()
    if _NAME_MAP_PATH.exists():
        try:
            mtime = _NAME_MAP_PATH.stat().st_mtime
            if now - mtime < _NAME_MAP_TTL_SECONDS:
                with _NAME_MAP_PATH.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    fresh = _fetch_name_map_via_akshare()
    if not fresh:
        if _NAME_MAP_PATH.exists():
            try:
                with _NAME_MAP_PATH.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}
    _NAME_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _NAME_MAP_PATH.open("w", encoding="utf-8") as f:
            json.dump(fresh, f, ensure_ascii=False)
    except OSError:
        pass
    return fresh


def _lookup_code_by_name(name: str) -> str | None:
    return _load_name_map().get(name)


# --------------------------------------------------------------------------- #
# 调用 akshare_stock(vendored,纯 import)
# --------------------------------------------------------------------------- #


def call_akshare(
    code: str,
    *,
    format_: str,
    topk: int,
    include_sector: bool,
    adjust: str,
    macd: str,
) -> tuple[int, str]:
    """调用 vendored akshare_stock.pipeline.run。

    返回 (returncode, captured_stdout)。所有 akshare 的 print / Rich 输出都
    已被 vendored 的 silence.py 抑制,pipeline.run 自身的 stdout 输出
    (json 模式的 ``print(emit_json(payload))`` / text 模式的 Rich 面板)通过
    ``redirect_stdout`` 捕获到字符串后原样回放。
    """
    try:
        from akshare_stock import pipeline  # noqa: PLC0415,import-outside-toplevel
    except ImportError as exc:
        msg = (
            f"无法 import akshare_stock: {exc}\n"
            "请确认 scripts/vendor/akshare_stock/ 目录存在;若是首次使用,可能需要\n"
            "  pip install -r scripts/requirements.txt"
        )
        return (127, msg)

    try:
        macd_params = tuple(int(x) for x in macd.split(","))
        if len(macd_params) != 3 or any(p <= 0 for p in macd_params):
            raise ValueError
    except (ValueError, AttributeError):
        return (2, f"--macd 参数非法: {macd!r},应为 'fast,slow,signal' 三正整数")

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = pipeline.run(
                code,
                topk=topk,
                include_sector=include_sector,
                adjust=adjust,
                macd_params=macd_params,  # type: ignore[arg-type]
                output_format=format_,  # type: ignore[arg-type]
            )
    except ConnectionError as exc:
        return (3, f"网络中断: {exc}(请检查网络后重试)")
    except KeyboardInterrupt:
        return (130, "用户中断")
    except Exception as exc:  # noqa: BLE001
        return (1, f"akshare 调用异常: {exc}")

    return (rc, buf.getvalue())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stock_query",
        description="通过 vendored akshare 拉取 A 股个股综合信息。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--symbol", "-s", required=True,
        help="股票代码或中文名(逗号分隔多只)。支持 SH600519 / 600519.SH / 600519 / 浦发银行。",
    )
    p.add_argument(
        "--format", "-f", default="text", choices=["text", "json"],
        help="输出格式:text=Rich 面板(默认) / json=结构化 JSON",
    )
    p.add_argument(
        "--topk", type=int, default=10,
        help="概念板块 TopK,默认 10",
    )
    p.add_argument(
        "--no-sector", action="store_true",
        help="跳过概念板块(更快速)",
    )
    p.add_argument(
        "--adjust", default="", choices=["", "qfq", "hfq"],
        help="K 线复权:默认 '' 不复权 / qfq 前复权 / hfq 后复权",
    )
    p.add_argument(
        "--macd", default="12,26,9",
        help="MACD 参数 (fast,slow,signal),默认 12,26,9",
    )
    return p


def _run_one(
    raw_symbol: str,
    *,
    format_: str,
    topk: int,
    include_sector: bool,
    adjust: str,
    macd: str,
) -> int:
    try:
        code = normalize_symbol(raw_symbol)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    rc, out = call_akshare(
        code, format_=format_, topk=topk, include_sector=include_sector,
        adjust=adjust, macd=macd,
    )
    if out:
        if format_ == "json" and not out.endswith("\n"):
            sys.stdout.write(out + "\n")
        else:
            sys.stdout.write(out)
    return rc


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
    if not symbols:
        print("❌ --symbol 不能为空", file=sys.stderr)
        return 2

    rc = 0
    for i, raw in enumerate(symbols):
        if i > 0:
            sys.stdout.write("\n")
        single_rc = _run_one(
            raw, format_=args.format, topk=args.topk,
            include_sector=not args.no_sector, adjust=args.adjust,
            macd=args.macd,
        )
        rc = rc or single_rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
market_env.py - Fetch real-time Chinese A-share market environment data.

Queries key market indices via the CN A-Stock MCP server using the `brief` tool,
and aggregates them into a structured market overview report.

Usage:
    python3 scripts/market_env.py                          # default: all indices overview
    python3 scripts/market_env.py --format json             # JSON output
    python3 scripts/market_env.py --server http://your-server/mcp

Data sources:
    - 主要指数：上证/深成/创业板/沪深300/科创50/中证500（通过 brief 工具查询）
    - 成交额/量能：包含在 brief 返回数据中

Note:
    The MCP server provides data via `brief`/`medium`/`full` tools only.
    Fund flow, sector performance, and global markets require additional
    data sources beyond the current MCP server capabilities.
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error

DEFAULT_SERVER = "http://82.156.17.205/cnstock/mcp"
DEFAULT_TIMEOUT = 15

INDICES = {
    "上证指数": "SH000001",
    "深证成指": "SZ399001",
    "创业板指": "SZ399006",
    "沪深300": "SH000300",
    "科创50": "SH000688",
    "中证500": "SH000905",
}


def mcp_call(server, method, params, timeout=DEFAULT_TIMEOUT):
    """Make an MCP JSON-RPC call via streamable-http protocol."""
    import hashlib
    request_id = int(hashlib.md5(f"{method}{json.dumps(params, sort_keys=True)}".encode()).hexdigest()[:8], 16)
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        server, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        return {"error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}
    try:
        return _parse_sse(raw)
    except Exception as e:
        return {"error": f"Parse error: {str(e)}", "raw": raw[:500]}


def _parse_sse(raw_text):
    """Parse SSE response to extract JSON data."""
    for line in raw_text.split('\n'):
        if line.startswith('data:'):
            data_str = line[len('data:'):].strip()
            if data_str:
                return json.loads(data_str)
    return json.loads(raw_text)


def _extract_text(result):
    """Extract text content from MCP response."""
    if "error" in result:
        return f"[Error: {result['error']}]"
    try:
        result_obj = result.get("result", {})
        if "structuredContent" in result_obj:
            return result_obj["structuredContent"].get("result", "")
        elif "content" in result_obj:
            return result_obj["content"][0].get("text", "")
        return json.dumps(result_obj)
    except Exception:
        return json.dumps(result)


def fetch_index(server, code, timeout):
    """Fetch brief data for a single index."""
    mcp_call(server, "notifications/initialized", None, timeout)
    result = mcp_call(server, "tools/call", {
        "name": "brief",
        "arguments": {"symbol": code},
    }, timeout)
    return _extract_text(result)


def _extract_field(raw_text, patterns):
    """Extract a field value from raw markdown text using multiple patterns."""
    if not raw_text or raw_text.startswith("[Error"):
        return "-"
    if isinstance(patterns, str):
        patterns = [patterns]
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return "-"


def parse_index_data(name, raw_text):
    """Parse index brief data into structured dict."""
    return {
        "name": name,
        "price": _extract_field(raw_text, [r"## 价格.*?当日:\s*([\d.]+)"]),
        "high": _extract_field(raw_text, [r"## 价格.*?最高:\s*([\d.]+)"]),
        "low": _extract_field(raw_text, [r"## 价格.*?最低:\s*([\d.]+)"]),
        "change_pct": _extract_field(raw_text, [r"## 涨跌幅.*?当日:\s*([-\d.]+%)"]),
        "amplitude": _extract_field(raw_text, [r"## 振幅.*?当日:\s*([\d.]+%)"]),
        "volume": _extract_field(raw_text, [r"## 成交量.*?当日:\s*([\d.]+)"]),
        "turnover": _extract_field(raw_text, [r"## 成交额.*?当日:\s*([\d.]+)"]),
        "ma5": _extract_field(raw_text, [r"5日均价:\s*([\d.]+)"]),
        "ma20": _extract_field(raw_text, [r"20日均价:\s*([\d.]+)"]),
        "ma60": _extract_field(raw_text, [r"60日均价:\s*([\d.]+)"]),
        "raw": raw_text,
    }


def format_markdown(indices):
    """Format market overview as markdown."""
    lines = ["# 🌐 市场环境数据\n"]

    lines.append("## 📈 主要指数行情\n")
    lines.append("| 指数 | 最新价 | 涨跌幅 | 振幅 | 成交额(亿) | 5日MA | 20日MA |")
    lines.append("|------|--------|--------|------|------------|-------|--------|")
    for idx in indices:
        lines.append(
            f"| {idx['name']} | {idx['price']} | {idx['change_pct']} "
            f"| {idx['amplitude']} | {idx['turnover']} | {idx['ma5']} | {idx['ma20']} |"
        )
    lines.append("")

    up = sum(1 for i in indices if i['change_pct'] != '-' and not i['change_pct'].startswith('-') and i['change_pct'] != '0.00%')
    down = len(indices) - up
    lines.append(f"**涨跌分布**: 🟢 上涨 {up} / 🔴 下跌 {down}\n")

    lines.append("## 📊 市场情绪\n")
    total_turnover = 0
    for idx in indices:
        if idx['turnover'] != '-':
            try:
                total_turnover += float(idx['turnover'].replace(',', ''))
            except ValueError:
                pass
    lines.append(f"- **主要指数总成交额**: {total_turnover:.2f} 亿")
    lines.append(f"- **市场活跃度**: {'🔥 放量' if up > down else '🧊 缩量' if up < down else '⚖️ 均衡'}")
    lines.append("")

    for idx in indices:
        lines.append(f"### {idx['name']} 详细数据\n")
        lines.append(f"<details><summary>点击查看</summary>\n\n```")
        if idx['raw'] and not idx['raw'].startswith("[Error"):
            lines.append(idx['raw'])
        else:
            lines.append(idx['raw'] or "无数据")
        lines.append("```\n</details>\n")

    lines.append("---")
    lines.append("> **数据说明**: 通过 MCP `brief` 工具查询指数代码获取。")
    lines.append("> 资金流向、板块行情、国际市场等数据需额外数据源支持，当前 MCP 服务器未提供专用工具。\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch real-time Chinese A-share market environment data",
    )
    parser.add_argument(
        "--format", "-f", default="markdown", choices=["markdown", "json"],
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--server", default=DEFAULT_SERVER,
        help=f"MCP server URL (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )

    args = parser.parse_args()

    indices = []
    for name, code in INDICES.items():
        raw = fetch_index(args.server, code, args.timeout)
        indices.append(parse_index_data(name, raw))

    if args.format == "json":
        output = []
        for idx in indices:
            d = {k: v for k, v in idx.items() if k != 'raw'}
            d['raw_data'] = idx['raw']
            output.append(d)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(indices))


if __name__ == "__main__":
    main()

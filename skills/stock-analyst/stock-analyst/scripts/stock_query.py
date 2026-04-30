#!/usr/bin/env python3
"""
stock_query.py - Query Chinese A-share stock data via MCP streamable-http protocol.

This script directly calls the CN A-Stock MCP server without requiring
an MCP source connection in the workspace. It implements the MCP
streamable-http protocol using only Python standard library modules.

Usage:
    python stock_query.py --symbol SH600000 --level brief
    python stock_query.py --symbol SH600000 --level full
    python stock_query.py --symbol 浦发银行 --level full
    python stock_query.py --symbol 600000 --level medium
    python stock_query.py --symbol SZ000001,SH600000 --level brief --format json

Options:
    --symbol  Stock symbol or name (comma-separated for multiple stocks)
    --level   Data level: brief (default), medium, or full
    --format  Output format: markdown (default) or json
    --server  MCP server URL (default: http://82.156.17.205/cnstock/mcp)
    --timeout Request timeout in seconds (default: 15)
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error

DEFAULT_SERVER = "http://82.156.17.205/cnstock/mcp"
DEFAULT_TIMEOUT = 15

# Symbol format normalization map
# Users may input: 600000, SH600000, 600000.SH, 浦发银行
# We need to convert to: SH600000 or SZ000001 format


def normalize_symbol(raw: str) -> str:
    """Normalize stock symbol to MCP format (SH600001 or SZ000001).

    Handles inputs like:
    - 600000 → SH600000
    - SH600000 → SH600000
    - 600000.SH → SH600000
    - SZ000001 → SZ000001
    - 000001 → SZ000001
    - 000001.SZ → SZ000001
    - Chinese names are passed through (server resolves them)
    """
    raw = raw.strip().upper()

    # If purely Chinese characters, pass through (server resolves names)
    if all('\u4e00' <= c <= '\u9fff' for c in raw):
        return raw

    # Handle 600000.SH or 000001.SZ format
    match = re.match(r'^(\d+)\.(SH|SZ)$', raw)
    if match:
        code, exchange = match.groups()
        return f"{exchange}{code}"

    # Handle SH600000 or SZ000001 (already correct)
    match = re.match(r'^(SH|SZ)(\d+)$', raw)
    if match:
        return raw

    # Pure numeric code - infer exchange
    # Shanghai: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx (科创板)
    # Shenzhen: 000xxx, 002xxx, 300xxx (创业板)
    match = re.match(r'^(\d{6})$', raw)
    if match:
        code = match.group(1)
        if code.startswith(('60', '68')):
            return f"SH{code}"
        elif code.startswith(('00', '30')):
            return f"SZ{code}"

    # Return as-is and let server try to resolve
    return raw


def parse_sse_response(raw_text: str) -> dict:
    """Parse SSE (Server-Sent Events) response to extract JSON data.

    The MCP streamable-http server returns SSE format:
        event: message
        data: {"jsonrpc":"2.0",...}
    """
    for line in raw_text.split('\n'):
        if line.startswith('data:'):
            data_str = line[len('data:'):].strip()
            if data_str:
                return json.loads(data_str)
    # Fallback: try parsing as raw JSON
    return json.loads(raw_text)


def mcp_call(server: str, method: str, params: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Make an MCP JSON-RPC call via streamable-http protocol.

    Each call is stateless - no session management required.
    """
    request_id = hash(f"{method}{json.dumps(params, sort_keys=True)}") % (10**8)

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params is not None:
        payload["params"] = params

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        server,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        return {"error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

    try:
        return parse_sse_response(raw)
    except (json.JSONDecodeError, Exception) as e:
        return {"error": f"Failed to parse response: {str(e)}", "raw": raw[:500]}


def get_stock_data(server: str, symbol: str, level: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Get stock data at the specified level (brief/medium/full).

    Returns dict with 'symbol', 'level', 'data', and optional 'error'.
    """
    normalized = normalize_symbol(symbol)

    # Send initialized notification (stateless, so optional but good practice)
    mcp_call(server, "notifications/initialized", None, timeout)

    # Call the appropriate tool
    result = mcp_call(server, "tools/call", {
        "name": level,
        "arguments": {"symbol": normalized},
    }, timeout)

    if "error" in result:
        return {
            "symbol": normalized,
            "level": level,
            "error": result["error"],
            "data": None,
        }

    # Extract result from JSON-RPC response
    if "error" in result:
        return {
            "symbol": normalized,
            "level": level,
            "error": f"Server error: {result['error']}",
            "data": None,
        }

    data = None
    try:
        result_obj = result.get("result", {})
        # Try structuredContent first (cleaner), then content[0].text
        if "structuredContent" in result_obj:
            data = result_obj["structuredContent"].get("result", "")
        elif "content" in result_obj:
            data = result_obj["content"][0].get("text", "")
        else:
            data = json.dumps(result_obj)
    except (KeyError, IndexError, TypeError):
        data = json.dumps(result, indent=2)

    return {
        "symbol": normalized,
        "level": level,
        "data": data,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query Chinese A-share stock data via MCP streamable-http",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --symbol SH600000 --level full
  %(prog)s --symbol 浦发银行 --level brief
  %(prog)s --symbol SZ000001,SH600000 --level medium --format json
  %(prog)s --symbol 600000 --level full --server http://your-server/mcp
        """,
    )
    parser.add_argument(
        "--symbol", "-s", required=True,
        help="Stock symbol or name (comma-separated for multiple stocks)",
    )
    parser.add_argument(
        "--level", "-l", default="brief", choices=["brief", "medium", "full"],
        help="Data detail level (default: brief)",
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

    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
    results = []

    for sym in symbols:
        result = get_stock_data(args.server, sym, args.level, args.timeout)
        results.append(result)

    # Output results
    if args.format == "json":
        output = {
            "symbols": args.symbol,
            "level": args.level,
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for r in results:
            if r["error"]:
                print(f"❌ Error for {r['symbol']} ({r['level']}): {r['error']}", file=sys.stderr)
                continue
            print(f"\n{'='*60}")
            print(f"📊 {r['symbol']} [{r['level'].upper()}]")
            print(f"{'='*60}\n")
            print(r["data"])
            print()


if __name__ == "__main__":
    main()

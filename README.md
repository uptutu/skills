# Uptutu Skills

A collection of AI agent skills for Claude Code and compatible tools. Follows the [agentskills.io](https://agentskills.io) open standard.

## Install

### Install via npx

```bash
npx skills add uptutu/skills -s stock-analyst
```

### Install all skills

```bash
npx skills add uptutu/skills
```

## Usage

### stock-analyst

中国A股交易分析技能。通过内置脚本直接调用 MCP 服务获取实时股票数据，结合 sequential-thinking 进行 buy/sell/hold 决策，提供目标价、止损价、退出计划和风险收益比。

**Prerequisites:** Python 3.6+ (stdlib only, no pip install needed)

**Input format** (one stock per line):

```
<公司名/股票代码>,<持仓数量>,<持仓成本价>
```

**Example:**

```
601689.SH,100,2.2
AAPL,0
```

- 持仓数量 > 0：已持仓，返回 buy/sell/hold 决策
- 持仓数量 = 0：未持仓，返回 buy/wait 建议

**Query stock data manually:**

```bash
# brief: price / change / volume / funds / turnover
python3 scripts/stock_query.py --symbol SH601689 --level brief

# medium: brief + financial data (revenue / profit / EPS)
python3 scripts/stock_query.py --symbol SH601689 --level medium

# full: medium + technical indicators (MACD/RSI/KDJ/BOLL, 30 days)
python3 scripts/stock_query.py --symbol SH601689,SZ000001 --level full

# JSON output
python3 scripts/stock_query.py --symbol SH601689 --level full --format json

# custom MCP server URL
python3 scripts/stock_query.py --symbol 601689 --level brief --server http://your-server/mcp
```

## Add a New Skill

1. Create a directory under `skills/<skill-name>/`
2. Add `skill.json` (manifest) and `SKILL.md` (definition)
3. Optionally add `scripts/` for supporting tools

```
skills/
└── <skill-name>/
    ├── skill.json      # manifest: name, version, description, triggers, deps
    ├── SKILL.md        # skill definition and instructions
    └── scripts/        # (optional) supporting scripts
```

## License

MIT

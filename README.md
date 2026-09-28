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

### intro-pro

提示词精炼器。把口语化、有歧义的提示词改写成措辞精准、目标显式的版本，并输出一段可直接复制给 agent 的提示词。

**用法：**

```
/intro-pro <要精炼的提示词>
```

输出四段：拆出的目标 → 替换记录 → 待确认假设 → 精炼提示词（可复制块）。
不追问；歧义以 `〔假设: …〕` 就地标注；代码、路径、命令、数字等字面量一字不改。
无参数时只提示粘贴，不猜历史消息。

**文件：**

- `skills/intro-pro/SKILL.md` —— 技能定义
- `prompts/intro-pro.md` —— `/intro-pro` 命令壳（可选，给支持 prompt template 的宿主用）

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

### ford（问津）

需求与问题拆解参谋。输入任意模糊想法、明确需求、第三方原始需求或具体技术问题（架构/细节/实现），经复述对齐 → 第一性原理拆解 → ≤5 问边界拷问 → subagent 并行领域分析，交付带引用、可直接下达的方案（Markdown + 可选 HTML）。

**用法：**

```
/问津 <想法 / 需求 / 技术问题>
```

或使用触发词：需求拆解 / 拷问边界 / grill 需求 / 技术方案 等。

**可选依赖（不装也能跑，SKILL.md 内有降级路径）：**

```bash
npx skills add mattpocock/skills -s grill-me   # 阶段 3 拷问风格
npx skills add tw93/Kami -s kami               # 阶段 5 报告渲染 HTML
```

**文件：**

- `skills/ford/SKILL.md` —— 技能定义
- `skills/ford/skill.json` —— 清单
- `skills/ford/cherry-studio.json` —— Cherry Studio 智能体导入文件（智能体页 → 导入），提示词与 SKILL.md 同步（已去 frontmatter）

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

# Vendor: akshare_stock

本目录是 akshare 仓库中 `akshare_stock/` 子包的快照,2026-07-03 从
`/home/alex/codes/akshare` 拷贝而来。

## 为什么 vendor

stock-analyst skill 需要一套本地、离线、A 股综合数据抓取能力(基本面 / 行情 /
K 线 / 16 个技术指标 / 财务 / 板块),akshare 仓库恰好提供这套能力但没有发布到
PyPI。把 akshare_stock 子包拷贝到本仓库,让 stock-analyst 不依赖任何外部代码
路径,完全自给自足。

## 包大小

20 个 Python 文件,约 2500 行抓取 + 渲染代码(无第三方 akshare 包)。

## 安装

vendored 包本身不需要安装,但它的传递依赖需要:

```bash
pip install -r scripts/requirements.txt
```

依赖列表(pandas / numpy / rich)由 `vendor/akshare_stock/*.py` 的 import 语句推导。

## 升级

不需要主动同步。用户决策明确:不与上游 akshare 仓库同步,本快照为最终实现。
若 akshare_stock 子包未来更新导致兼容问题,在 `scripts/stock_query.py` 内部
做适配(修改入口 / 加 try/except),不修改 vendored 代码。

## 文件清单

```
vendor/akshare_stock/
├── __init__.py             # 包标记
├── pipeline.py             # 入口:run(symbol, topk, include_sector, adjust, macd_params, output_format)
├── json_output.py          # JSON 序列化(K 线 49 列全量)
├── printer.py              # Rich 中文面板渲染
├── silence.py              # 噪声抑制
├── retry.py                # 指数退避重试
├── profile.py              # 基本信息 + 板块(4 源并发)
├── history.py              # K 线(东方财富 + 腾讯源回退)
├── quote.py                # 当前行情(K 线末行代理)
├── fundamentals.py         # 财务指标
├── indicators.py           # 指标编排入口
├── indicators_trend.py     # MA / MACD / DMA
├── indicators_momentum.py  # RSI / KDJ / CCI / BIAS
├── indicators_volume.py    # OBV / VR / MFI
├── indicators_pattern.py   # BOLL / 枢轴点 / 斐波那契 / 缺口 / 突破
├── signals.py              # 信号编排入口
├── signals_trend.py
├── signals_momentum.py
├── signals_volume.py
└── signals_pattern.py
```
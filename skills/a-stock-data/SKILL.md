---
name: a-stock-data
description: "当任务需要写代码实际获取A股数据时使用——拉取行情/K线(mootdx+腾讯+百度)、研报(东财+同花顺+iwencai)、信号(热点/北向/龙虎榜/解禁/行业)、资金面(融资融券/大宗/股东户数/分红/资金流)、新闻、财务三表/F10、公告(巨潮)、打板(涨停池/连板/炸板率/重点监控池/日内异动)、ETF期权(T型报价/希腊字母/IV)、舆情互动(互动易/热榜/人气榜)、筹码分布(获利比例/成本区间)、复权因子、估值历史(PE/PB/PS+换手率+ST)、申万行业变迁史、宏观(社融/PMI)等真实数据。十一层数据源·54端点(含3官方备胎)·内嵌全部可运行代码，自包含零依赖外部文件；优先用通达信(mootdx)/腾讯(不封IP)，东财接口已内置限流防封，主源被封可查「备用源速查」降级。仅在需要调用数据接口取数时使用：A股概念解释、投资观点讨论、策略问答等无需取数的话题不要加载本skill。"
---

> **渐进披露式文档**：本文件只保留 frontmatter、分册导览与高频快查；全部端点正文已按章节拆入 `references/` 分册，逐字未改。用法：先按下表定位分册 → 只读所需分册（端点级 §→函数速查另见 references/routing-table.md）。

## 分册导览（主题 → 相对路径 → 一句话）

| 主题 | 文档 | 一句话 |
|---|---|---|
| 总览·版本史·架构树·激活场景 | references/overview.md | 十一层架构全景、V3.x 全部变更日志、When to Activate 触发场景 |
| 端点路由速查 | references/routing-table.md | 54 端点「§→函数→拿什么→源」全表，按需定位分册内章节 |
| 数据源优先级 & 东财防封 | references/source-priority-antiban.md | 通达信/腾讯优先原则、东财风控阈值与实测封禁案例、防封铁律、em_get() 限流说明 |
| Prerequisites | references/prerequisites.md | 依赖清单、tdx_client()（mootdx BESTIP 规避）、市场前缀规则、norm_ticker() 归一化、em_get()/eastmoney_datacenter() 共用 helper |
| Layer 1 行情层 | references/quotes-kline.md | mootdx K线/五档/逐笔、腾讯实时价/PE/PB/市值/涨跌停/指数/ETF、百度K线带MA、新浪复权因子 |
| Layer 2 研报层 | references/research-reports.md | 东财个股/行业研报+PDF下载、同花顺一致预期EPS、iwencai NL语义搜索 |
| Layer 3 信号层 | references/signals.md | 同花顺热点题材归因/北向资金、东财板块归属/个股分钟资金流、龙虎榜、解禁日历、行业排名、板块资金流 |
| Layer 4 资金面 | references/margin-trading.md | 融资融券、大宗交易、股东户数、分红送转、120日个股资金流 |
| Layer 4 筹码分布 | references/chip-distribution.md | CYQ 获利比例/平均成本/90-70成本区间/筹码峰（OHLC+换手率本地推演） |
| Layer 5 新闻层 | references/news.md | 东财个股新闻、财联社快讯（v1+本地签名零key）、东财全球资讯7x24 |
| Layer 6 基础数据层 | references/financial-f10.md | mootdx 财务快照/F10、东财个股信息、新浪财报三表、baostock 估值历史/上市退市日、申万行业变迁史 |
| Layer 7 公告层 | references/announcements.md | 巨潮公告全文检索+PDF下载、mootdx 公告摘要 |
| Layer 8 打板层 | references/limit-up.md | 涨停/炸板/跌停/昨涨停四池、同花顺涨停揭秘、打板情绪速算、重点监控池、日内异动池 |
| Layer 9 ETF 期权层 | references/etf-options.md | 期权合约清单、T型报价、希腊字母+隐含波动率IV |
| Layer 10 舆情互动层 | references/sentiment.md | 互动易投资者问答、同花顺热榜、东财人气榜/概念命中 |
| Layer 11 宏观层 | references/macro.md | 人民银行社会融资规模增量、国家统计局 PMI（制造业/非制造业/综合） |
| 估值计算公式 | references/valuation-formulas.md | 前向PE、PE消化时间、PEG、单票估值全景 full_valuation() |
| 完整调研流程 | references/research-workflow.md | 流程A单票估值 / B批量对比 / C主题研报检索 / D新标的快速调研 |
| 备用源速查 & 降级策略 | references/fallback-sources.md | 数据源优先级简表 + 主源被封时的官方备胎函数与逐层降级路径 |
| FAQ | references/faq.md | 东财403被封、财联社复活、mootdx停更、字段口径等高频问答 |
| 安装说明 | references/install.md | 五步安装与激活验证 |

## 高频快查（以下为最常用端点的用法节选，原样摘自分册，全文见对应文件）

### norm_ticker() — 代码归一化（所有端点入口，全文见 references/prerequisites.md）

```python
# 用法
norm_ticker("SH600519")      # '600519'
norm_ticker("600519.SH")     # '600519'
norm_ticker("bj920982")      # '920982'
norm_ticker("6005190")       # ValueError（7 位，不会被截成 600519）
norm_ticker("茅台")           # ValueError
norm_ticker("SH000001.SZ")   # ValueError（前后缀矛盾，不猜市场）
norm_ticker("SH000001", stock_only=True)     # ValueError（上证指数，不是平安银行）
norm_ticker("000001.SH", stock_only=True)    # ValueError（后缀写法同样拦下）
norm_ticker("SZ600519")                      # ValueError（600519 是沪市，标识矛盾）
norm_ticker("sz000016")                      # '000016'（深康佳A，000 段的显式消歧，合法）
```

### mootdx 行情（K线/五档/逐笔，全文见 references/quotes-kline.md §1.1）

```python
from mootdx.quotes import Quotes

client = tdx_client()  # 见 Prerequisites 的 tdx_client() helper（规避 0.11.x BESTIP bug；等价 Quotes.factory(market='std')）

# === K线数据 ===
# ⚠️ 参数名是 frequency（不是 category！传 category 会被 **kwargs 静默吞掉，
#    永远退化成默认 frequency=9 日线，拿不到分钟数据）。
# mootdx 0.11.7 实测频率值表：
#   0=5分钟  1=15分钟  2=30分钟  3=60分钟(1小时)  4=日线  5=周线  6=月线
#   8=1分钟  9=日线(默认)  10=季线  11=年线        （7=1分钟除权口径,少用）
klines = client.bars(symbol='688017', frequency=9, offset=10)    # 日线
min1   = client.bars(symbol='688017', frequency=8, offset=240)   # 1分钟（一个交易日≈240根）
min5   = client.bars(symbol='688017', frequency=0, offset=48)    # 5分钟
# 返回: open, close, high, low, vol, amount, datetime
# ⚠️ 复权：bars 返回【不复权】原始价（通达信原始数据，无 adjust 参数）。
#    跨除权除息日做估值/回测前需自行复权，或改用带前复权的日K数据源（腾讯财经）。

# === 实时报价 ===
quotes = client.quotes(symbol=['688017', '300476'])
# 返回 46 个字段:
#   price(现价), open, high, low, last_close(昨收)
#   bid1~bid5, ask1~ask5, bid_vol1~bid_vol5, ask_vol1~ask_vol5
#   vol(成交量), amount(成交额), servertime

# === 逐笔成交（非交易时间返回空）===
trades = client.transaction(symbol='688017', date='20260502')
# 返回: time, price, vol, num, buyorsell(0买/1卖/2中性)
```

### 腾讯实时行情（价/PE/PB/市值/涨跌停，全文见 references/quotes-kline.md §1.2）

```python
# 用法: 个股
quotes = tencent_quote(["688017", "300476", "002463"])
for code, q in quotes.items():
    print(f"{q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 用法: 指数 — sh000001=上证指数, sh000300=沪深300, sz399006=创业板指
index_quotes = tencent_quote(["000001", "000300", "399006"])

# 用法: ETF — sh510050=上证50ETF, sh510300=沪深300ETF
etf_quotes = tencent_quote(["510050", "510300"])
```

### 同花顺当日强势股+题材归因（全文见 references/signals.md §3.1）

```python
# 用法
df = ths_hot_reason("2026-05-09")
print(f"当日强势股: {len(df)} 只")
print(df[["代码", "名称", "涨幅%", "题材归因"]].head(10))
```

### 东财涨停池（打板核心，全文见 references/limit-up.md §8.1）

```python
# 用法
zt = em_zt_pool("20260626")
print(f"今日涨停 {len(zt)} 只")
for s in zt[:3]:
    print(f"  {s['name']} {s['zt_stat']} 封板{s['seal_fund']/1e8:.2f}亿 {s['industry']}")
```

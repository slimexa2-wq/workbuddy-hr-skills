---
name: quant-kline-and-event-study
description: A股日线行情高速抓取（腾讯11字段校验）与事件研究（涨停板/公告事件超额收益CAR、t检验及DSR多重检验修正）规范。当进行A股量化回测、信号验证、涨停次日溢价分析或因子显著性检验时激活。
---

# A 股日线抓取与事件研究（Event Study）实证规范

沉淀自本机量化团队（DSH Quant / Codex / Antigravity）在 A 股数据抓取与策略回测中的验证标准与反例教训。

## 1. 腾讯日线接口高速抓取与 11 字段强校验
当 AkShare / 东方财富接口受代理或反爬限制时，优先使用腾讯前复权日线接口（直连稳定、无需 Token）：
- **URL 模板**：
  `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},{count},qfq`
  - `{symbol}`：带市场前缀小写代码，如 `sh600519`、`sz000001`、`bj832566`
- **数据提取与强校验铁律**：
  1. 响应 JSON 路径：`data[symbol]["qfqday"]`（若无复权事件则回退 `data[symbol]["day"]`）。
  2. 每行前 6 个元素固定为：`[date, open, close, high, low, volume]`。
  3. **严禁接受空表或残缺行**：落盘前必须校验：
     - `open > 0, high > 0, low > 0, close > 0`
     - `high >= max(open, close) >= min(open, close) >= low`
     - `volume >= 0`
     - 计算衍生字段 `pct_chg = (close / prev_close - 1) * 100` 与 `amplitude = (high - low) / prev_close * 100` 后，必须检查是否存在停牌跨月导致的跳空失真。

## 2. A 股事件研究（Event Study）与涨停溢价回测铁律
1. **严禁未来函数与不可成交买入假设（Look-Ahead & Unfillable Bias）**：
   - 若事件在 $T$ 日收盘时才确认（如 $T$ 日涨停收盘、$T$ 日盘后公告），**实盘买入点只能是 $T+1$ 日开盘价（或 $T+1$ 日 VWAP）**，严禁以 $T$ 日收盘价计算策略收益。
   - **一字涨停排板过滤**：若 $T+1$ 日全天 `high == low` 且涨停（一字板），普通资金无法在 $T+1$ 日开盘买进，回测中必须将此类样本单独剔除或归入“不可成交组”，否则会严重虚增策略夏普率。
2. **板块涨跌停幅度区分**：
   - 主板（`60xxxx`/`00xxxx`）：非 ST 为 `10%`，ST 为 `5%`（按四舍五入到分位判定涨停价 `round(prev_close * 1.10 + 1e-6, 2)`）。
   - 创业板（`30xxxx`）/ 科创板（`688xxx`）：`20%`。
   - 北交所（`8xxxxx`/`43xxxx`/`92xxxx`）：`30%`。
3. **多重假设检验与 DSR（Deflated Sharpe Ratio）硬门槛**：
   - 历史踩坑教训（Spider Lesson `limit-up-event-study`）：在扫描多组参数或子样本时，单次 $t$ 统计量看似显著（如 $t \approx 2.0$），但经多重检验修正后的 **DSR（去偏夏普比率概率）可能仅 0.3189（远低于 0.95 显著性门槛）**。
   - **交付铁律**：任何量化回测报告必须同时披露：
     - 样本量 $N$、胜率（Win Rate）、均值（Mean）、中位数（Median，防止极值拉高均值）
     - 交易双边成本扣除后净收益（A 股默认扣除印花税 `5 bps` + 双边佣金与滑点 `10-15 bps`，合计单次换手扣除 `15-20 bps`）
     - 尝试过的参数组合总数 $K$ 及修正后的 $p$-value / DSR；未过显著性门槛的必须明确标注“统计不显著，不建议实盘”。

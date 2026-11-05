---
name: manus-agent-runner
description: Manus / Muse 云端协同（Spider Cloud MCP 直连 & DSH Manus Bot）与 Manus v2 API 调用契约（10位秒级时间戳、积分预算硬熔断）规范。当任务需要委派给 Manus/Muse 执行深度多源网页调研、异构文档交付，或排查 Manus API 响应格式与积分消耗时激活。
---

# Manus / Muse 云端协同与 v2 API 调用规范

## 1. 适用边界与最新协同通道（2026-11-01）

- **何时用 Manus / Muse**：需要云端沙箱浏览器多源交叉调研、外部公开信息深度搜集、打包生成多格式长报告。
- **何时不用 Manus**：本机文件读写、内网/本地 Excel 核算（如供应商提成、人力周报）、本机代码重构（直接用本机 Codex / Antigravity / WorkBuddy 或 `spider-plugin` 的 `delegate(mode="parallel")` 免费模型池完成，零积分消耗且数据不出机）。
- **三大协同入口**：
  1. **DSH 专职 Bot 通道（推荐）**：通过 `spider-plugin` 调用 `delegate({ mode: "dsh", target: "manus", prompt: "..." })` 或 `dsh({ action: "dispatch", bot_id: "manus", instruction: "..." })`。
  2. **Muse / Manus 网页版 Cloud MCP 双向直连**：已通过本机 Tailscale Funnel 永久固定域名 `https://wangmacbook-air.tail1df9ca.ts.net/10f98dc41314075d7bee1b4cd0f397d31dcce42ca92deb08/mcp?client=muse&profile=core`（及 Tailnet 内部签名放行）直连本机 Spider Owner 全权 MCP。
  3. **Manus v2 REST API 直接调用**：按下方契约执行。

---

## 2. Manus v2 REST API 认证与基础端点

- **Header**：`x-manus-api-key: $MANUS_API_KEY`（**严禁**使用 `Authorization: Bearer`，否则必报 `401 Unauthorized`）
- **Base URL**：`https://api.manus.im`
- **核心端点**：
  - 创建任务：`POST /v2/task.create`
  - 查询详情：`GET /v2/task.detail?task_id=<id>`
  - 消息流：`GET /v2/task.listMessages?task_id=<id>`
  - 下载文件：`GET /v2/file.getDownloadUrl?file_id=<id>`

---

## 3. 已验证踩坑教训（必须遵守）

1. **时间戳单位是秒（Seconds）而非毫秒**：
   - Manus v2 返回的 `created_at` / `updated_at` 均为 **10 位秒级 Unix 时间戳**（如 `1776569474`）。
   - 在 JavaScript/TypeScript 中转换为 `Date` 时**必须乘以 1000**（`new Date(ts * 1000)`）；在 Python 中直接 `datetime.fromtimestamp(ts)`，切勿除以 1000（否则会变成 1970 年 1 月！）。
2. **积分预算与两档硬熔断**：
   - **单任务上限**：`2,000 credits`。轮询 `task.detail` 时若 `credit_usage > 2000`，立即告警并停止追加追问。
   - **单日累计上限**：`15,000 credits`。发起长任务前优先评估能否由本地 CLI 或 Magpie 免费号池（`group/never-stuck`）分流；确需消耗大量积分时须经用户明确批准。
3. **标准轮询节奏**：
   - 每 `15s` 轮询一次 `GET /v2/task.detail?task_id=...`。
   - 终止状态：`completed`、`failed`、`stopped`、`waiting_for_user`。
   - 遇到 `waiting_for_user` 时，读取最后一条 assistant 提问，能按已知事实回答的自动补充，涉及高风险决策的转交用户拍板。

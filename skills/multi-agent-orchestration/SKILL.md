---
name: multi-agent-orchestration
description: 本机多Agent协同编排（Spider × Magpie 1+1>2 原生总线）、8大本机Agent+3大云端AI选型矩阵、M5芯片并发档位、无头CLI防挂死、同机交错A/B测试、独立交叉验收与孤儿进程清理规范。当需要跨Agent委派任务、并发派生子代理、执行性能/延迟A/B对比或做交付前终审时激活。
---

# 全机多 Agent 协同编排与工程验收规范（2026-11-01 最新版）

沉淀自本机 **8 大本机 Agent（`Antigravity`、`Codex`、`WorkBuddy`、`CodeBuddy`、`ZCode`、`Qoder`、`Hermes`、`DSH 9-Bot`）+ 3 大云端 AI（`ChatGPT Web`、`Gemini Cloud/App`、`Muse/Manus`）** 经由 **Spider × Magpie `1+1>2` 极速协同总线** 的实战运行标准与避坑铁律。

---

## 1. Spider × Magpie 原生协同总线（首选调用方式）

全机 8 大本机 Agent 已通过 Magpie Library 统一挂载进程内极速原生插件 **`spider-plugin`**（`http://127.0.0.1:3425/mcp/magpie/tools/spider`，基于 `bun:sqlite` `<1ms` 直连 `memory.db` 与 `hub.db`）：

1. **零轮次起手（省去 `spider_loadout`）**：
   - 凡经 Magpie 网关（`127.0.0.1:3425`）发起的请求，网关 `onRequest`（`spider-memory.hooks.ts`）已在 `<1ms` 内自动将 **指派给当前 Agent 的待办任务、其他 Agent 实时黑板动态、L1 确认铁律、L2 关联记忆与匹配共享技能** 注入 `<system-reminder><!-- spider-context -->`。
   - 看到 `<!-- spider-context -->` 时直接作答，**不要再浪费 1 轮 Tool Call 调用 `spider_loadout`**；仅在需深挖更多历史时调 `recall({ query })`，需直读某项共享技能全文时调 `recall({ resource_id: "skill:<name>" })`（`<0.5ms`）。
2. **三大协同派单模式（`delegate` 工具）**：
   - **`mode: "parallel"`（多模型并发子 Agent）**：调用 `delegate({ mode: "parallel", subtasks: [{ title, prompt, role }] })`，进程内 `<1ms` 自动为每个子任务检索装填 Spider L1 铁律与 L2 记忆，并借用 Magpie 免费模型池（`auto/deepseek-v4.1-flash` / `group/never-stuck` 9 渠道毫秒级故障转移）1~5 路并发执行、当场返回结果并自动在 `hub.db` 结单。
   - **`mode: "dsh"`（唤醒 DSH 9-Bot 专职舰队）**：调用 `delegate({ mode: "dsh", target: "大肥鱼|招聘|数据|量化|openai|google|anthropic|workbuddy|manus", prompt: "..." })` 自动注入 Spider 关联铁律并派发给专职 Bot。
   - **`mode: "handoff"`（跨 CLI Agent 精准交接）**：调用 `delegate({ mode: "handoff", target: "codex|antigravity|workbuddy|qoder|zcode", title, prompt })`，对方下次请求经过 Magpie 网关时 `<1ms` 自动置顶注入；接收方完成后只需在回复末尾附带 `[TASK_DONE: 任务ID]`（或调 `tasks({ action: "complete", id })`），网关 `onResponse` `<0.5ms` 自动结单并广播至全机实时黑板。

---

## 2. 全机 Agent 选型矩阵（按任务类型走最短路径）

| 任务类型 | 首选 Agent / 通道 | 标准调用方式 | 核验与配合机制 |
|---|---|---|---|
| **多文件工程重构、并发子代理核算（如多项目提成并行审核）、复杂脚本与自动化测试** | **Codex** (`gpt-5.4`) | 跨端交接：`delegate({ mode: "handoff", target: "codex" })`；或 Codex 原生子代理；或底层脚本 `/Users/wangmini/.dsh/bot/workspace/team/_shared/tools/agent-run.sh` | 搭配 `independent-reviewer` 子代理做落盘证据核验 |
| **交互式全栈架构、MCP 密集编排、科学可视化、UI/浏览器直控、Spider Dream 治理** | **Antigravity (AGY)** | IDE 主会话；或 `delegate({ mode: "handoff", target: "antigravity" })`；或脚本 `/Users/wangmini/.local/share/spider/scripts/agy-run.sh` | 修改配置前必备份，收尾通过 `fact` / `capture` 写回 |
| **本地 Office/Excel/Word 批处理、招聘/HR 业务流、国内生态快速落地** | **WorkBuddy / CodeBuddy / Qoder / ZCode** | 客户端会话或 `delegate({ mode: "handoff", target: "workbuddy" })` | 沙箱内 `npm/pip` 大批量文件操作遇阻时启用 `workbuddy-sandbox-pkg-install` |
| **快速并发核验、多角度审查、低成本批量子任务** | **Magpie 并行协办池** | `delegate({ mode: "parallel", subtasks: [...] })`（默认走 `auto/deepseek-v4.1-flash` 免费池） | 自动携带 Spider L1 铁律与 L2 记忆，2~3 秒并发返回 |
| **常驻团队分诊、厂商专项研究、量化/数据/招聘日常巡检** | **DSH 9-Bot 舰队** | `delegate({ mode: "dsh", target: "数据|量化|招聘|大肥鱼" })` 或 `dsh({ action: "status|dispatch" })` | 模型路由已由 Magpie `group/never-stuck` 统一接管 |
| **云端网页端远程协同与多源深度调研** | **ChatGPT Web / Gemini Cloud / Muse (Manus)** | 已通过 Tailscale Funnel 永久域名 `https://wangmacbook-air.tail1df9ca.ts.net` 挂载 Spider Owner 全权 MCP（57 工具）；或调用 `manus-agent-runner` | 云端与本机共享同一套 `memory.db` 与 `hub.db` |

---

## 3. Apple Silicon M5 (4P+6E, 32GB) 并发档位与子 Agent 分治法则

根据本机 M5 硬件实测（4 个 Super 性能大核共享 16MB L2 缓存 + 6 个 Efficiency 能效小核，纯被动散热 + 外接风扇散热架）：

1. **本地重型 Worker 并发档位硬约束**：
   - **黄金档位（Sweet Spot）**：**4 个并发 Worker**（1:1 独占 4 个 Super 核心，零 Swap 颠簸，单任务延迟最低）。
   - **高吞吐上限**：**6 ~ 8 个并发 Worker**（编译构建参数统一固化为 `MAKEFLAGS="-j6"`、`CARGO_BUILD_JOBS=6`）。
   - **严禁超载**：严禁在本地同时拉起 `10+` 个重型编译/浏览器/Python Worker，防止 4 个 Super 核心 L2 缓存剧烈抖动（Eviction）与被动散热降频；长耗时后台任务前面加 `taskpolicy -b <cmd>` 压入 6 个能效小核运行。
2. **单项目物理隔离（`delivery_style.staged_incremental`）**：
   - 处理多项目提成审核或多分子公司报表时，每个子 Agent（`single-project-auditor`）每次只负责 **1 个独立项目**，独立查 SQLite 政策库（`sync_policy_sqlite.py`），核完 1 个立即静默生成《（审核版）》落盘，绝不把多个不同表头的项目混在同一上下文中提取。
3. **两振熔断与职责分离**：
   - 同一命令或路径连续 2 次失败无新信息立即停止盲试并切换独立路径；实现者自称完成不等于完成，必须经 `independent-reviewer` 核验落盘文件、零批注/空值填 0 与公式重算结果。

---

## 4. 同机性能/网络 A/B 测试铁律（`shared-machine-ab-must-interleave`）

在本机对比两个代理节点、两个模型端点或两套并发参数时：
- **严禁顺序分块测试**（如先连续跑完 A 方案 10 分钟，再跑 B 方案 10 分钟），避免 macOS 内存压缩池（Compressor Pool）与被动散热温升造成先后顺序偏差。
- **必须采用交错配对设计（Interleaved Paired Design）**：按 `A1 → B1 → B2 → A2 ...` 轮换交错采样，留固定冷却窗口，使用配对差值（Paired Difference）的中位数与分位数评估优劣。

---

## 5. 进程卫生与孤儿进程清理铁律（`agent_process_hygiene_rule`）

1. **严禁遗留后台孤儿进程**：Agent 任务完成或异常退出时，必须主动清理自己启动的临时子进程、测试 HTTP 服务与临时文件；严禁手写无退出的 `while true` 保活脚本（常驻服务统一由 `launchd` 托管，且注意 `ai.watchdog.renderer` 与 `com.workbuddy.kzzi-k75-modifier` 已永久停用隔离，切勿恢复）。
2. **自动与按需清理通道**：
   - 本机已部署 `com.wangmini.agent-reaper` 守护服务（每 10 分钟自动运行 `/Users/wangmini/.local/bin/agent-reaper` -> `/Users/wangmini/.local/share/agent-reaper/agent_reaper.py` 清理无主孤儿进程）；
   - 也可随时通过 `spider-plugin` 调用 `dsh({ action: "optimize", sub_action: "clean_orphan_processes" })` 一键清理。

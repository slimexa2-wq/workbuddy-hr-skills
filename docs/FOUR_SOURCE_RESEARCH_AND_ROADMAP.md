> 🚨 **最高统帅原则（效率第一 · 后台复杂 · 前端极简 · 严禁过度安全）**：
> 1. **严禁过度安全恶心用户**：砍掉一切冗余的二次确认令牌、繁琐弹窗拦截、机械必填报错与人为卡点；常规操作采用“一键直达 + 后台自动快照备份 + 随时可撤回”。
> 2. **后台复杂、前端极简**：所有格式兼容、脏数据清洗、漏填状态补齐、四方公式核对、跨表勾稽全部封装在后台自动完成；前端交互必须做到傻瓜式直观（1 步输入/拖入 → 1 键出定稿结果），便捷所有使用者！
> 3. **Top 50 开源标杆融合**：详见同目录 `docs/TOP50_OPEN_SOURCE_FUSION.md`。

# 祥能 HR 自动化技能套件与系统预检卫士深度调研与演进蓝图（四源对标版）

> **调研基线**：本蓝图汇总 **① 祥能集团 16 项生产级 HR 技能与周期报表铁律**、**② 同类产品（影刀 RPA / UiPath / 飞书多维表格自动化）**、**③ 优秀开源项目（`python-calamine` / `openpyxl` OOXML 原生引擎）** 与 **④ 电子表格公式静态分析与多 Agent 进程治理研究**，指导本仓库技能脚本与守护工具的持续完善。

---

## 一、四源深度调研矩阵

### 1. 本公司真实业务资料与核心交付红线
- **全局 Excel 交付三道铁律（`deliverable_zero_fill_and_no_annotation_rule`）**：
  1. **零批注（`comments=0`）**：定稿表严禁包含任何单元格批注或表底“核验说明”废话。
  2. **空值填 `0`（`blanks=0`）**：数值格无数据一律填数字 `0`，文本格填 `"/"` 或 `"0"`，绝不留空。
  3. **WPS 占用锁预检与原子备份（`check_wps_lock`）**：写入前自动检测 `wpsoffice / Excel` 进程占用与 `~$` 临时锁文件，发现占用立即 `Exit Code 2` 阻断，并在 `/tmp` 生成带时间戳原子备份。
- **核心自动化套件业务规则**：
  - **周期资源报表套件（`periodic-resource-reports`）**：每周一 3 项（在离职周报、项目需求周报、学生工需求与校招推进周报）+ 每月初 4 项（自主招聘台账 2026-10 基准 `254人` 金标准核算、资源目标达成进度表横向漏列扫描、内部提成对账、肖总月度绩效联动）。
  - **供应商提成四方核对（`supplier-commission-audit`）**：B-Tree SQLite 精确政策库（`sync_policy_sqlite.py` 自动清除过期旧表）+ 单项目物理隔离核对 + `ooxml_append.py` 无损追加右侧 6 列（剥离幽灵空列、保持原工作簿公式/行高/合并单元格 100% 不变）。
  - **新员工入职档案生成（`employee-onboarding-dossier`）**：`pdf2png` 高清正立转换、身份证/银行卡/体检报告版式自动编排。

### 2. 同类标杆商业产品对标
- **影刀 RPA / UiPath Document Understanding**：借鉴其针对非标业务表格的“表头语义指纹匹配（Header Fuzzy Fingerprinting）”与“执行前-执行中-执行后”三段式门禁校验报告。

### 3. 优秀开源项目借鉴
- **`python-calamine` (Rust `calamine` 绑定)**：借鉴其对 WPS 导出的非标准/空 `<fill/>` 样式的免疫特性，作为高速只读解析首选引擎。
- **OOXML 原生 ZIP/XML 注入技术**：直接操作 `xl/worksheets/sheet*.xml` 与 `xl/styles.xml`，避免 `openpyxl` 全量重序列化破坏复杂外链、条件格式与打印区域。

### 4. 学术论文与算法支撑
- **Spreadsheet Formula Smell Detection (ICSE / FSE)**：自动检测纵向 `SUM` 漏选末尾新增行（如双流大茂丰安保漏行）、跨列引用错位（如总计行误引 `V29` 而非 `M29`）、文本型数字（带 `
` 或空格）导致求和失真等经典电子表格缺陷。

---

## 二、分阶段功能完善与工程演进路线图

### Phase 1：电子表格公式缺陷静态扫描器与预检门禁升级（`guards/` + `skills/periodic-resource-reports`）
1. 增强 `guards/agent-preflight-guard` 的 `xlsx-check` 能力：除检测批注（`comments=0`）、空值（`blanks=0`）与公式错误（`#REF! / #VALUE! / #NAME?`）外，新增 **SUM 区间断层/漏行自动预警** 与 **文本型数字（Numeric-String Smell）自动识别**。
2. 为 `periodic_reports_suite.py`、`ooxml_append.py`、`sync_policy_sqlite.py` 补齐基于合成夹具（Synthetic Excel Fixtures）的端到端回归测试套件，确保 `< 3.0s` 极速执行与 100% 确定性通过。

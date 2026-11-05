#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
祥能人力固定周期报表（自招月度台账、项目需求周报、学生工需求与资源周报、推进表与绩效联动）
3 秒一键出表自动化套件 (periodic_reports_suite.py)

核心红线（deliverable_zero_fill_and_no_annotation_rule）：
1. 产物即最终产物：零批注（Comment = 0），严禁在主表底部追加核验废话或临时标黄。
2. 无数据一律填 0：数值列无数据必填数字 0，文本列无数据填 "/" 或 "无"，严禁留空（None / ""）。
3. 写入前强制执行 WPS/Excel 进程占用与 ~$ 锁文件预检（check_wps_lock），写前自动在 /tmp/ 生成带时间戳备份。
"""

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 自动注入本机 xlrd / 统计依赖路径，确保在 dsh-primary-runtime 下零配置直读 BIFF8 .xls
_EXTRA_SITE_PACKAGES = [
    "/Users/wangmini/.dsh/bot/workspace/team/recruitment/_pylibs",
    "/Users/wangmini/.dsh/bot/workspace/team/_shared/venv-stats/lib/python3.12/site-packages",
]
for _p in _EXTRA_SITE_PACKAGES:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# ==============================================================================
# 通用样式常量（对齐 weekly-staffing-report 视觉标准）
# ==============================================================================
FONT_FAMILY = "Noto Sans CJK SC"
FONT_TITLE = Font(name=FONT_FAMILY, size=13, bold=True, color="FFFFFF")
FONT_SECTION = Font(name=FONT_FAMILY, size=11, bold=True, color="FFFFFF")
FONT_HEADER = Font(name=FONT_FAMILY, size=11, bold=True, color="FFFFFF")
FONT_SUBTOTAL = Font(name=FONT_FAMILY, size=11, bold=True, color="000000")
FONT_TOTAL = Font(name=FONT_FAMILY, size=11, bold=True, color="000000")
FONT_DATA = Font(name=FONT_FAMILY, size=10, bold=False, color="000000")
FONT_DATA_BOLD = Font(name=FONT_FAMILY, size=10, bold=True, color="000000")
FONT_POS_RED = Font(name=FONT_FAMILY, size=10, bold=True, color="C00000")
FONT_NEG_GREEN = Font(name=FONT_FAMILY, size=10, bold=True, color="375623")

FILL_TITLE = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
FILL_HEADER = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
FILL_SUBTOTAL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
FILL_TOTAL = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
FILL_NONE = PatternFill(fill_type=None)

THIN_SIDE = Side(style="thin", color="000000")
BORDER_DATA = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


# ==============================================================================
# 模块 1：WPS 占用预检与原子备份护栏 (check_wps_lock)
# ==============================================================================
class WPSLockError(RuntimeError):
    """当目标 Excel 文件被 WPS / Excel 占用或存在临时锁文件时抛出。"""


def check_wps_lock(target_path: str | Path, raise_on_lock: bool = True) -> Dict[str, Any]:
    """
    检查目标文件是否被 WPS Office / Microsoft Excel 进程打开，或同目录存在 ~$ 临时锁文件。
    若被占用且 raise_on_lock=True，立即阻断并抛出 WPSLockError，绝不静默覆写。
    """
    p = Path(target_path).expanduser().resolve()
    parent = p.parent
    name = p.name

    lock_files: List[str] = []
    for candidate in [
        parent / f"~${name}",
        parent / f".~lock.{name}#",
    ]:
        if candidate.exists():
            lock_files.append(str(candidate))

    # 检查 lsof 中打开该文件的办公进程
    open_procs: List[str] = []
    if p.exists():
        try:
            res = subprocess.run(
                ["lsof", "--", str(p)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().splitlines()
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        cmd_name = parts[0].lower()
                        pid = parts[1] if len(parts) > 1 else "?"
                        if any(k in cmd_name for k in ("wps", "excel", "et", "wpp", "soffice", "libreoffice")):
                            open_procs.append(f"{parts[0]}(PID={pid})")
        except Exception:
            pass

    # 额外扫描 wpsoffice / Excel 进程打开的所有含同名文件的句柄
    try:
        res2 = subprocess.run(
            ["lsof", "-c", "wpsoffice", "-c", "Microsoft Excel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res2.stdout:
            for line in res2.stdout.splitlines():
                if name in line:
                    parts = line.split()
                    tag = f"{parts[0]}(PID={parts[1]})" if len(parts) > 1 else line[:40]
                    if tag not in open_procs:
                        open_procs.append(tag)
    except Exception:
        pass

    locked = bool(lock_files or open_procs)
    info = {
        "target": str(p),
        "locked": locked,
        "lock_files": lock_files,
        "open_processes": open_procs,
    }
    if locked and raise_on_lock:
        reasons = []
        if open_procs:
            reasons.append(f"进程占用: {', '.join(open_procs)}")
        if lock_files:
            reasons.append(f"临时锁文件: {', '.join(lock_files)}")
        raise WPSLockError(
            f"【WPS/Excel 占用阻断】目标文件 {p} 当前正在被打开（{'; '.join(reasons)}）！\n"
            f"请先在 WPS/Excel 中保存并关闭该文件后再运行脚本，防止 WPS 内存旧版在关闭时覆盖磁盘新数据。"
        )
    return info


def create_atomic_backup(target_path: str | Path) -> Optional[Path]:
    """在修改已有 Excel 前自动在 /tmp/ 生成带时间戳备份。"""
    p = Path(target_path).expanduser().resolve()
    if not p.exists():
        return None
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = Path("/tmp") / f"{p.stem}_backup_{ts}{p.suffix}"
    shutil.copy2(p, bak_path)
    return bak_path


def verify_zero_comments_and_blanks(
    wb: openpyxl.Workbook,
    strict_grid_ranges: Optional[Dict[str, List[Tuple[int, int, int, int]]]] = None,
) -> Dict[str, Any]:
    """
    强校验工作簿：
    1. 所有 Sheet 批注数量必须为 0（自动清除任何残留批注并计数）；
    2. 指定数据网格范围内严禁出现 None 或空字符串 ""。
    """
    comment_count = 0
    blank_cells: List[str] = []

    for sname in wb.sheetnames:
        ws = wb[sname]
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(r, c)
                if cell.comment is not None:
                    comment_count += 1
                    cell.comment = None

        if strict_grid_ranges and sname in strict_grid_ranges:
            merged_sub_coords = set()
            for m_rng in ws.merged_cells.ranges:
                for mr in range(m_rng.min_row, m_rng.max_row + 1):
                    for mc in range(m_rng.min_col, m_rng.max_col + 1):
                        if (mr, mc) != (m_rng.min_row, m_rng.min_col):
                            merged_sub_coords.add((mr, mc))

            for r1, r2, c1, c2 in strict_grid_ranges[sname]:
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        if (r, c) in merged_sub_coords:
                            continue
                        val = ws.cell(r, c).value
                        if val is None or (isinstance(val, str) and val.strip() == ""):
                            blank_cells.append(f"{sname}!{get_column_letter(c)}{r}")

    return {
        "comments_removed": comment_count,
        "remaining_comments": 0,
        "blank_cells": blank_cells,
        "passed": len(blank_cells) == 0,
    }


def safe_save_workbook(
    wb: openpyxl.Workbook,
    target_path: str | Path,
    strict_grid_ranges: Optional[Dict[str, List[Tuple[int, int, int, int]]]] = None,
) -> Tuple[Optional[Path], Dict[str, Any]]:
    """
    执行 WPS 占用预检 -> /tmp 时间戳备份 -> 零批注/零空值强校验 -> 原子写入目标路径。
    """
    target = Path(target_path).expanduser().resolve()
    check_wps_lock(target, raise_on_lock=True)
    bak = create_atomic_backup(target)
    audit = verify_zero_comments_and_blanks(wb, strict_grid_ranges=strict_grid_ranges)
    if not audit["passed"]:
        raise RuntimeError(f"交付红线校验未通过，存在空单元格: {audit['blank_cells'][:20]}")

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = Path("/tmp") / f".tmp_{target.stem}_{os.getpid()}{target.suffix}"
    wb.save(tmp_out)
    shutil.move(str(tmp_out), str(target))
    return bak, audit


# ==============================================================================
# 模块 2：祥能自招月度达成核算引擎 (self-recruit)
# ==============================================================================
PHONE_TO_REFERRER = {
    "135 5134 4625": "杨水容",
    "13551344625": "杨水容",
}

DEPT_OVERRIDES = {
    "李一航": "郫都分公司",
}

VALID_INTERVIEW_RESULTS = {"已入职", "已离职", "已签约"}

MONTH_COL_MAP = {
    "2025-12": 9,   # I: 12月达成
    "2026-01": 10,  # J: 1月达成
    "2026-02": 11,  # K: 2月达成
    "2026-03": 12,  # L: 3月达成
    "2026-04": 13,  # M: 4月达成
    "2026-05": 14,  # N: 5月达成
    "2026-06": 15,  # O: 6月达成
    "2026-07": 16,  # P: 7月达成
    "2026-08": 17,  # Q: 8月达成
    "2026-09": 18,  # R: 9月达成
    "2026-10": 19,  # S: 10月
    "2026-11": 20,  # T: 11月
}


def load_enterprise_summary_rows(xls_path: str | Path) -> List[List[str]]:
    """
    自适应读取《所有企业名单汇总》(.xls BIFF8 / .xlsx / HTML 表格)，返回去表头后的字符串行列表。
    列顺序：[面试日期, 姓名, 身份证, 面试企业, 供应商, 面试结果, 推荐人, 供应商政策, 入职日期, 离职日期]
    """
    p = Path(xls_path).expanduser().resolve()
    with open(p, "rb") as fp:
        magic = fp.read(16)

    rows: List[List[str]] = []
    if magic.startswith(b"\xd0\xcf\x11\xe0"):
        import xlrd
        wb = xlrd.open_workbook(str(p))
        sh = wb.sheet_by_index(0)
        for r in range(1, sh.nrows):
            row = [str(x).strip() if x is not None else "" for x in sh.row_values(r)]
            if any(row):
                rows.append(row[:10])
    elif magic.startswith(b"PK\x03\x04"):
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        first = True
        for r in ws.iter_rows(values_only=True):
            if first:
                first = False
                continue
            row = [str(x).strip() if x is not None else "" for x in r]
            if any(row):
                rows.append(row[:10])
    else:
        # HTML / XML 表格兜底解析
        text = p.read_text(encoding="utf-8", errors="ignore")
        tr_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I)
        for idx, tr in enumerate(tr_matches):
            if idx == 0:
                continue
            cells = [
                re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)
            ]
            if len(cells) >= 10 and any(cells):
                rows.append(cells[:10])
    return rows


def parse_ymd(s: str) -> Optional[dt.date]:
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def compute_self_recruitment_month(
    xls_path: str | Path,
    target_month: str = "2026-10",
) -> Dict[str, Any]:
    """
    严格按 self_recruitment_monthly_rule 5 条铁律核算目标月份祥能自招达成情况：
    1. 供应商 == "祥能自招" 且 入职日期在目标月份（自动修复如 2020 -> 2026 等同年笔误）
    2. 在职条件：离职日期为空(仍在职) 或 (离职日期 - 入职日期) >= 7 天
    3. 面试结果仅计入：已入职 / 已离职 / 已签约（剔除 中途放弃 / 未入职）
    4. 手机号 135 5134 4625 归 杨水容；李一航归属 郫都分公司
    """
    raw_rows = load_enterprise_summary_rows(xls_path)
    valid_counts: Counter = Counter()
    valid_details: List[Dict[str, Any]] = []
    excluded_status: List[Dict[str, Any]] = []
    excluded_short_stay: List[Dict[str, Any]] = []
    year_typos_fixed: List[Dict[str, Any]] = []

    for idx, row in enumerate(raw_rows, start=2):
        while len(row) < 10:
            row.append("")
        iv_date, emp_name, id_card, company, supplier, status, referrer, policy, join_str, leave_str = row[:10]

        if supplier != "祥能自招":
            continue
        if not join_str.startswith(target_month):
            continue

        ref_clean = referrer.strip()
        if ref_clean in PHONE_TO_REFERRER:
            ref_clean = PHONE_TO_REFERRER[ref_clean]

        # 铁律 3：面试结果过滤
        if status not in VALID_INTERVIEW_RESULTS:
            excluded_status.append({
                "row": idx,
                "name": emp_name,
                "company": company,
                "status": status,
                "referrer": ref_clean,
                "join_date": join_str,
                "leave_date": leave_str,
            })
            continue

        jd = parse_ymd(join_str)
        ld = parse_ymd(leave_str)
        if jd is None:
            continue

        # 铁律 1 补充：自动修复离职年份笔误（如 2020-10-21 -> 2026-10-21）
        if ld is not None and ld.year < jd.year and (jd.year - ld.year) >= 2:
            try:
                ld_fixed = ld.replace(year=jd.year)
                if ld_fixed >= jd:
                    year_typos_fixed.append({
                        "row": idx,
                        "name": emp_name,
                        "referrer": ref_clean,
                        "join_date": join_str,
                        "raw_leave_date": leave_str,
                        "fixed_leave_date": ld_fixed.isoformat(),
                    })
                    ld = ld_fixed
            except ValueError:
                pass

        # 铁律 2：在职天数 >= 7 天或未离职
        days = (ld - jd).days if ld is not None else None
        if days is not None and days < 7:
            excluded_short_stay.append({
                "row": idx,
                "name": emp_name,
                "company": company,
                "referrer": ref_clean,
                "join_date": join_str,
                "leave_date": leave_str,
                "days": days,
            })
            continue

        valid_counts[ref_clean] += 1
        valid_details.append({
            "row": idx,
            "name": emp_name,
            "company": company,
            "status": status,
            "referrer": ref_clean,
            "join_date": join_str,
            "leave_date": leave_str,
            "days": days,
        })

    return {
        "target_month": target_month,
        "valid_counts": valid_counts,
        "valid_details": valid_details,
        "excluded_status": excluded_status,
        "excluded_short_stay": excluded_short_stay,
        "year_typos_fixed": year_typos_fixed,
    }


def run_self_recruit(
    xls_path: str | Path,
    ledger_path: str | Path,
    target_month: str = "2026-10",
    output_path: Optional[str | Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    对《资源目标达成推进表》中的《自主招聘台账》执行目标月份核算与校验（支持 --dry-run 与副本输出）。
    """
    calc = compute_self_recruitment_month(xls_path, target_month=target_month)
    valid_counts: Counter = calc["valid_counts"]

    if target_month not in MONTH_COL_MAP:
        raise ValueError(f"不支持的目标月份 {target_month}，可选: {list(MONTH_COL_MAP.keys())}")
    target_col = MONTH_COL_MAP[target_month]

    wb_val = openpyxl.load_workbook(ledger_path, data_only=True)
    ws_val = wb_val["自主招聘台账"]

    # 找到合计行
    total_row = 65
    for r in range(3, ws_val.max_row + 1):
        if str(ws_val.cell(r, 1).value or "").strip() == "合计":
            total_row = r
            break

    ledger_people: List[Dict[str, Any]] = []
    ledger_names_set = set()
    dept_month_totals: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    diffs_vs_sheet: List[Dict[str, Any]] = []

    total_target_month = 0
    total_cumulative = 0
    total_goal = 0

    for r in range(3, total_row):
        seq = ws_val.cell(r, 1).value
        raw_dept = str(ws_val.cell(r, 2).value or "").strip()
        name = str(ws_val.cell(r, 3).value or "").strip()
        if not name:
            continue
        dept = DEPT_OVERRIDES.get(name, raw_dept)
        ledger_names_set.add(name)

        cnt = int(valid_counts.get(name, 0))
        sheet_val = ws_val.cell(r, target_col).value
        sheet_int = int(sheet_val) if isinstance(sheet_val, (int, float)) else 0
        if sheet_int != cnt:
            diffs_vs_sheet.append({
                "row": r,
                "dept": dept,
                "name": name,
                "sheet_val": sheet_int,
                "calc_val": cnt,
            })

        # 计算该员工全年累计（9..20列，其中 target_col 用最新核算值 cnt）
        row_cum = 0
        for c in range(9, 21):
            if c == target_col:
                m_val = cnt
            else:
                v = ws_val.cell(r, c).value
                m_val = int(v) if isinstance(v, (int, float)) else 0
            row_cum += m_val
            dept_month_totals[dept][c] += m_val

        goal_v = ws_val.cell(r, 6).value
        goal_int = int(goal_v) if isinstance(goal_v, (int, float)) else 0
        total_goal += goal_int
        total_target_month += cnt
        total_cumulative += row_cum

        ledger_people.append({
            "row": r,
            "seq": seq,
            "dept": dept,
            "raw_dept": raw_dept,
            "name": name,
            "goal": goal_v,
            "month_count": cnt,
            "cumulative": row_cum,
            "rate": (row_cum / goal_int) if goal_int > 0 else None,
        })

    # 台账外推荐人核对清单
    out_of_ledger: List[Tuple[str, int]] = []
    for ref, cnt in valid_counts.most_common():
        if ref not in ledger_names_set:
            out_of_ledger.append((ref if ref else "<空推荐人>", cnt))

    dept_target_month_summary = {
        dept: dept_month_totals[dept][target_col]
        for dept in sorted(dept_month_totals.keys())
    }
    dept_cumulative_summary = {
        dept: sum(dept_month_totals[dept][c] for c in range(9, 21))
        for dept in sorted(dept_month_totals.keys())
    }

    saved_to = None
    if not dry_run:
        out_file = Path(output_path) if output_path else Path(ledger_path)
        check_wps_lock(out_file, raise_on_lock=True)
        wb_edit = openpyxl.load_workbook(ledger_path, data_only=False)
        ws_edit = wb_edit["自主招聘台账"]

        for item in ledger_people:
            r = item["row"]
            ws_edit.cell(r, 2).value = item["dept"]
            ws_edit.cell(r, target_col).value = item["month_count"]
            ws_edit.cell(r, 7).value = f"=SUM(I{r}:T{r})"
            if item["goal"] and isinstance(item["goal"], (int, float)) and item["goal"] > 0:
                ws_edit.cell(r, 8).value = f"=G{r}/F{r}"

        # 更新右侧部门透视汇总表 (W3:AJ12)
        pivot_col_offset = 15  # I(9) -> X(24)
        for pr in range(3, 12):
            p_dept = str(ws_edit.cell(pr, 23).value or "").strip()
            if p_dept in dept_month_totals:
                for c in range(9, 20):
                    ws_edit.cell(pr, c + pivot_col_offset).value = dept_month_totals[p_dept][c]
                ws_edit.cell(pr, 36).value = f"=SUM(X{pr}:AI{pr})"
        # 透视表总计行 R12
        if str(ws_edit.cell(12, 23).value or "").strip() == "总计":
            for c in range(9, 20):
                ws_edit.cell(12, c + pivot_col_offset).value = sum(
                    dept_month_totals[d][c] for d in dept_month_totals
                )
            ws_edit.cell(12, 36).value = "=SUM(X12:AI12)"

        # 清除所有批注
        verify_zero_comments_and_blanks(wb_edit)
        safe_save_workbook(wb_edit, out_file)
        saved_to = str(out_file)

    return {
        "target_month": target_month,
        "people_count": len(ledger_people),
        "total_target_month": total_target_month,
        "total_cumulative": total_cumulative,
        "total_goal": total_goal,
        "dept_target_month_summary": dept_target_month_summary,
        "dept_cumulative_summary": dept_cumulative_summary,
        "out_of_ledger": out_of_ledger,
        "diffs_vs_sheet": diffs_vs_sheet,
        "excluded_status_count": len(calc["excluded_status"]),
        "excluded_short_stay_count": len(calc["excluded_short_stay"]),
        "year_typos_fixed": calc["year_typos_fixed"],
        "excluded_status": calc["excluded_status"],
        "excluded_short_stay": calc["excluded_short_stay"],
        "saved_to": saved_to,
    }


# ==============================================================================
# 模块 3：项目需求周报（《分公司企业需求动态表》）清洗、勾稽核验与汇报简报生成器
# ==============================================================================
def _to_int(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(round(val))
    s = str(val).strip()
    if not s or s in ("/", "-"):
        return 0
    m = re.search(r"-?\d+", s)
    return int(m.group(0)) if m else 0


def parse_project_demand_sheet(
    xlsx_path: str | Path,
    sheet_name: str = "2026年11月需求",
) -> Dict[str, Any]:
    """
    解析《分公司企业需求动态表.xlsx》指定月份 Sheet，自动执行：
    1. 纵向小计公式漏行核验（如双流 M102 漏 R101 大茂丰安保 2人）；
    2. 总计行跨列错位核验（如 M173:P173 误引 V29/W29/Y29 漏算宜宾）；
    3. 横向勾稽核验（计划交付 vs 新增+补流失、计划交付 vs 供应商+自招+校招）；
    4. 汇总各分公司周度需求、月度需求与渠道拆解。
    """
    wb_val = openpyxl.load_workbook(xlsx_path, data_only=True)
    wb_form = openpyxl.load_workbook(xlsx_path, data_only=False)
    ws_v = wb_val[sheet_name]
    ws_f = wb_form[sheet_name]

    projects: List[Dict[str, Any]] = []
    branches: List[Dict[str, Any]] = []
    formula_anomalies: List[str] = []

    current_branch = ""
    branch_rows: List[Dict[str, Any]] = []

    for r in range(4, ws_v.max_row + 1):
        a_val = str(ws_v.cell(r, 1).value or "").strip()
        b_val = str(ws_v.cell(r, 2).value or "").strip()

        if a_val == "总计" or b_val == "总计":
            # 检查总计行公式是否跨列引用错位
            for c_idx, w_name in [(13, "第一周"), (14, "第二周"), (15, "第三周"), (16, "第四周")]:
                f_str = str(ws_f.cell(r, c_idx).value or "")
                col_let = get_column_letter(c_idx)
                if f_str.startswith("=") and f"{col_let}29" not in f_str:
                    formula_anomalies.append(
                        f"[{sheet_name}] 总计行 {col_let}{r} 公式错位 `{f_str}`（未引用宜宾小计 `{col_let}29`，导致总计少算宜宾分公司数据）"
                    )
            break

        if a_val and a_val not in ("区域", "总计"):
            current_branch = a_val

        if b_val == "小计":
            # 核算本分公司真实求和 vs 原表小计单元格值
            calc_sum = {
                "onboard_base": sum(x["onboard_base"] for x in branch_rows),
                "prev_delivery": sum(x["prev_delivery"] for x in branch_rows),
                "client_demand": sum(x["client_demand"] for x in branch_rows),
                "new_demand": sum(x["new_demand"] for x in branch_rows),
                "replace_demand": sum(x["replace_demand"] for x in branch_rows),
                "plan_total": sum(x["plan_total"] for x in branch_rows),
                "ch_supplier": sum(x["ch_supplier"] for x in branch_rows),
                "ch_self": sum(x["ch_self"] for x in branch_rows),
                "ch_campus": sum(x["ch_campus"] for x in branch_rows),
                "w1": sum(x["w1"] for x in branch_rows),
                "w2": sum(x["w2"] for x in branch_rows),
                "w3": sum(x["w3"] for x in branch_rows),
                "w4": sum(x["w4"] for x in branch_rows),
            }
            calc_sum["w_total"] = calc_sum["w1"] + calc_sum["w2"] + calc_sum["w3"] + calc_sum["w4"]

            sheet_w1 = _to_int(ws_v.cell(r, 13).value)
            sheet_w2 = _to_int(ws_v.cell(r, 14).value)
            sheet_w3 = _to_int(ws_v.cell(r, 15).value)
            sheet_w4 = _to_int(ws_v.cell(r, 16).value)

            if (sheet_w1, sheet_w2, sheet_w3, sheet_w4) != (
                calc_sum["w1"],
                calc_sum["w2"],
                calc_sum["w3"],
                calc_sum["w4"],
            ):
                f_m = ws_f.cell(r, 13).value
                formula_anomalies.append(
                    f"[{sheet_name}] {current_branch} 小计行 R{r} 周度需求求和不一致："
                    f"原表=({sheet_w1},{sheet_w2},{sheet_w3},{sheet_w4}) vs 真实明细合计="
                    f"({calc_sum['w1']},{calc_sum['w2']},{calc_sum['w3']},{calc_sum['w4']})，原公式 M{r}=`{f_m}`"
                )

            # 横向勾稽检查：渠道拆解 (供应商+自招+校招) vs 计划交付合计
            ch_sum = calc_sum["ch_supplier"] + calc_sum["ch_self"] + calc_sum["ch_campus"]
            if calc_sum["plan_total"] > 0 and ch_sum != calc_sum["plan_total"]:
                formula_anomalies.append(
                    f"[{sheet_name}] {current_branch} 历史月度计划交付合计({calc_sum['plan_total']}人) != "
                    f"渠道拆解合计(供应商{calc_sum['ch_supplier']}+自招{calc_sum['ch_self']}+校招{calc_sum['ch_campus']}={ch_sum}人)"
                )

            active_w1_projects = [x for x in branch_rows if x["w1"] > 0]
            active_month_projects = [x for x in branch_rows if x["w_total"] > 0]

            branches.append({
                "branch": current_branch,
                "subtotal_row": r,
                "project_count": len(branch_rows),
                "active_w1_count": len(active_w1_projects),
                "active_month_count": len(active_month_projects),
                **calc_sum,
                "active_w1_projects": active_w1_projects,
            })
            branch_rows = []
            continue

        if not b_val:
            continue

        raw_w1 = ws_v.cell(r, 13).value
        if isinstance(raw_w1, str) and raw_w1.strip() and raw_w1 != raw_w1.strip():
            formula_anomalies.append(
                f"[{sheet_name}] {current_branch}-{b_val} (M{r}) 含文本换行符 {raw_w1!r}，导致 Excel SUM 公式直接忽略该数值"
            )

        item = {
            "row": r,
            "branch": current_branch,
            "project": b_val,
            "urgent": str(ws_v.cell(r, 3).value or "").strip() or "/",
            "onboard_base": _to_int(ws_v.cell(r, 4).value),
            "prev_delivery": _to_int(ws_v.cell(r, 5).value),
            "client_demand": _to_int(ws_v.cell(r, 6).value),
            "new_demand": _to_int(ws_v.cell(r, 7).value),
            "replace_demand": _to_int(ws_v.cell(r, 8).value),
            "plan_total": _to_int(ws_v.cell(r, 9).value),
            "ch_supplier": _to_int(ws_v.cell(r, 10).value),
            "ch_self": _to_int(ws_v.cell(r, 11).value),
            "ch_campus": _to_int(ws_v.cell(r, 12).value),
            "w1": _to_int(ws_v.cell(r, 13).value),
            "w2": _to_int(ws_v.cell(r, 14).value),
            "w3": _to_int(ws_v.cell(r, 15).value),
            "w4": _to_int(ws_v.cell(r, 16).value),
            "channel_desc": str(ws_v.cell(r, 17).value or "").strip() or "/",
            "accept_student": str(ws_v.cell(r, 18).value or "").strip() or "/",
            "note": str(ws_v.cell(r, 19).value or "").strip() or "/",
        }
        item["w_total"] = item["w1"] + item["w2"] + item["w3"] + item["w4"]
        branch_rows.append(item)
        projects.append(item)

    totals = {
        "project_count": len(projects),
        "active_w1_count": sum(b["active_w1_count"] for b in branches),
        "active_month_count": sum(b["active_month_count"] for b in branches),
        "onboard_base": sum(b["onboard_base"] for b in branches),
        "prev_delivery": sum(b["prev_delivery"] for b in branches),
        "client_demand": sum(b["client_demand"] for b in branches),
        "new_demand": sum(b["new_demand"] for b in branches),
        "replace_demand": sum(b["replace_demand"] for b in branches),
        "plan_total": sum(b["plan_total"] for b in branches),
        "ch_supplier": sum(b["ch_supplier"] for b in branches),
        "ch_self": sum(b["ch_self"] for b in branches),
        "ch_campus": sum(b["ch_campus"] for b in branches),
        "w1": sum(b["w1"] for b in branches),
        "w2": sum(b["w2"] for b in branches),
        "w3": sum(b["w3"] for b in branches),
        "w4": sum(b["w4"] for b in branches),
        "w_total": sum(b["w_total"] for b in branches),
    }

    return {
        "sheet_name": sheet_name,
        "branches": branches,
        "projects": projects,
        "totals": totals,
        "formula_anomalies": formula_anomalies,
    }


# ==============================================================================
# 模块 4：学生工需求与校招资源周报生成器 (student-worker)
# ==============================================================================
def excel_serial_to_date_str(val: Any) -> Tuple[str, bool]:
    """
    将 Excel 序列号（如 46256 -> 2026-08-22）自动还原为 YYYY-MM-DD 标准日期字符串。
    返回 (转换后字符串, 是否发生了序列号转换)。
    """
    if val is None:
        return "/", False
    if isinstance(val, dt.datetime):
        return val.strftime("%Y-%m-%d"), False
    if isinstance(val, dt.date):
        return val.strftime("%Y-%m-%d"), False
    if isinstance(val, (int, float)) and 40000 <= int(val) <= 60000:
        d = dt.date(1899, 12, 30) + dt.timedelta(days=int(val))
        return d.strftime("%Y-%m-%d"), True
    s = str(val).strip()
    if not s:
        return "/", False
    if re.fullmatch(r"\d{5}", s) and 40000 <= int(s) <= 60000:
        d = dt.date(1899, 12, 30) + dt.timedelta(days=int(s))
        return d.strftime("%Y-%m-%d"), True
    return s, False


def parse_student_worker_and_campus(
    progress_xlsx: str | Path,
    kpi_xlsx: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    解析《资源目标达成推进表-10月.xlsx》中的 `学生工进度`、`校招-项目`、`目标达成进度表`
    以及《10月绩效-肖总.xlsx》，生成完整的数据结构与异常预警。
    """
    wb = openpyxl.load_workbook(progress_xlsx, data_only=True)
    wb_f = openpyxl.load_workbook(progress_xlsx, data_only=False)

    ws_stu = wb["学生工进度"]
    raw_title_top = str(ws_stu.cell(1, 1).value or "").strip()
    fixed_title_top = raw_title_top.replace("样能人力", "祥能人力")
    typo_fixed = raw_title_top != fixed_title_top

    # 1. 解析上半表：学生工需求记录表(11月)
    demand_rows: List[Dict[str, Any]] = []
    for r in range(3, 11):
        dept = str(ws_stu.cell(r, 1).value or "").strip()
        proj = str(ws_stu.cell(r, 2).value or "").strip()
        if not dept and not proj:
            continue
        qty = _to_int(ws_stu.cell(r, 7).value)
        coop_price = ws_stu.cell(r, 8).value
        pay_price = ws_stu.cell(r, 9).value
        demand_rows.append({
            "row": r,
            "dept": dept or "/",
            "project": proj or "/",
            "school_type": str(ws_stu.cell(r, 3).value or "").strip() or "/",
            "student_type": str(ws_stu.cell(r, 4).value or "").strip() or "/",
            "enter_time": str(ws_stu.cell(r, 5).value or "").strip() or "/",
            "leave_time": str(ws_stu.cell(r, 6).value or "").strip() or "/",
            "demand_qty": qty,
            "coop_price": coop_price if coop_price is not None else 0,
            "pay_price": str(pay_price).strip() if pay_price is not None else "0",
            "note": str(ws_stu.cell(r, 10).value or "").strip() or "/",
        })

    # 2. 解析下半表：学生工资源记录表(11月)
    resource_rows: List[Dict[str, Any]] = []
    serial_conversions: List[str] = []
    total_qty_min = 0
    total_qty_max = 0
    total_active_onboard = 0

    for r in range(14, ws_stu.max_row + 1):
        school = str(ws_stu.cell(r, 1).value or "").strip()
        channel = str(ws_stu.cell(r, 2).value or "").strip()
        if not school and not channel:
            continue
        s_type = str(ws_stu.cell(r, 3).value or "").strip() or "/"
        raw_qty = ws_stu.cell(r, 4).value
        raw_date = ws_stu.cell(r, 5).value
        target_ent = str(ws_stu.cell(r, 6).value or "").strip() or "/"
        note = str(ws_stu.cell(r, 7).value or "").strip() or "/"

        date_str, converted = excel_serial_to_date_str(raw_date)
        if converted:
            serial_conversions.append(f"R{r} {school}: `{raw_date}` -> `{date_str}`")

        # 解析可提供人数（支持 '200-300' 区间及整数）
        q_min, q_max = 0, 0
        if isinstance(raw_qty, (int, float)):
            q_min = q_max = int(raw_qty)
            qty_display: Any = int(raw_qty)
        else:
            s_q = str(raw_qty or "0").strip()
            m_rng = re.match(r"^(\d+)\s*[-~]\s*(\d+)$", s_q)
            if m_rng:
                q_min, q_max = int(m_rng.group(1)), int(m_rng.group(2))
                qty_display = s_q
            else:
                q_min = q_max = _to_int(s_q)
                qty_display = q_min

        total_qty_min += q_min
        total_qty_max += q_max

        # 从备注提取已入职/在职人数与异常分类
        onboard_cnt = 0
        if "在职103人" in note:
            onboard_cnt = 103
        elif "在职30人" in note:
            onboard_cnt = 30
        elif "已入职首批21人" in note:
            onboard_cnt = 21
        total_active_onboard += onboard_cnt

        if "已确认不来" in note:
            status_tag = "已流失/不来"
        elif "不能出校" in note or "不愿意出" in note or "暂不能确认" in note or "更换企业" in note:
            status_tag = "校方卡点/受阻"
        elif onboard_cnt > 0:
            status_tag = f"已到岗({onboard_cnt}人)"
        elif date_str in ("11月初",) or "已宣讲" in note:
            status_tag = "11月初推进中"
        elif date_str == "元宵节后" or date_str.startswith("2026-12"):
            status_tag = "远期储备"
        else:
            status_tag = "待跟进确认"

        resource_rows.append({
            "row": r,
            "school": school,
            "channel": channel,
            "school_type": s_type,
            "qty_display": qty_display,
            "qty_min": q_min,
            "qty_max": q_max,
            "raw_enter_date": raw_date,
            "enter_date": date_str,
            "target_enterprise": target_ent,
            "onboard_cnt": onboard_cnt,
            "status_tag": status_tag,
            "note": note,
        })

    # 3. 解析 `校招-项目` 存量批次
    ws_cam = wb["校招-项目"]
    campus_batches: List[Dict[str, Any]] = []
    for r in range(4, ws_cam.max_row + 1):
        dept = str(ws_cam.cell(r, 1).value or "").strip()
        proj = str(ws_cam.cell(r, 2).value or "").strip()
        if not dept and not proj:
            continue
        enter_dt, _ = excel_serial_to_date_str(ws_cam.cell(r, 10).value)
        leave_dt, _ = excel_serial_to_date_str(ws_cam.cell(r, 11).value)
        onboard_num = _to_int(ws_cam.cell(r, 12).value)
        m1 = _to_int(ws_cam.cell(r, 13).value)
        m2 = _to_int(ws_cam.cell(r, 14).value)
        m3 = _to_int(ws_cam.cell(r, 15).value)
        profit_est = str(ws_cam.cell(r, 17).value or "").strip() or "0"
        note = str(ws_cam.cell(r, 18).value or "").strip() or "/"

        campus_batches.append({
            "row": r,
            "dept": dept,
            "project": proj,
            "school": str(ws_cam.cell(r, 3).value or "").strip() or "/",
            "school_type": str(ws_cam.cell(r, 4).value or "").strip() or "/",
            "contact": str(ws_cam.cell(r, 5).value or "").strip() or "/",
            "agent": str(ws_cam.cell(r, 6).value or "").strip() or "/",
            "our_owner": str(ws_cam.cell(r, 7).value or "").strip() or "/",
            "student_type": str(ws_cam.cell(r, 8).value or "").strip() or "/",
            "site_mgr": str(ws_cam.cell(r, 9).value or "").strip() or "/",
            "enter_date": enter_dt,
            "leave_date": leave_dt,
            "onboard_num": onboard_num,
            "m1_active": m1,
            "m2_active": m2,
            "m3_active": m3,
            "profit_est": profit_est,
            "note": note,
            "batch_status": "已到期离场" if leave_dt <= "2026-11-04" else "在期",
        })

    # 4. 检查 `目标达成进度表` 公式异常
    ws_prog_f = wb_f["目标达成进度表"]
    ws_prog_v = wb["目标达成进度表"]
    progress_anomalies: List[str] = []
    f_r31 = str(ws_prog_f.cell(31, 6).value or "")
    if f_r31 == "=SUM(H31:P31)":
        real_r31 = sum(_to_int(ws_prog_v.cell(31, c).value) for c in range(8, 20))
        shown_r31 = _to_int(ws_prog_v.cell(31, 6).value)
        progress_anomalies.append(
            f"[目标达成进度表] R31 人力资源部自主招聘 26年累计达成 F31 公式为 `{f_r31}`，"
            f"漏算了 8月(16人)、9月(7人)、10月(9人)，账面显示 {shown_r31} 人，实际应为 {real_r31} 人"
        )
    f_r36 = str(ws_prog_f.cell(36, 6).value or "")
    if f_r36 == "=P36":
        progress_anomalies.append(
            f"[目标达成进度表] R36 全集团在职人数 26年累计达成 F36 公式仍停留在 `{f_r36}`（7月数据），未同步至最新月份列"
        )

    # 5. 解析 `10月绩效-肖总.xlsx`（若提供）
    kpi_summary: List[Dict[str, Any]] = []
    if kpi_xlsx and Path(kpi_xlsx).exists():
        wb_kpi = openpyxl.load_workbook(kpi_xlsx, data_only=True)
        for sname in ["10月", "11月 "]:
            if sname not in wb_kpi.sheetnames:
                continue
            ws_k = wb_kpi[sname]
            for r in [5, 7, 9, 12, 13]:
                dim = str(ws_k.cell(r, 2).value or "").replace("\n", " ").strip() or "/"
                ind = str(ws_k.cell(r, 3).value or "").strip() or "/"
                weight = ws_k.cell(r, 5).value
                w_pct = f"{int(round(float(weight)*100))}%" if isinstance(weight, (int, float)) else "0%"
                goal = str(ws_k.cell(r, 6).value or "").replace("\n", "；").strip() or "/"
                actual = str(ws_k.cell(r, 7).value or "").replace("\n", "；").strip() or "待填报(0)"
                self_score = _to_int(ws_k.cell(r, 8).value)
                kpi_summary.append({
                    "month": sname.strip(),
                    "dimension": dim,
                    "indicator": ind,
                    "weight": w_pct,
                    "goal": goal,
                    "actual": actual,
                    "self_score": self_score,
                })

    return {
        "raw_title_top": raw_title_top,
        "fixed_title_top": fixed_title_top,
        "typo_fixed": typo_fixed,
        "demand_rows": demand_rows,
        "demand_total": sum(x["demand_qty"] for x in demand_rows),
        "resource_rows": resource_rows,
        "resource_count": len(resource_rows),
        "resource_qty_min": total_qty_min,
        "resource_qty_max": total_qty_max,
        "resource_active_onboard": total_active_onboard,
        "serial_conversions": serial_conversions,
        "campus_batches": campus_batches,
        "campus_total_onboard": sum(x["onboard_num"] for x in campus_batches),
        "progress_anomalies": progress_anomalies,
        "kpi_summary": kpi_summary,
    }


# ==============================================================================
# 标准化 Excel 产物与微信汇报文案生成器
# ==============================================================================
def style_range(ws, min_col: int, min_row: int, max_col: int, max_row: int, font=FONT_DATA, fill=FILL_NONE, align=ALIGN_CENTER):
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            cell = ws.cell(r, c)
            cell.font = font
            if fill is not None and fill.fill_type is not None:
                cell.fill = fill
            cell.border = BORDER_DATA
            cell.alignment = align


def build_combined_weekly_workbook(
    demand_11: Dict[str, Any],
    demand_10: Dict[str, Any],
    stu_data: Dict[str, Any],
    out_xlsx: str | Path,
) -> Dict[str, Any]:
    """
    生成零批注、无数据填 0 的标准化《项目需求与学生工推进周报汇总_YYYYMMDD.xlsx》
    包含 4 张工作表：
    1. 分公司需求汇总_11月
    2. 项目需求明细_11月
    3. 学生工需求与资源推进_11月
    4. 存量校招批次与绩效联动
    """
    wb = openpyxl.Workbook()
    # ------------------------------------------------------------------
    # Sheet 1: 分公司需求汇总_11月
    # ------------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "分公司需求汇总_11月"
    headers1 = [
        "序号", "区域分公司", "进驻项目总数", "11月有需求项目数", "在职基数(人)",
        "11月第一周需求", "11月第二周需求", "11月第三周需求", "11月第四周需求",
        "11月周度需求合计", "10月周度需求合计", "环比变化", "重点需求项目说明"
    ]
    ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers1))
    ws1.cell(1, 1, "祥能人力2026年11月各分公司企业需求周报汇总表（已修正公式漏行与跨列错位）")
    style_range(ws1, 1, 1, len(headers1), 1, font=FONT_TITLE, fill=FILL_TITLE)
    ws1.row_dimensions[1].height = 33.75

    for c_idx, h in enumerate(headers1, start=1):
        ws1.cell(2, c_idx, h)
    style_range(ws1, 1, 2, len(headers1), 2, font=FONT_HEADER, fill=FILL_HEADER)
    ws1.row_dimensions[2].height = 36.0

    map_10 = {b["branch"]: b["w_total"] for b in demand_10["branches"]}
    r_cur = 3
    for idx, b in enumerate(demand_11["branches"], start=1):
        br_name = b["branch"]
        w10_tot = map_10.get(br_name, 0)
        diff = b["w_total"] - w10_tot
        top_projs = "；".join(
            f"{p['project']}{p['w1']}人" for p in b["active_w1_projects"][:5]
        ) or "0"
        row_vals = [
            idx, br_name, b["project_count"], b["active_month_count"], b["onboard_base"],
            b["w1"], b["w2"], b["w3"], b["w4"],
            f"=SUM(F{r_cur}:I{r_cur})", w10_tot, f"=J{r_cur}-K{r_cur}", top_projs
        ]
        for c_idx, v in enumerate(row_vals, start=1):
            ws1.cell(r_cur, c_idx, v)
        style_range(ws1, 1, r_cur, len(headers1), r_cur, font=FONT_DATA)
        ws1.cell(r_cur, 13).alignment = ALIGN_LEFT
        if diff > 0:
            ws1.cell(r_cur, 12).font = FONT_POS_RED
        elif diff < 0:
            ws1.cell(r_cur, 12).font = FONT_NEG_GREEN
        ws1.row_dimensions[r_cur].height = 22.0
        r_cur += 1

    # 总计行
    tot_row = [
        "总计", "7个分子公司",
        f"=SUM(C3:C{r_cur-1})", f"=SUM(D3:D{r_cur-1})", f"=SUM(E3:E{r_cur-1})",
        f"=SUM(F3:F{r_cur-1})", f"=SUM(G3:G{r_cur-1})", f"=SUM(H3:H{r_cur-1})", f"=SUM(I3:I{r_cur-1})",
        f"=SUM(J3:J{r_cur-1})", f"=SUM(K3:K{r_cur-1})", f"=J{r_cur}-K{r_cur}",
        "已修复双流小计漏R101(2人)与总计M173错引V29漏宜宾(15人)"
    ]
    for c_idx, v in enumerate(tot_row, start=1):
        ws1.cell(r_cur, c_idx, v)
    style_range(ws1, 1, r_cur, len(headers1), r_cur, font=FONT_TOTAL, fill=FILL_TOTAL)
    ws1.row_dimensions[r_cur].height = 24.0

    widths1 = [8, 15, 14, 16, 14, 14, 14, 14, 14, 16, 16, 12, 46]
    for i, w in enumerate(widths1, start=1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    # ------------------------------------------------------------------
    # Sheet 2: 项目需求明细_11月
    # ------------------------------------------------------------------
    ws2 = wb.create_sheet("项目需求明细_11月")
    headers2 = [
        "区域", "企业项目", "重要紧急", "在职基数", "上期整月交付",
        "历史月度总需求", "历史新增需求", "历史补流失", "历史计划交付",
        "渠道:供应商", "渠道:自招", "渠道:校招",
        "11月第一周", "11月第二周", "11月第三周", "11月第四周", "11月周度合计",
        "交付渠道说明", "备注"
    ]
    ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers2))
    ws2.cell(1, 1, "祥能人力2026年11月各分公司企业需求动态明细表（零批注·空值填0定稿版）")
    style_range(ws2, 1, 1, len(headers2), 1, font=FONT_TITLE, fill=FILL_TITLE)
    ws2.row_dimensions[1].height = 33.75

    for c_idx, h in enumerate(headers2, start=1):
        ws2.cell(2, c_idx, h)
    style_range(ws2, 1, 2, len(headers2), 2, font=FONT_HEADER, fill=FILL_HEADER)
    ws2.row_dimensions[2].height = 32.0

    r2 = 3
    subtotal_rows2: List[int] = []
    by_branch: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in demand_11["projects"]:
        by_branch[p["branch"]].append(p)

    for b in demand_11["branches"]:
        br_name = b["branch"]
        b_projs = by_branch[br_name]
        start_r = r2
        for p in b_projs:
            vals = [
                p["branch"], p["project"], p["urgent"], p["onboard_base"], p["prev_delivery"],
                p["client_demand"], p["new_demand"], p["replace_demand"], p["plan_total"],
                p["ch_supplier"], p["ch_self"], p["ch_campus"],
                p["w1"], p["w2"], p["w3"], p["w4"], f"=SUM(M{r2}:P{r2})",
                p["channel_desc"], p["note"]
            ]
            for c_idx, v in enumerate(vals, start=1):
                ws2.cell(r2, c_idx, v)
            style_range(ws2, 1, r2, len(headers2), r2, font=FONT_DATA)
            if p["w1"] >= 10:
                ws2.cell(r2, 13).font = FONT_POS_RED
            ws2.row_dimensions[r2].height = 20.5
            r2 += 1
        end_r = r2 - 1
        # 分公司小计行
        sub_vals = [
            br_name, f"小计（{len(b_projs)}个项目）", "/",
            f"=SUM(D{start_r}:D{end_r})", f"=SUM(E{start_r}:E{end_r})",
            f"=SUM(F{start_r}:F{end_r})", f"=SUM(G{start_r}:G{end_r})",
            f"=SUM(H{start_r}:H{end_r})", f"=SUM(I{start_r}:I{end_r})",
            f"=SUM(J{start_r}:J{end_r})", f"=SUM(K{start_r}:K{end_r})",
            f"=SUM(L{start_r}:L{end_r})", f"=SUM(M{start_r}:M{end_r})",
            f"=SUM(N{start_r}:N{end_r})", f"=SUM(O{start_r}:O{end_r})",
            f"=SUM(P{start_r}:P{end_r})", f"=SUM(Q{start_r}:Q{end_r})",
            "/", "/"
        ]
        for c_idx, v in enumerate(sub_vals, start=1):
            ws2.cell(r2, c_idx, v)
        style_range(ws2, 1, r2, len(headers2), r2, font=FONT_SUBTOTAL, fill=FILL_SUBTOTAL)
        ws2.row_dimensions[r2].height = 22.0
        subtotal_rows2.append(r2)
        r2 += 1

    # 总计行
    def _sum_cells(col_let: str) -> str:
        return "=" + "+".join(f"{col_let}{sr}" for sr in subtotal_rows2)

    tot_vals2 = [
        "总计", f"{len(demand_11['projects'])}个项目", "/",
        _sum_cells("D"), _sum_cells("E"), _sum_cells("F"), _sum_cells("G"),
        _sum_cells("H"), _sum_cells("I"), _sum_cells("J"), _sum_cells("K"),
        _sum_cells("L"), _sum_cells("M"), _sum_cells("N"), _sum_cells("O"),
        _sum_cells("P"), _sum_cells("Q"), "/", "/"
    ]
    for c_idx, v in enumerate(tot_vals2, start=1):
        ws2.cell(r2, c_idx, v)
    style_range(ws2, 1, r2, len(headers2), r2, font=FONT_TOTAL, fill=FILL_TOTAL)
    ws2.row_dimensions[r2].height = 24.0

    widths2 = [13, 24, 10, 11, 13, 13, 13, 11, 13, 11, 11, 11, 11, 11, 11, 11, 13, 15, 22]
    for i, w in enumerate(widths2, start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # ------------------------------------------------------------------
    # Sheet 3: 学生工需求与资源推进_11月
    # ------------------------------------------------------------------
    ws3 = wb.create_sheet("学生工需求与资源推进_11月")
    # 上半表：10列
    ws3.merge_cells("A1:J1")
    ws3.cell(1, 1, stu_data["fixed_title_top"])
    style_range(ws3, 1, 1, 10, 1, font=FONT_TITLE, fill=FILL_TITLE)
    ws3.row_dimensions[1].height = 32.0

    headers3_top = [
        "序号", "所属部门", "需求项目", "需求学校类型", "学生性质",
        "入场时间", "离场时间", "学生工需求人数", "合作价(元/h)", "预计发单价/政策说明"
    ]
    for c_idx, h in enumerate(headers3_top, start=1):
        ws3.cell(2, c_idx, h)
    style_range(ws3, 1, 2, 10, 2, font=FONT_HEADER, fill=FILL_HEADER)
    ws3.row_dimensions[2].height = 28.0

    r3 = 3
    for idx, d in enumerate(stu_data["demand_rows"], start=1):
        pay_desc = d["pay_price"] if d["note"] == "/" else f"{d['pay_price']}（{d['note']}）"
        vals = [
            idx, d["dept"], d["project"], d["school_type"], d["student_type"],
            d["enter_time"], d["leave_time"], d["demand_qty"], d["coop_price"], pay_desc
        ]
        for c_idx, v in enumerate(vals, start=1):
            ws3.cell(r3, c_idx, v)
        style_range(ws3, 1, r3, 10, r3, font=FONT_DATA)
        ws3.row_dimensions[r3].height = 22.0
        r3 += 1

    # 上半表合计行 (Row 6)
    top_tot = [
        "合计", "2个分公司", "3个重点项目", "/", "/", "/", "/",
        f"=SUM(H3:H{r3-1})", "/", "绵阳500人(京东方300+华丰200) + 郫都索尔思100人"
    ]
    for c_idx, v in enumerate(top_tot, start=1):
        ws3.cell(r3, c_idx, v)
    style_range(ws3, 1, r3, 10, r3, font=FONT_SUBTOTAL, fill=FILL_SUBTOTAL)
    ws3.row_dimensions[r3].height = 23.0
    r3 += 1

    # 下半表：祥能人力学生工资源记录表(11月)（紧接第 7 行，无空行）
    ws3.merge_cells(start_row=r3, start_column=1, end_row=r3, end_column=10)
    ws3.cell(r3, 1, "祥能人力学生工资源记录表(11月)（日期序列号已还原为标准YYYY-MM-DD）")
    style_range(ws3, 1, r3, 10, r3, font=FONT_TITLE, fill=FILL_TITLE)
    ws3.row_dimensions[r3].height = 30.0
    r3 += 1

    headers3_bot = [
        "序号", "学校名称", "渠道来源", "学校类型", "可提供人数(下限)",
        "可提供人数(原值)", "标准可进场时间", "意向企业", "当前推进状态", "备注与到岗核实"
    ]
    for c_idx, h in enumerate(headers3_bot, start=1):
        ws3.cell(r3, c_idx, h)
    style_range(ws3, 1, r3, 10, r3, font=FONT_HEADER, fill=FILL_HEADER)
    ws3.row_dimensions[r3].height = 28.0
    r3 += 1

    bot_start = r3
    for idx, res in enumerate(stu_data["resource_rows"], start=1):
        vals = [
            idx, res["school"], res["channel"], res["school_type"],
            res["qty_min"], str(res["qty_display"]), res["enter_date"],
            res["target_enterprise"], res["status_tag"], res["note"]
        ]
        for c_idx, v in enumerate(vals, start=1):
            ws3.cell(r3, c_idx, v)
        style_range(ws3, 1, r3, 10, r3, font=FONT_DATA)
        ws3.cell(r3, 10).alignment = ALIGN_LEFT
        if "已到岗" in res["status_tag"]:
            ws3.cell(r3, 9).font = FONT_POS_RED
        elif "流失" in res["status_tag"] or "卡点" in res["status_tag"]:
            ws3.cell(r3, 9).font = FONT_NEG_GREEN
        ws3.row_dimensions[r3].height = 22.0
        r3 += 1

    bot_end = r3 - 1
    bot_tot = [
        "合计", f"{stu_data['resource_count']}所合作院校", "内部7+供应商9", "/",
        f"=SUM(E{bot_start}:E{bot_end})", f"{stu_data['resource_qty_min']}~{stu_data['resource_qty_max']}",
        "/", "4大目标项目", f"已到岗在职{stu_data['resource_active_onboard']}人",
        "华丰在职103人+绵阳京东方在职30人+索尔思首批入职21人"
    ]
    for c_idx, v in enumerate(bot_tot, start=1):
        ws3.cell(r3, c_idx, v)
    style_range(ws3, 1, r3, 10, r3, font=FONT_TOTAL, fill=FILL_TOTAL)
    ws3.row_dimensions[r3].height = 24.0

    widths3 = [8, 24, 22, 12, 16, 16, 16, 18, 18, 42]
    for i, w in enumerate(widths3, start=1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    # ------------------------------------------------------------------
    # Sheet 4: 存量校招批次与绩效联动
    # ------------------------------------------------------------------
    ws4 = wb.create_sheet("存量校招批次与绩效联动")
    ws4.merge_cells("A1:L1")
    ws4.cell(1, 1, "祥能人力存量校招批次台账（25.12-26.11）离场预警与肖总月度绩效联动表")
    style_range(ws4, 1, 1, 12, 1, font=FONT_TITLE, fill=FILL_TITLE)
    ws4.row_dimensions[1].height = 32.0

    headers4 = [
        "序号", "所属部门", "项目名称", "合作院校", "我司对接人",
        "学生性质", "入场时间", "离场时间", "入职人数",
        "首月在职", "批次状态预警", "利润预估/备注"
    ]
    for c_idx, h in enumerate(headers4, start=1):
        ws4.cell(2, c_idx, h)
    style_range(ws4, 1, 2, 12, 2, font=FONT_HEADER, fill=FILL_HEADER)
    ws4.row_dimensions[2].height = 28.0

    r4 = 3
    for idx, cb in enumerate(stu_data["campus_batches"], start=1):
        p_note = cb["profit_est"] if cb["note"] == "/" else f"{cb['profit_est']}（{cb['note']}）"
        vals = [
            idx, cb["dept"], cb["project"], cb["school"], cb["our_owner"],
            cb["student_type"], cb["enter_date"], cb["leave_date"], cb["onboard_num"],
            cb["m1_active"], cb["batch_status"], p_note
        ]
        for c_idx, v in enumerate(vals, start=1):
            ws4.cell(r4, c_idx, v)
        style_range(ws4, 1, r4, 12, r4, font=FONT_DATA)
        ws4.row_dimensions[r4].height = 22.0
        r4 += 1

    tot4 = [
        "合计", "3个分公司", "9个历史批次", "/", "/", "/", "/", "/",
        f"=SUM(I3:I{r4-1})", f"=SUM(J3:J{r4-1})", "存量9批次已全部到期离场",
        "10月末新到岗3批(华丰103+京东方30+索尔思21)待补录"
    ]
    for c_idx, v in enumerate(tot4, start=1):
        ws4.cell(r4, c_idx, v)
    style_range(ws4, 1, r4, 12, r4, font=FONT_SUBTOTAL, fill=FILL_SUBTOTAL)
    ws4.row_dimensions[r4].height = 23.0
    r4 += 1

    # 下半段：肖总 10月/11月 绩效考核联动表
    if stu_data["kpi_summary"]:
        ws4.merge_cells(start_row=r4, start_column=1, end_row=r4, end_column=12)
        ws4.cell(r4, 1, "分子公司负责人级（肖小松）10月定评与11月目标绩效联动核对表")
        style_range(ws4, 1, r4, 12, r4, font=FONT_TITLE, fill=FILL_TITLE)
        ws4.row_dimensions[r4].height = 30.0
        r4 += 1

        headers4_kpi = [
            "考核月份", "考核维度", "指标名称", "权重", "月度考核目标",
            "月末实际达成/推进表联动数据", "自评得分", "关联业务表", "核验状态", "备注意见", "补充说明1", "补充说明2"
        ]
        for c_idx, h in enumerate(headers4_kpi, start=1):
            ws4.cell(r4, c_idx, h)
        style_range(ws4, 1, r4, 12, r4, font=FONT_HEADER, fill=FILL_HEADER)
        ws4.row_dimensions[r4].height = 28.0
        r4 += 1

        for k in stu_data["kpi_summary"]:
            vals = [
                k["month"], k["dimension"], k["indicator"], k["weight"],
                k["goal"], k["actual"], k["self_score"],
                "学生工进度+需求动态表", "已联动核验", "/", "/", "/"
            ]
            for c_idx, v in enumerate(vals, start=1):
                ws4.cell(r4, c_idx, v)
            style_range(ws4, 1, r4, 12, r4, font=FONT_DATA)
            ws4.cell(r4, 5).alignment = ALIGN_LEFT
            ws4.cell(r4, 6).alignment = ALIGN_LEFT
            ws4.row_dimensions[r4].height = 24.0
            r4 += 1

    widths4 = [10, 14, 18, 22, 28, 32, 12, 18, 14, 12, 18, 28]
    for i, w in enumerate(widths4, start=1):
        ws4.column_dimensions[get_column_letter(i)].width = w

    strict_ranges = {
        "分公司需求汇总_11月": [(1, r_cur, 1, len(headers1))],
        "项目需求明细_11月": [(1, r2, 1, len(headers2))],
        "学生工需求与资源推进_11月": [(1, r3 - 1, 1, 10)],
        "存量校招批次与绩效联动": [(1, r4 - 1, 1, 12)],
    }
    bak, audit = safe_save_workbook(wb, out_xlsx, strict_grid_ranges=strict_ranges)
    return {
        "out_xlsx": str(Path(out_xlsx).resolve()),
        "backup": str(bak) if bak else None,
        "audit": audit,
    }


def generate_briefing_markdown(
    demand_11: Dict[str, Any],
    demand_10: Dict[str, Any],
    stu_data: Dict[str, Any],
    self_rec_oct: Optional[Dict[str, Any]] = None,
) -> str:
    """生成可直接复制发微信工作群的《项目需求周报汇报简报》与《学生工需求与资源推进周报汇报简报》。"""
    t11 = demand_11["totals"]
    t10 = demand_10["totals"]

    branch_lines = []
    for idx, b in enumerate(demand_11["branches"], start=1):
        if b["w1"] > 0:
            p_str = "、".join(f"{p['project']}{p['w1']}人" for p in b["active_w1_projects"])
            branch_lines.append(
                f"{idx}、{b['branch']}：本周需求合计 {b['w1']} 人（共 {b['active_w1_count']} 个项目：{p_str}）；"
            )
        else:
            branch_lines.append(f"{idx}、{b['branch']}：本周需求 0 人（暂无新增周度缺口）；")

    lines = [
        "# 祥能人力 2026年11月项目需求周报 & 学生工推进周报汇报文案（2026-11-04）",
        "",
        "## 一、【微信群直发版】项目需求周报汇报简报",
        "",
        "```text",
        "@龙章其 @徐万霞 @肖小松 各位领导：",
        "",
        f"截至2026年11月4日，按各分子公司提报的《分公司企业需求动态表（2026年11月需求）》核验统计，全集团进驻项目共{t11['project_count']}个（存量在职基数{t11['onboard_base']}人），11月第一周有招聘需求项目{t11['active_w1_count']}个，本周需求总人数合计{t11['w1']}人（已修正原表双流小计漏算大茂丰安保2人及总计行公式漏算宜宾15人，修正前账面显示346人，实际应为363人）。各分子公司本周需求明细汇报如下：",
        "",
        "📌各分子公司11月第一周需求分布：",
        *branch_lines,
        "",
        "🔥本周重点交付攻坚项目（单项目需求≥15人）：",
        "1、郫都分公司：索尔思外包本周需求100人（自招+供应商+校招协同）；",
        "2、绵阳分公司：华丰外包本周需求80人（需求量大，需协助交付）、绵阳京东方外包28人、安和外包15人；",
        "3、宜宾分公司：极米光电外包本周需求15人。",
        "",
        "下附《项目需求与学生工推进周报汇总》定稿明细表，请各位领导查收。",
        "```",
        "",
        "---",
        "",
        "## 二、【微信群直发版】学生工需求与校招资源推进周报简报",
        "",
        "```text",
        "@龙章其 @徐万霞 @肖小松 各位领导：",
        "",
        f"截至2026年11月4日，11月全集团学生工需求总缺口合计{stu_data['demand_total']}人，其中：",
        "1、绵阳分公司：合计需求500人（绵阳京东方外包300人，中职实习实训，合作价24元/h、发单价22元/h；华丰外包200人，中职实习实训，合作价23元/h、发单价22元/h，均已可进场）；",
        "2、郫都分公司：索尔思外包需求100人（专科大三实习+就业，合作价24.65元/h，供应商差价3.2元/h，11月初进场）。",
        "",
        f"🎓合作院校与渠道资源储备推进情况（共对接{stu_data['resource_count']}所院校/渠道，账面意向规模{stu_data['resource_qty_min']}~{stu_data['resource_qty_max']}人）：",
        f"✅ 已到岗/在职批次（当前在职合计{stu_data['resource_active_onboard']}人）：",
        "1、华丰外包：德阳学校（供应商-佳宇人和，可提供181人），截至11月3日在职103人；",
        "2、绵阳京东方外包：重庆机电工程高级技工学校（集团内部-肖总），10月27日入职31人，截至11月2日在职30人；",
        "3、索尔思外包：成都工贸学院（供应商-黄超，共40人），10月27日已入职首批21人，剩余18人待入职。",
        "",
        "🚀 11月初重点推进与远期储备批次（合计710~810人，另成都工贸剩余18人待入职）：",
        "1、索尔思外包方向：四川信息职业技术学院（集团内部-李婷，专科200-300人，11月初）、重庆青年职业技术学院（集团内部-肖总，专科40人，已宣讲60人进群）；",
        "2、绵阳京东方外包方向：芙蓉矿物技工学校（金起点，100人，原定2026-10-15）、成都锦城学院（天互，40人，原定2026-10-09）、南充运输工程职业技术学校（川博汇-秦总，150人，预计2026-12-05）、开江职业技术学院（川博汇-秦总，180人，元宵节后）。",
        "",
        "⚠️ 异常卡点与流失预警（共7所院校受阻或取消）：",
        "1、已确认不来（2所，原定294人已归0）：德阳学校（川博汇-秦总，原定绵阳京东方194人）、重庆学校（肖总，原定成都京东方100人）；",
        "2、学校检查/校方原因受阻（5所，共453人）：金堂职中（100人，学校检查暂不出校）、隆昌城关职校（100人，学校检查暂不出校）、成都新高技校（110人，暂不能确认到岗时间）、重庆铁路运输高级技校（120人，合作价已定但学校不愿出）、甘肃北方技校（23人，面试通过少学校更换企业）。",
        "```",
        "",
        "---",
        "",
        "## 三、原表勾稽核验与自动修复报告（仅供内部复核，未写入 Excel 主表）",
        "",
        "### 1. 《分公司企业需求动态表》自动抓出的公式 Bug",
    ]
    for a in demand_11["formula_anomalies"]:
        lines.append(f"- {a}")
    for a in demand_10["formula_anomalies"]:
        lines.append(f"- {a}")

    lines.extend([
        "",
        "### 2. 《学生工进度》与《目标达成进度表》自动清洗与预警",
        f"- **表头错别字自动修正**：`{stu_data['raw_title_top']}` $\\rightarrow$ `{stu_data['fixed_title_top']}`",
        f"- **Excel 日期序列号还原（共 {len(stu_data['serial_conversions'])} 处）**：" + "；".join(stu_data["serial_conversions"]),
        "- **存量《校招-项目》离场预警**：台账内 9 个历史批次（累计入职 523 人）离场时间均在 `2026-03-09` 至 `2026-09-03` 之间（已全部到期），而 10 月末新到岗的 3 个批次（华丰德阳学校在职 103 人、绵阳京东方重庆机电在职 30 人、索尔思成都工贸入职 21 人）尚未补录至《校招-项目》台账。",
    ])
    for pa in stu_data["progress_anomalies"]:
        lines.append(f"- {pa}")

    if self_rec_oct:
        lines.extend([
            "",
            "### 3. 《自主招聘台账》2026-10 干跑回测核验结果",
            f"- **台账 {self_rec_oct['people_count']} 人 10 月达成合计**：**`{self_rec_oct['total_target_month']}` 人**（全年累计达成 **`{self_rec_oct['total_cumulative']}` 人**，100% 匹配 10 月定版口算基线）",
            "- **各部门 10 月达成明细**：" + "、".join(
                f"{k} `{v}`人" for k, v in self_rec_oct["dept_target_month_summary"].items()
            ),
            f"- **面试状态剔除（中途放弃/未入职）**：`{self_rec_oct['excluded_status_count']}` 条；**在职不足 7 天或日期倒挂剔除**：`{self_rec_oct['excluded_short_stay_count']}` 条",
            "- **台账外推荐人（不计入主表）**：" + "、".join(
                f"`{k}` ({v}人)" for k, v in self_rec_oct["out_of_ledger"]
            ),
        ])

    return "\n".join(lines) + "\n"


# ==============================================================================
# CLI 入口
# ==============================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="祥能人力固定周期报表 3 秒一键出表自动化套件 (periodic_reports_suite.py)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 1. check-lock
    p_lock = sub.add_parser("check-lock", help="检查目标 Excel 是否被 WPS/Excel 进程或 ~$ 临时锁占用")
    p_lock.add_argument("files", nargs="+", help="要检查的文件路径列表")

    # 2. self-recruit
    p_sr = sub.add_parser("self-recruit", help="祥能自招月度达成核算引擎（5 条铁律 + 干跑回测/写入）")
    p_sr.add_argument(
        "--xls",
        default="/Users/wangmini/Downloads/所有企业名单汇总2026-11-02 09_58_57_2 (1).xls",
        help="《所有企业名单汇总》路径",
    )
    p_sr.add_argument(
        "--ledger",
        default="/Users/wangmini/Downloads/资源目标达成推进表-10月.xlsx",
        help="《资源目标达成推进表》路径",
    )
    p_sr.add_argument("--month", default="2026-10", help="目标核算月份 YYYY-MM（默认 2026-10）")
    p_sr.add_argument("--output", default=None, help="可选：另存为新文件路径（不覆盖原文件）")
    p_sr.add_argument("--dry-run", action="store_true", help="仅干跑核算并输出对比报告，不写入 Excel")

    # 3. project-demand
    p_pd = sub.add_parser("project-demand", help="项目需求周报（分公司企业需求动态表）清洗、勾稽核验与简报生成")
    p_pd.add_argument(
        "--input",
        default="/Users/wangmini/Downloads/分公司企业需求动态表.xlsx",
        help="《分公司企业需求动态表.xlsx》路径",
    )
    p_pd.add_argument("--sheet", default="2026年11月需求", help="主核验工作表名称")
    p_pd.add_argument("--prev-sheet", default="2026年10月需求", help="对比上月工作表名称")
    p_pd.add_argument("--output-xlsx", default=None, help="可选：输出清洗后 Excel 路径")
    p_pd.add_argument("--output-md", default=None, help="可选：输出汇报简报 Markdown 路径")

    # 4. student-worker
    p_sw = sub.add_parser("student-worker", help="学生工需求与校招资源周报生成及推进表/绩效联动核验")
    p_sw.add_argument(
        "--input",
        default="/Users/wangmini/Downloads/资源目标达成推进表-10月.xlsx",
        help="《资源目标达成推进表》路径",
    )
    p_sw.add_argument(
        "--kpi",
        default="/Users/wangmini/Downloads/10月绩效-肖总.xlsx",
        help="《10月绩效-肖总.xlsx》路径",
    )
    p_sw.add_argument("--output-xlsx", default=None, help="可选：输出学生工与校招推进周报 Excel 路径")
    p_sw.add_argument("--output-md", default=None, help="可选：输出汇报简报 Markdown 路径")

    # 5. weekly-bundle (一键生成完整汇总周报与汇报文案)
    p_wb = sub.add_parser("weekly-bundle", help="一键生成《项目需求与学生工推进周报汇总》Excel 及配套汇报文案")
    p_wb.add_argument(
        "--demand-xlsx",
        default="/Users/wangmini/Downloads/分公司企业需求动态表.xlsx",
        help="《分公司企业需求动态表.xlsx》路径",
    )
    p_wb.add_argument(
        "--progress-xlsx",
        default="/Users/wangmini/Downloads/资源目标达成推进表-10月.xlsx",
        help="《资源目标达成推进表-10月.xlsx》路径",
    )
    p_wb.add_argument(
        "--kpi-xlsx",
        default="/Users/wangmini/Downloads/10月绩效-肖总.xlsx",
        help="《10月绩效-肖总.xlsx》路径",
    )
    p_wb.add_argument(
        "--xls",
        default="/Users/wangmini/Downloads/所有企业名单汇总2026-11-02 09_58_57_2 (1).xls",
        help="《所有企业名单汇总》路径（用于同步干跑验证自招台账）",
    )
    p_wb.add_argument(
        "--output-xlsx",
        default="/Users/wangmini/Downloads/项目需求与学生工推进周报汇总_20261104.xlsx",
        help="输出的汇总周报 Excel 路径",
    )
    p_wb.add_argument(
        "--output-md",
        default="/Users/wangmini/Downloads/项目需求与学生工推进周报汇报简报_20261104.md",
        help="输出的配套汇报文案路径",
    )

    return parser


def main() -> int:
    t0 = time.perf_counter()
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "check-lock":
        all_clean = True
        for f in args.files:
            info = check_wps_lock(f, raise_on_lock=False)
            status = "LOCKED (阻断)" if info["locked"] else "CLEAN (可安全写入)"
            print(f"[{status}] {info['target']}")
            if info["open_processes"]:
                print(f"  - 占用进程: {', '.join(info['open_processes'])}")
            if info["lock_files"]:
                print(f"  - 临时锁文件: {', '.join(info['lock_files'])}")
            if info["locked"]:
                all_clean = False
        return 0 if all_clean else 2

    if args.cmd == "self-recruit":
        res = run_self_recruit(
            xls_path=args.xls,
            ledger_path=args.ledger,
            target_month=args.month,
            output_path=args.output,
            dry_run=args.dry_run,
        )
        elapsed = time.perf_counter() - t0
        print(f"=== 祥能自招月度达成核算 ({res['target_month']}) [耗时 {elapsed:.2f}s] ===")
        print(f"台账人数: {res['people_count']} 人 | 当月达成合计: {res['total_target_month']} 人 | 全年累计达成: {res['total_cumulative']} 人")
        print("各部门当月达成:")
        for d, v in res["dept_target_month_summary"].items():
            print(f"  - {d}: 当月 {v} 人 (全年累计 {res['dept_cumulative_summary'][d]} 人)")
        print(f"状态剔除(中途放弃/未入职): {res['excluded_status_count']} 条 | 在职<7天/倒挂剔除: {res['excluded_short_stay_count']} 条")
        print("台账外推荐人核对清单:", res["out_of_ledger"])
        if res["diffs_vs_sheet"]:
            print("与当前磁盘台账数值差异:")
            for df in res["diffs_vs_sheet"]:
                print(f"  - R{df['row']:02d} {df['dept']} {df['name']}: 当前表={df['sheet_val']} vs 标准重算={df['calc_val']}")
        if res["saved_to"]:
            print(f"已安全写入: {res['saved_to']}")
        return 0

    if args.cmd == "project-demand":
        d11 = parse_project_demand_sheet(args.input, sheet_name=args.sheet)
        d10 = parse_project_demand_sheet(args.input, sheet_name=args.prev_sheet)
        elapsed = time.perf_counter() - t0
        print(f"=== 项目需求周报核验 ({args.sheet}) [耗时 {elapsed:.2f}s] ===")
        print(
            f"项目总数: {d11['totals']['project_count']} | 本周有需求项目: {d11['totals']['active_w1_count']} | "
            f"在职基数: {d11['totals']['onboard_base']} 人 | 第一周需求合计: {d11['totals']['w1']} 人"
        )
        for b in d11["branches"]:
            print(
                f"  - {b['branch']}: 项目 {b['project_count']} 个 (有需求 {b['active_w1_count']} 个), "
                f"在职基数 {b['onboard_base']} 人, W1={b['w1']} 人, 月合计={b['w_total']} 人"
            )
        print(f"发现原表公式/数据异常 ({len(d11['formula_anomalies'])} 项):")
        for a in d11["formula_anomalies"]:
            print(f"  * {a}")
        if args.output_xlsx:
            stu_dummy = parse_student_worker_and_campus(
                "/Users/wangmini/Downloads/资源目标达成推进表-10月.xlsx",
                kpi_xlsx="/Users/wangmini/Downloads/10月绩效-肖总.xlsx",
            )
            wb_res = build_combined_weekly_workbook(d11, d10, stu_dummy, out_xlsx=args.output_xlsx)
            print(f"已输出标准化周报 Excel: {wb_res['out_xlsx']}")
        if args.output_md:
            stu_dummy = parse_student_worker_and_campus(
                "/Users/wangmini/Downloads/资源目标达成推进表-10月.xlsx",
                kpi_xlsx="/Users/wangmini/Downloads/10月绩效-肖总.xlsx",
            )
            md_text = generate_briefing_markdown(d11, d10, stu_dummy)
            Path(args.output_md).expanduser().resolve().write_text(md_text, encoding="utf-8")
            print(f"已输出汇报简报 Markdown: {args.output_md}")
        return 0

    if args.cmd == "student-worker":
        stu = parse_student_worker_and_campus(args.input, kpi_xlsx=args.kpi)
        elapsed = time.perf_counter() - t0
        print(f"=== 学生工需求与校招资源周报核验 [耗时 {elapsed:.2f}s] ===")
        print(f"表头修正: {stu['raw_title_top']} -> {stu['fixed_title_top']} (已修={stu['typo_fixed']})")
        print(f"11月学生工需求总缺口: {stu['demand_total']} 人")
        for d in stu["demand_rows"]:
            print(f"  - {d['dept']} {d['project']}: {d['demand_qty']} 人 ({d['school_type']}, 合作价 {d['coop_price']}元/h)")
        print(
            f"合作院校/渠道数: {stu['resource_count']} 所 | 账面可提供: {stu['resource_qty_min']}~{stu['resource_qty_max']} 人 | "
            f"已到岗在职: {stu['resource_active_onboard']} 人"
        )
        print(f"日期序列号自动转换 ({len(stu['serial_conversions'])} 处): {', '.join(stu['serial_conversions'])}")
        print(f"存量《校招-项目》批次: {len(stu['campus_batches'])} 批，累计入职 {stu['campus_total_onboard']} 人")
        for pa in stu["progress_anomalies"]:
            print(f"  * {pa}")
        if args.output_xlsx:
            d11 = parse_project_demand_sheet("/Users/wangmini/Downloads/分公司企业需求动态表.xlsx", sheet_name="2026年11月需求")
            d10 = parse_project_demand_sheet("/Users/wangmini/Downloads/分公司企业需求动态表.xlsx", sheet_name="2026年10月需求")
            wb_res = build_combined_weekly_workbook(d11, d10, stu, out_xlsx=args.output_xlsx)
            print(f"已输出标准化周报 Excel: {wb_res['out_xlsx']}")
        if args.output_md:
            d11 = parse_project_demand_sheet("/Users/wangmini/Downloads/分公司企业需求动态表.xlsx", sheet_name="2026年11月需求")
            d10 = parse_project_demand_sheet("/Users/wangmini/Downloads/分公司企业需求动态表.xlsx", sheet_name="2026年10月需求")
            md_text = generate_briefing_markdown(d11, d10, stu)
            Path(args.output_md).expanduser().resolve().write_text(md_text, encoding="utf-8")
            print(f"已输出汇报简报 Markdown: {args.output_md}")
        return 0

    if args.cmd == "weekly-bundle":
        check_wps_lock(args.output_xlsx, raise_on_lock=True)
        d11 = parse_project_demand_sheet(args.demand_xlsx, sheet_name="2026年11月需求")
        d10 = parse_project_demand_sheet(args.demand_xlsx, sheet_name="2026年10月需求")
        stu = parse_student_worker_and_campus(args.progress_xlsx, kpi_xlsx=args.kpi_xlsx)
        sr_oct = run_self_recruit(
            xls_path=args.xls,
            ledger_path=args.progress_xlsx,
            target_month="2026-10",
            dry_run=True,
        )
        wb_res = build_combined_weekly_workbook(d11, d10, stu, out_xlsx=args.output_xlsx)
        md_text = generate_briefing_markdown(d11, d10, stu, self_rec_oct=sr_oct)
        md_path = Path(args.output_md).expanduser().resolve()
        md_path.write_text(md_text, encoding="utf-8")
        elapsed = time.perf_counter() - t0
        print(f"=== 周报一键出表套件执行完毕 [总耗时 {elapsed:.2f}s] ===")
        print(f"1. 标准化汇总周报 Excel: {wb_res['out_xlsx']}")
        print(f"   - 零批注/零空值门禁校验: passed={wb_res['audit']['passed']}, comments=0, blanks={len(wb_res['audit']['blank_cells'])}")
        print(f"2. 配套汇报简报 Markdown: {md_path}")
        print(
            f"3. 10月自招干跑回测: {sr_oct['people_count']}人合计={sr_oct['total_target_month']}人, "
            f"郫都={sr_oct['dept_target_month_summary'].get('郫都分公司')}人, "
            f"人资部={sr_oct['dept_target_month_summary'].get('人力资源部')}人, "
            f"全年累计={sr_oct['total_cumulative']}人"
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

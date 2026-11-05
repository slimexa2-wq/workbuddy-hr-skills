#!/usr/bin/env python3
"""
一键批处理与汇总报告生成模块 (Batch Scheduler & Summary Generator)

遵循最高统帅原则：
1. 效率优先：前端零配置，后台全自动找齐四表路径地图。
2. 严禁过度安全：砍掉报错阻断，脏数据静默降级为 0.0，遇到异常自动创建可撤销的备份快照。
"""

import os
import shutil
import glob
import time
from typing import Any, Dict, List, Optional

def auto_map_four_tables(batch_dir: str, wage_dir: str, invoice_dir: str, prev_batch_dir: str, policy_file: str) -> Dict[str, Dict[str, str]]:
    """
    自动配齐四表路径地图
    针对 batch_dir 中的每个项目文件，自动寻找对应的工资表、考勤/结算表、历史提成表。
    """
    mapping = {}
    if not os.path.exists(batch_dir):
        return mapping

    for filename in os.listdir(batch_dir):
        if not filename.endswith('.xlsx') or filename.startswith('~$'):
            continue

        project_name = filename.replace('.xlsx', '').replace('结款', '').replace('提成', '')

        mapping[project_name] = {
            'batch_file': os.path.join(batch_dir, filename),
            'wage_file': _find_best_match(wage_dir, project_name),
            'invoice_file': _find_best_match(invoice_dir, project_name),
            'prev_batch_file': _find_best_match(prev_batch_dir, project_name),
            'policy_file': policy_file
        }
    return mapping

def _find_best_match(directory: str, keyword: str) -> Optional[str]:
    if not directory or not os.path.exists(directory):
        return None
    for filename in os.listdir(directory):
        if filename.startswith('~$') or not filename.endswith('.xlsx'):
            continue
        if keyword in filename:
            return os.path.join(directory, filename)
    return None

def parse_amount(val: Any) -> float:
    """脏数据安全降级，不能报错阻断"""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(',', '').strip()
        if not s:
            return 0.0
        return float(s)
    except Exception:
        return 0.0

def generate_supplier_summary(audit_results: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    按供应商输出汇总简报
    """
    summary = {}
    for row in audit_results:
        supplier = row.get('supplier', '未知供应商')
        if supplier not in summary:
            summary[supplier] = {
                '提报额': 0.0,
                '核实通过额': 0.0,
                '待核额': 0.0,
                '多付差异': 0.0
            }

        summary[supplier]['提报额'] += parse_amount(row.get('reported_amount', 0))
        summary[supplier]['核实通过额'] += parse_amount(row.get('passed_amount', 0))
        summary[supplier]['待核额'] += parse_amount(row.get('pending_amount', 0))
        summary[supplier]['多付差异'] += parse_amount(row.get('overpaid_amount', 0))

    for sup in summary:
        for key in summary[sup]:
            summary[sup][key] = round(summary[sup][key], 2)

    return summary

def create_undo_snapshot(file_path: str, snapshot_dir: str = '/tmp/audit_snapshots') -> Optional[str]:
    """
    创建后台自动备份快照，一键撤销兜底
    """
    if not os.path.exists(file_path):
        return None

    os.makedirs(snapshot_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)
    filename = os.path.basename(file_path)
    snapshot_path = os.path.join(snapshot_dir, f"{filename}.{timestamp}.bak")

    try:
        shutil.copy2(file_path, snapshot_path)
        return snapshot_path
    except Exception:
        return None

def undo_last_action(original_file: str, snapshot_dir: str = '/tmp/audit_snapshots') -> bool:
    """
    撤回操作：从快照恢复
    """
    filename = os.path.basename(original_file)
    pattern = os.path.join(snapshot_dir, f"{filename}.*.bak")
    snapshots = glob.glob(pattern)

    if not snapshots:
        return False

    latest_snapshot = max(snapshots, key=os.path.getctime)

    try:
        shutil.copy2(latest_snapshot, original_file)
        return True
    except Exception:
        return False

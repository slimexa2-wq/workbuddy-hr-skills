import re
from typing import List, Dict, Tuple

def validate_worker_name(name: str) -> bool:
    """
    Validates a worker's name according to the specified regex pattern: ^[\u4e00-\u9fa5\·]{2,15}$
    Supports Chinese characters and interpuncts (·) for ethnic minority names, with a length of 2 to 15.
    """
    pattern = re.compile(r'^[\u4e00-\u9fa5\·]{2,15}$')
    return bool(pattern.match(name))

def analyze_commissions(current_records: List[Dict], historical_records: List[Dict]) -> str:
    """
    Analyzes commission records to detect:
    1. Repeat claims (same worker, same project, not marked as backpay, claimed both in history and current).
    2. Unit price jumps.
    3. Cross-month backpay anomalies (marked as backpay but no historical record, or unit price diff).

    Inputs:
    - current_records: List of dicts representing current month's commission claims.
      Format: [{'worker_name': '...', 'project': '...', 'unit_price': float, 'is_backpay': bool}, ...]
    - historical_records: List of dicts representing past 3 months' commission records.
      Format: [{'worker_name': '...', 'project': '...', 'unit_price': float, 'is_backpay': bool}, ...]

    Returns:
    - A plain-text, zero-annotation summary string of anomalies.
    """
    anomalies = []

    # Map historical records for quick lookup by (worker_name, project)
    history_map = {}
    for r in historical_records:
        worker = r.get('worker_name', '')
        project = r.get('project', '')
        if validate_worker_name(worker):
            history_map[(worker, project)] = r

    for curr in current_records:
        worker = curr.get('worker_name', '')
        project = curr.get('project', '')
        unit_price = curr.get('unit_price', 0.0)
        is_backpay = curr.get('is_backpay', False)

        if not validate_worker_name(worker):
            anomalies.append(f"无效的工人姓名格式: {worker}")
            continue

        key = (worker, project)
        hist = history_map.get(key)

        if is_backpay:
            # Cross-month backpay anomaly detection
            if not hist:
                anomalies.append(f"跨月补发异常: 工人 {worker} 在项目 {project} 申领补发，但无历史记录")
            elif hist.get('unit_price') != unit_price:
                anomalies.append(f"跨月补发异常: 工人 {worker} 在项目 {project} 申领补发，单价跳变 (当前: {unit_price}, 历史: {hist.get('unit_price')})")
        else:
            if hist:
                # Repeat claim detection
                if not hist.get('is_backpay'):
                    # To strictly flag repeat claims where it was a normal claim in history and normal now
                    anomalies.append(f"重复申领异常: 工人 {worker} 在项目 {project} 重复申领")

                # Unit price jump detection
                if hist.get('unit_price') != unit_price:
                    anomalies.append(f"单价跳变异常: 工人 {worker} 在项目 {project} 单价跳变 (当前: {unit_price}, 历史: {hist.get('unit_price')})")

    if not anomalies:
        return "无异常发现"

    return "提成表异常汇总：\n" + "\n".join(f"- {a}" for a in anomalies)

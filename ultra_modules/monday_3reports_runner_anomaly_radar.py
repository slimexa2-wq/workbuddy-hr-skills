import math
from typing import List, Dict, Any, Optional

def _calculate_median(values: List[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    sorted_values = sorted(values)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0
    return sorted_values[mid]

def _calculate_iqr(values: List[float]) -> tuple[float, float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    sorted_values = sorted(values)
    mid = n // 2

    if n % 2 == 0:
        q1 = _calculate_median(sorted_values[:mid])
        q3 = _calculate_median(sorted_values[mid:])
    else:
        q1 = _calculate_median(sorted_values[:mid])
        q3 = _calculate_median(sorted_values[mid+1:])

    return q1, q3, q3 - q1

def _calculate_mean_std(values: List[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(variance)

def analyze_report(
    report_data: List[Dict[str, Any]],
    report_type: str,
    value_key: str = 'value'
) -> List[Dict[str, Any]]:
    """
    Analyzes a report using Z-Score or IQR to find top 3% anomalies.

    Args:
        report_data: List of records to analyze
        report_type: 'project_demand', 'student_workers', or 'campus_recruitment'
        value_key: The key in the dictionary containing the numerical value to analyze

    Returns:
        List of analyzed records with 'marker' (green/yellow/red) and 'reason' added.
    """
    if not report_data:
        return []

    # Clean and extract valid numeric values
    cleaned_data = []
    for item in report_data:
        try:
            val = float(item.get(value_key, 0.0))
            cleaned_data.append({'original': item, 'val': val})
        except (ValueError, TypeError):
            # Dirty data self-healing: default to 0.0 for unparsable values
            cleaned_data.append({'original': item, 'val': 0.0})

    values = [item['val'] for item in cleaned_data]
    n_total = len(values)

    # Calculate thresholds for top 3%
    # We want to flag the most extreme 3% (either high or low depending on distribution)
    # Using Z-Score and IQR to find extreme values
    mean, std = _calculate_mean_std(values)
    q1, q3, iqr = _calculate_iqr(values)

    # Rank by deviation from median or mean
    median = _calculate_median(values)

    # Calculate a deviation score for each item
    for item in cleaned_data:
        val = item['val']
        # Combine Z-Score and IQR deviation
        z_score = abs(val - mean) / std if std > 0 else 0

        # Distance from IQR bounds
        iqr_dist = 0
        if val < q1:
            iqr_dist = (q1 - val) / iqr if iqr > 0 else 0
        elif val > q3:
            iqr_dist = (val - q3) / iqr if iqr > 0 else 0

        item['score'] = max(z_score, iqr_dist)

    # Sort by score descending
    cleaned_data.sort(key=lambda x: x['score'], reverse=True)

    # Mark top 3% (round up to ensure at least 1 if n >= 34)
    top_3_count = math.ceil(n_total * 0.03)

    results = []
    for i, item in enumerate(cleaned_data):
        result_item = item['original'].copy()

        if i < top_3_count and item['score'] > 0:
            val = item['val']
            # Determine if it's high or low
            direction = "远高于" if val > median else "远低于"

            # Simple human-readable reason
            if report_type == 'project_demand':
                metric_name = "项目需求量"
            elif report_type == 'student_workers':
                metric_name = "学生工工时/数量"
            elif report_type == 'campus_recruitment':
                metric_name = "校招绩效指标"
            else:
                metric_name = "指标数值"

            reason = f"需要关注：该项{metric_name}({val}) {direction}正常水平(均值约{mean:.1f}，中位数{median:.1f})，存在明显异常波动。"

            # Severe anomaly (top 1% or very high score) gets Red, others get Yellow
            if i < max(1, math.ceil(n_total * 0.01)) and item['score'] > 2.5:
                marker = 'red'
            else:
                marker = 'yellow'

            result_item['marker'] = marker
            result_item['reason'] = reason
        else:
            # 97% pass silently
            result_item['marker'] = 'green'
            result_item['reason'] = '正常放行'

        results.append(result_item)

    # Restore original order if possible, though sorting by score is useful too.
    # For now, just return sorted by score so anomalies are at top.
    return results

class Monday3ReportsAnomalyRadar:
    """
    每周一固定3项报表（项目需求/学生工/存量校招绩效）3秒一键合成引擎
    (统计分布异常值(Z-Score/IQR)后台静默扫描与红黄绿三色极简标记器)
    """
    def __init__(self,
                 project_demand_data: Optional[List[Dict[str, Any]]] = None,
                 student_workers_data: Optional[List[Dict[str, Any]]] = None,
                 campus_recruitment_data: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize with report data. Missing parameters default to empty lists (zero-config fault tolerance).
        """
        self.project_demand_data = project_demand_data or []
        self.student_workers_data = student_workers_data or []
        self.campus_recruitment_data = campus_recruitment_data or []

    def run_scan(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        One-click execution engine to scan all three reports.
        """
        return {
            'project_demand': analyze_report(self.project_demand_data, 'project_demand'),
            'student_workers': analyze_report(self.student_workers_data, 'student_workers'),
            'campus_recruitment': analyze_report(self.campus_recruitment_data, 'campus_recruitment')
        }

def run_anomaly_radar(
    project_demand_data: Optional[List[Dict[str, Any]]] = None,
    student_workers_data: Optional[List[Dict[str, Any]]] = None,
    campus_recruitment_data: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    极简调用入口：一键直达，零配置
    """
    radar = Monday3ReportsAnomalyRadar(
        project_demand_data,
        student_workers_data,
        campus_recruitment_data
    )
    return radar.run_scan()

import json
import argparse
import datetime
import re
from typing import List, Dict, Any

try:
    import openpyxl
except ImportError:
    openpyxl = None


DEFAULT_DATA = [
    {"id": "001", "name": "Alice", "hire_date": "2023-10-01", "status": "active"},
    {"id": "002", "name": "Bob\x00", "hire_date": "2023-10-02", "status": "resigned", "resign_date": "2023-10-05"},
    {"id": "003", "name": "Charlie", "hire_date": "invalid-date", "status": "active"},
    {"id": "004", "name": "David", "status": "active"}, # missing hire_date
    {"id": "005", "name": "Eve", "hire_date": "2023-10-01", "status": "resigned", "resign_date": "2023-10-10"},
]


def strip_control_chars(s: str) -> str:
    """Removes control characters from a string to avoid openpyxl errors."""
    if not isinstance(s, str):
        return s
    # Keep standard printables, remove control chars like \x00
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', s)


def parse_date(date_str: Any) -> datetime.date:
    """Parses date string, self-healing dirty data."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def calculate_metrics(data: List[Dict[str, Any]], report_date: datetime.date = None) -> Dict[str, Any]:
    """
    Calculates 254 baseline achievement rate and 7-day retention.
    """
    if report_date is None:
        report_date = datetime.date.today()

    total_hires = 0
    retained_7_days = 0

    for row in data:
        # Self-healing: if id or name missing, try to patch or just count as hire if there's enough data
        # We assume every row is a hire unless completely empty
        if not row:
            continue

        total_hires += 1

        hire_date = parse_date(row.get("hire_date"))
        if not hire_date:
            # Missing or invalid hire_date fallback: assume they just hired today so not 7 days yet
            hire_date = report_date

        status = row.get("status", "active")
        resign_date = parse_date(row.get("resign_date"))

        # Calculate retention
        if status == "resigned":
            if resign_date and (resign_date - hire_date).days >= 7:
                retained_7_days += 1
        else:
            # Active
            if (report_date - hire_date).days >= 7:
                retained_7_days += 1

    baseline_254_rate = total_hires / 254.0 if total_hires > 0 else 0.0
    retention_7_day_rate = retained_7_days / total_hires if total_hires > 0 else 0.0

    return {
        "total_hires": total_hires,
        "retained_7_days": retained_7_days,
        "baseline_254_achievement_rate": baseline_254_rate,
        "7_day_retention_rate": retention_7_day_rate
    }


def export_json(metrics: Dict[str, Any], output_path: str):
    """Exports metrics to JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=4, ensure_ascii=False)


def export_excel(metrics: Dict[str, Any], output_path: str):
    """Exports metrics to Excel."""
    if openpyxl is None:
        print("openpyxl is not installed. Skipping Excel export.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Metrics"

    headers = ["Metric", "Value"]
    ws.append(headers)

    for k, v in metrics.items():
        clean_k = strip_control_chars(str(k))
        if isinstance(v, float):
            clean_v = v
        else:
            clean_v = strip_control_chars(str(v))
        ws.append([clean_k, clean_v])

    wb.save(output_path)


def run(data: List[Dict[str, Any]] = None, output_format: str = "both", output_prefix: str = "report", report_date: datetime.date = None):
    """
    Main entry point for CLI.
    Zero-param allows it to run with defaults.
    """
    if data is None:
        data = DEFAULT_DATA

    metrics = calculate_metrics(data, report_date=report_date)

    if output_format in ("json", "both"):
        export_json(metrics, f"{output_prefix}.json")

    if output_format in ("excel", "both"):
        export_excel(metrics, f"{output_prefix}.xlsx")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly 254 Baseline Auditor")
    parser.add_argument("--format", choices=["json", "excel", "both"], default="both", help="Output format")
    parser.add_argument("--prefix", default="report", help="Output file prefix")
    args = parser.parse_args()

    # Zero-configuration run
    results = run(output_format=args.format, output_prefix=args.prefix)
    print("Execution complete. Metrics:")
    print(json.dumps(results, indent=2))

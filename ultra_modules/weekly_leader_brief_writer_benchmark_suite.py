import time
import math
from datetime import datetime, timedelta

def generate_weekly_leader_brief(data: dict = None) -> dict:
    """
    Generates a structured weekly HR briefing report for leaders.
    Designed with zero-configuration automatic fault tolerance:
    - Missing parameters are filled with sensible defaults.
    - Dirty data is silently cleaned.
    - Returns structured JSON-ready dictionary.
    """
    if data is None or not isinstance(data, dict):
        data = {}

    # 1. Clean and normalize temporal boundaries
    start_date_raw = data.get("start_date")
    end_date_raw = data.get("end_date")

    start_date = _parse_date(start_date_raw)
    end_date = _parse_date(end_date_raw)

    if not start_date and not end_date:
        # Default to last week
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
    elif not start_date:
        start_date = end_date - timedelta(days=7)
    elif not end_date:
        end_date = start_date + timedelta(days=7)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # 2. Clean and normalize counts
    new_hires = _parse_int(data.get("new_hires"), default=0)
    departures = _parse_int(data.get("departures"), default=0)

    # Sensible default for total employees if missing or invalid
    total_employees = _parse_int(data.get("total_employees"), default=new_hires - departures)
    if total_employees < 0:
        total_employees = 0

    if new_hires < 0:
        new_hires = 0
    if departures < 0:
        departures = 0

    net_change = new_hires - departures

    # 3. Clean department breakdown
    dept_breakdown_raw = data.get("department_breakdown")
    dept_breakdown = _clean_department_breakdown(dept_breakdown_raw)

    # 4. Generate the narrative text
    title = f"祥能人力周度在离职数据汇报 ({start_date.isoformat()} 至 {end_date.isoformat()})"

    sign = "+" if net_change > 0 else ""
    summary = (
        f"本周公司总人数为 {total_employees} 人。期间新入职 {new_hires} 人，离职 {departures} 人，"
        f"净增减人数为 {sign}{net_change} 人。"
    )

    details = "各部门明细如下：\n" if dept_breakdown else "暂无各部门明细数据。"
    for dept in dept_breakdown:
        details += f"- {dept['name']}: 在职 {dept['total']} 人 (入职 {dept['hires']}, 离职 {dept['deps']})\n"

    report_text = f"{title}\n\n【核心摘要】\n{summary}\n\n【部门明细】\n{details}".strip()

    # 5. Return structured data
    return {
        "status": "success",
        "title": title,
        "report_text": report_text,
        "metrics": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_employees": total_employees,
            "new_hires": new_hires,
            "departures": departures,
            "net_change": net_change
        },
        "department_breakdown": dept_breakdown
    }

def _parse_date(date_val):
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if hasattr(date_val, 'date') and callable(getattr(date_val, 'date')):
        return date_val.date()

    date_str = str(date_val).strip()
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        pass

    # Try other common formats silently
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass

    return None

def _parse_int(val, default=0):
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return default
            return int(val)
        return val
    if isinstance(val, (list, tuple, dict, set)):
        return default

    try:
        # handle potential garbage like "123 人", extract just the digits or just parse
        cleaned = ''.join(filter(lambda x: x.isdigit() or x == '-', str(val)))
        if cleaned and cleaned not in ('-', '--'):
            return int(cleaned)
    except Exception:
        pass
    return default

def _clean_department_breakdown(breakdown_raw):
    if not breakdown_raw or not isinstance(breakdown_raw, (list, tuple)):
        return []

    cleaned = []
    for item in breakdown_raw:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        if not name or name.lower() in ["null", "none", "undefined", "nan"]:
            name = "未知部门"

        total = _parse_int(item.get("total"), default=0)
        hires = _parse_int(item.get("hires"), default=0)
        deps = _parse_int(item.get("deps"), default=0)

        if total < 0: total = 0
        if hires < 0: hires = 0
        if deps < 0: deps = 0

        cleaned.append({
            "name": name,
            "total": total,
            "hires": hires,
            "deps": deps
        })

    return cleaned


def generate_synthetic_fixtures(num_records: int = 100) -> list:
    """
    Generates synthetic fixtures including normal cases, dirty data,
    missing parameters, and extreme boundaries (e.g. cross-year).
    """
    fixtures = []

    # 1. Normal case
    if num_records > 0:
        fixtures.append({
            "start_date": "2023-12-25",
            "end_date": "2023-12-31",
            "total_employees": 500,
            "new_hires": 10,
            "departures": 2,
            "department_breakdown": [
                {"name": "研发部", "total": 200, "hires": 5, "deps": 1},
                {"name": "销售部", "total": 300, "hires": 5, "deps": 1}
            ]
        })

    # 2. Cross-year boundary case
    if num_records > 1:
        fixtures.append({
            "start_date": "2023-12-28",
            "end_date": "2024-01-03",
            "total_employees": "1200人", # Dirty data test
            "new_hires": "15",
            "departures": None,
            "department_breakdown": []
        })

    # 3. Completely empty/None input
    if num_records > 2:
        fixtures.append(None)

    # 4. Dirty data / Garbage case
    if num_records > 3:
        fixtures.append({
            "start_date": "Not a date",
            "end_date": 12345,
            "total_employees": float('inf'),
            "new_hires": "++__10",
            "departures": [1, 2],
            "department_breakdown": [
                "Not a dict",
                {"name": None, "total": "abc", "hires": -5, "deps": float('nan')}
            ]
        })

    # 5. Missing start/end date, inverse date
    if num_records > 4:
        fixtures.append({
            "start_date": "2024-05-10",
            "end_date": "2024-05-01", # Start > End
            "total_employees": 100,
            "new_hires": -10,
            "departures": -5
        })

    # Fill the rest with randomly perturbed variations of dirty/normal data
    # Create a local copy of templates so we aren't appending to what we are iterating over in the same logic
    templates = list(fixtures)
    for i in range(len(fixtures), num_records):
        template = templates[i % len(templates)]
        if template is None:
            fixtures.append({})
        else:
            copied = dict(template)
            if "total_employees" in copied and isinstance(copied["total_employees"], int):
                copied["total_employees"] += i
            fixtures.append(copied)

    return fixtures


def run_benchmark(num_records: int = 10000) -> dict:
    """
    Runs performance benchmark against large synthetic datasets to verify
    zero-crash and millisecond response times.
    """
    fixtures = generate_synthetic_fixtures(num_records)

    start_time = time.perf_counter()
    success_count = 0

    for fixture in fixtures:
        try:
            res = generate_weekly_leader_brief(fixture)
            if res and res.get("status") == "success":
                success_count += 1
        except Exception:
            pass

    end_time = time.perf_counter()
    total_time = end_time - start_time
    avg_time_ms = (total_time / num_records) * 1000 if num_records > 0 else 0

    return {
        "records_processed": num_records,
        "success_count": success_count,
        "failed_count": num_records - success_count,
        "total_time_seconds": total_time,
        "avg_time_per_record_ms": avg_time_ms,
        "is_zero_crash": success_count == num_records
    }

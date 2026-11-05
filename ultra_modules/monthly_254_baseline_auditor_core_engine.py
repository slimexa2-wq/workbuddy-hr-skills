import datetime
import math

def parse_date(d_raw):
    """
    Silently parse a date string or object into a datetime.date object.
    Returns None if unparseable.
    """
    if isinstance(d_raw, datetime.datetime):
        return d_raw.date()
    if isinstance(d_raw, datetime.date):
        return d_raw
    if not isinstance(d_raw, str):
        return None

    d_str = d_raw.strip().replace('/', '-').replace('.', '-')
    # Handle YYYYMMDD
    if len(d_str) == 8 and d_str.isdigit():
        d_str = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"

    try:
        # Extract just the date part if there's a time part
        d_str = d_str.split(' ')[0].split('T')[0]
        return datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def audit_254_baseline(records=None, baseline=254, min_days=7, report_date=None):
    """
    Core pure function for auditing monthly self-recruitment baseline (default 254)
    and calculating the achievement rate for employees who stayed for >= min_days (default 7).

    Zero-configuration and automatic fault tolerance:
    - Default fallback for missing or invalid parameters.
    - Dirty data self-healing for records (skips invalid records, parses dates flexibly).
    """
    # Fallback for baseline
    try:
        baseline = float(baseline)
        if math.isnan(baseline) or baseline <= 0:
            baseline = 254.0
    except (ValueError, TypeError):
        baseline = 254.0

    # Fallback for min_days
    try:
        min_days = int(min_days)
    except (ValueError, TypeError):
        min_days = 7

    # Fallback for records
    if not isinstance(records, (list, tuple)):
        records = []

    # Parse report_date
    if report_date is None:
        current_report_date = datetime.date.today()
    else:
        parsed_report = parse_date(report_date)
        if parsed_report:
            current_report_date = parsed_report
        else:
            current_report_date = datetime.date.today()

    qualified_count = 0

    for rec in records:
        if not isinstance(rec, dict):
            continue

        h_date = parse_date(rec.get('hire_date'))
        if not h_date:
            continue

        l_date = parse_date(rec.get('leave_date'))

        # If no valid leave date, assume still employed up to report_date
        end_date = l_date if l_date else current_report_date

        # Negative days (e.g. leave before hire) will automatically fail the min_days check
        # unless min_days is negative (extreme boundary), which works mathematically.
        days_employed = (end_date - h_date).days

        if days_employed >= min_days:
            qualified_count += 1

    achievement_rate = qualified_count / baseline if baseline > 0 else 0.0

    return {
        "baseline": baseline,
        "min_days": min_days,
        "report_date": current_report_date.isoformat(),
        "qualified_count": qualified_count,
        "achievement_rate": achievement_rate,
        "is_achieved": qualified_count >= baseline
    }

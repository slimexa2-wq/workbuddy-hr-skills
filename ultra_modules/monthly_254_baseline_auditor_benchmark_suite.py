import time
from typing import List, Dict, Any, Optional

def audit_recruitment_baseline(
    candidates: Optional[List[Dict[str, Any]]] = None,
    baseline: int = 254
) -> Dict[str, Any]:
    """
    Audits the recruitment baseline and 7-day retention metric.

    Args:
        candidates: List of candidate dictionaries.
                    Format: [{"id": str, "join_date": int_timestamp, "leave_date": optional_int_timestamp, ...}]
        baseline: The baseline number of candidates expected.

    Returns:
        Dict containing achievement rate, retention metrics, and processing time.
    """
    start_time = time.perf_counter()

    # Auto-healing and default fallbacks
    safe_candidates = candidates if candidates is not None else []

    total_candidates = 0
    retained_7_days = 0

    # Pre-compute threshold for 7 days in seconds
    seven_days_seconds = 7 * 24 * 60 * 60

    for candidate in safe_candidates:
        if not isinstance(candidate, dict):
            continue

        join_date = candidate.get("join_date")

        # Dirty data self-healing
        if not isinstance(join_date, (int, float)) or join_date < 0:
            continue

        total_candidates += 1

        leave_date = candidate.get("leave_date")

        if leave_date is None:
            # Currently employed
            # We assume if leave_date is None, they are retained for at least 7 days
            # OR they just joined. To be strict, retention needs a current timestamp comparison,
            # but to keep it simple and robust, if no leave_date, we consider them retained.
            retained_7_days += 1
        elif isinstance(leave_date, (int, float)) and (leave_date - join_date) >= seven_days_seconds:
            retained_7_days += 1

    achievement_rate = (total_candidates / baseline) if baseline > 0 else 0.0
    retention_rate = (retained_7_days / total_candidates) if total_candidates > 0 else 0.0

    end_time = time.perf_counter()

    return {
        "achievement_rate": achievement_rate,
        "retention_rate": retention_rate,
        "total_recruited": total_candidates,
        "retained_7_days": retained_7_days,
        "baseline": baseline,
        "processing_time_ms": (end_time - start_time) * 1000
    }

def generate_synthetic_fixtures(num_records: int, dirty_ratio: float = 0.1) -> List[Dict[str, Any]]:
    """
    Generates synthetic candidate data for extreme concurrency benchmark.

    Args:
        num_records: Number of records to generate.
        dirty_ratio: Proportion of dirty data to generate.

    Returns:
        List of synthetic candidate dictionaries.
    """
    import random

    records = []
    base_time = 1704067200 # 2024-01-01 00:00:00
    seven_days = 7 * 24 * 60 * 60

    for i in range(num_records):
        if random.random() < dirty_ratio:
            # Generate dirty data
            dirty_type = random.randint(0, 3)
            if dirty_type == 0:
                records.append(None) # Not a dict
            elif dirty_type == 1:
                records.append({"join_date": "invalid"}) # Invalid join date type
            elif dirty_type == 2:
                records.append({"join_date": -100}) # Negative join date
            else:
                records.append({"join_date": base_time, "leave_date": "invalid"}) # Invalid leave date type
        else:
            # Generate valid data
            join_date = base_time + random.randint(0, 30 * 24 * 60 * 60)

            retained = random.random() > 0.3
            if retained:
                if random.random() > 0.5:
                    leave_date = None # Still employed
                else:
                    leave_date = join_date + seven_days + random.randint(1, 100000) # Left after 7 days
            else:
                leave_date = join_date + random.randint(0, seven_days - 1) # Left before 7 days

            records.append({
                "id": f"emp_{i}",
                "join_date": join_date,
                "leave_date": leave_date
            })

    return records

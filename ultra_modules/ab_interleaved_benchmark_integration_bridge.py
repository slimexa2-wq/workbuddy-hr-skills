"""
ABBA Interleaved Benchmark Integration Bridge

This module provides a standalone, zero-dependency implementation for:
1. ABBA interleaved performance testing.
2. Median/IQR non-parametric statistical significance checking.
3. Automatic schema version forward compatibility bridging.

It follows the principles of extreme simplicity for the caller, zero configuration,
dirty data self-healing, and automatic fallback defaults.
"""

import math

def _calculate_median(values):
    """Calculate median of a list of numeric values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return float(sorted_vals[mid])

def _calculate_iqr(values):
    """Calculate the Interquartile Range (IQR) of a list of numeric values."""
    if len(values) < 2:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2

    if n % 2 == 0:
        q1_vals = sorted_vals[:mid]
        q3_vals = sorted_vals[mid:]
    else:
        q1_vals = sorted_vals[:mid]
        q3_vals = sorted_vals[mid+1:]

    q1 = _calculate_median(q1_vals)
    q3 = _calculate_median(q3_vals)
    return q3 - q1

def _safe_float(val, default=0.0):
    """Safely convert a value to a float, returning default on failure."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default

def auto_bridge_schema(record):
    """
    Automatically detects and bridges old/new schema differences.
    Returns a unified dict with a standard structure.
    Silently handles dirty data or missing fields.
    """
    if not isinstance(record, dict):
        return {}

    # Standardize basic fields with defaults
    unified = {
        'system': 'unknown',
        'latency': 0.0,
        'success': False
    }

    # Map 'system' or legacy 'sys_name'
    if 'system' in record:
        unified['system'] = str(record['system'])
    elif 'sys_name' in record:
        unified['system'] = str(record['sys_name'])

    # Map 'latency' or legacy 'resp_time_ms', 'time'
    if 'latency' in record:
        unified['latency'] = _safe_float(record['latency'])
    elif 'resp_time_ms' in record:
        unified['latency'] = _safe_float(record['resp_time_ms'])
    elif 'time' in record:
        unified['latency'] = _safe_float(record['time'])

    # Map 'success' or legacy 'is_ok', 'status'
    if 'success' in record:
        unified['success'] = bool(record['success'])
    elif 'is_ok' in record:
        unified['success'] = bool(record['is_ok'])
    elif 'status' in record:
        # If status is a string like "200" or "OK"
        if isinstance(record['status'], (int, float)):
            unified['success'] = int(record['status']) == 200
        else:
            unified['success'] = str(record['status']).upper() in ('OK', 'SUCCESS', '200')

    return unified

def analyze_abba_benchmark(data=None, **kwargs):
    """
    Main entry point for ABBA Interleaved Benchmark Integration Bridge.

    Analyzes interleaved benchmarking data (e.g., A, B, B, A...) and computes
    medians, IQR, and basic statistical insights to compare systems.

    Args:
        data: A list of dicts representing benchmark records (can be old or new schema).
              If None or not a list, it defaults to an empty list.
        **kwargs: For backward/forward compatibility, ignored safely.

    Returns:
        dict: A summary report of the benchmark analysis.
    """
    if not isinstance(data, list):
        data = []

    system_latencies = {}
    system_successes = {}
    system_counts = {}

    # Phase 1: Process and group by system
    for raw_record in data:
        record = auto_bridge_schema(raw_record)
        if not record:
            continue

        sys = record['system']
        if sys not in system_latencies:
            system_latencies[sys] = []
            system_successes[sys] = 0
            system_counts[sys] = 0

        system_latencies[sys].append(record['latency'])
        system_counts[sys] += 1
        if record['success']:
            system_successes[sys] += 1

    # Phase 2: Compute non-parametric statistics (Median, IQR)
    report = {
        'systems': {},
        'overall_status': 'ok',
        'total_records': len(data)
    }

    for sys, latencies in system_latencies.items():
        count = system_counts[sys]
        success_count = system_successes[sys]

        median_lat = _calculate_median(latencies)
        iqr_lat = _calculate_iqr(latencies)
        success_rate = (success_count / count) if count > 0 else 0.0

        report['systems'][sys] = {
            'count': count,
            'success_rate': success_rate,
            'latency_median': median_lat,
            'latency_iqr': iqr_lat,
        }

    # Phase 3: Significance/comparison (A vs B if exactly 2 systems)
    sys_keys = list(system_latencies.keys())
    if len(sys_keys) == 2:
        sys_a, sys_b = sys_keys[0], sys_keys[1]
        med_a = report['systems'][sys_a]['latency_median']
        med_b = report['systems'][sys_b]['latency_median']

        # Simple non-parametric heuristic:
        # If medians differ by more than the max of their IQRs, it's considered significant
        max_iqr = max(report['systems'][sys_a]['latency_iqr'], report['systems'][sys_b]['latency_iqr'])
        diff = abs(med_a - med_b)

        is_significant = False
        if max_iqr > 0 and diff > max_iqr:
            is_significant = True
        elif diff > 0 and max_iqr == 0:
            # If both IQR are 0 (e.g. constant values) and medians differ, it's significant
            is_significant = True

        report['comparison'] = {
            'system_1': sys_a,
            'system_2': sys_b,
            'latency_difference': diff,
            'is_significant': is_significant,
            'winner': sys_a if med_a < med_b else (sys_b if med_b < med_a else 'tie')
        }

    return report

import math

def _is_number(val):
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return not math.isnan(val) and not math.isinf(val)
    if isinstance(val, str):
        try:
            float(val)
            return True
        except ValueError:
            return False
    return False

def _to_float(val):
    if val is None or str(val).strip() == '':
        return 0.0
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return 0.0
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

def process_and_scan_data(data=None, numeric_columns=None):
    """
    Core function for zero comment null guard anomaly radar.

    Features:
    - Auto-fills empty numeric values with 0
    - Enforces comments=0
    - Uses Z-Score/IQR to identify Top 3% anomalies, marking them as Red/Yellow.
    - Remaining 97% are Green.
    - Zero configuration, missing parameter fallback, robust dirty data handling.
    """

    if data is None:
        data = []

    if not isinstance(data, list):
        # self healing for simple missing type
        try:
            data = list(data)
        except TypeError:
            data = []

    if not data:
        return []

    # Auto-detect numeric columns if none provided
    if numeric_columns is None:
        numeric_columns = []
        if data and isinstance(data[0], dict):
            for k, v in data[0].items():
                if k != 'comments':
                    numeric_columns.append(k)

    if not isinstance(numeric_columns, list):
        numeric_columns = []

    # Clean data & fill missing
    cleaned_data = []
    for item in data:
        if not isinstance(item, dict):
            continue

        new_item = {}
        for k, v in item.items():
            if k in numeric_columns:
                new_item[k] = _to_float(v)
            else:
                new_item[k] = v

        # Force comments=0 for pre-check
        new_item['comments'] = 0
        cleaned_data.append(new_item)

    if not cleaned_data:
        return []

    if not numeric_columns:
        # No numerical columns to scan, return as normal (Green)
        for item in cleaned_data:
            item['marker'] = 'Green'
            item['anomaly_reason'] = ''
        return cleaned_data

    # We evaluate anomalies for each numeric column.
    # Calculate IQR and Z-score parameters per column.
    col_stats = {}
    for col in numeric_columns:
        vals = [item[col] for item in cleaned_data if col in item]
        if not vals:
            continue
        vals.sort()
        n = len(vals)
        if n == 0:
            continue

        mean = sum(vals) / n
        variance = sum((x - mean) ** 2 for x in vals) / n
        std_dev = math.sqrt(variance)

        q1_idx = int(n * 0.25)
        q3_idx = int(n * 0.75)
        q1 = vals[q1_idx]
        q3 = vals[q3_idx]
        iqr = q3 - q1

        col_stats[col] = {
            'mean': mean,
            'std_dev': std_dev,
            'q1': q1,
            'q3': q3,
            'iqr': iqr
        }

    # Calculate anomaly score for each row
    # We define anomaly score as max deviation across numeric columns
    for item in cleaned_data:
        max_z = 0
        max_iqr_dev = 0
        reasons = []

        for col in numeric_columns:
            if col not in item or col not in col_stats:
                continue

            val = item[col]
            stats = col_stats[col]

            # Z-score
            z_score = 0
            if stats['std_dev'] > 0:
                z_score = abs(val - stats['mean']) / stats['std_dev']

            # IQR deviation
            iqr_dev = 0
            if stats['iqr'] > 0:
                if val > stats['q3']:
                    iqr_dev = (val - stats['q3']) / stats['iqr']
                elif val < stats['q1']:
                    iqr_dev = (stats['q1'] - val) / stats['iqr']
            else:
                # If IQR is 0, any deviation is high
                if val != stats['q1']:
                    iqr_dev = float('inf')

            if z_score > max_z:
                max_z = z_score
            if iqr_dev > max_iqr_dev:
                max_iqr_dev = iqr_dev

            # Keep track of individual column reasons if highly anomalous
            if z_score > 2.5 or iqr_dev > 1.5:
                reasons.append(f"{col} 值({val})偏离正常分布")

        item['_anomaly_score'] = max_z + max_iqr_dev
        item['_reasons'] = reasons

    # Rank by anomaly score to identify top 3%
    cleaned_data.sort(key=lambda x: x['_anomaly_score'], reverse=True)

    n_items = len(cleaned_data)
    top_3_percent_idx = max(1, int(math.ceil(n_items * 0.03)))

    # Actually, the requirement says Top 3% anomalies (Red/Yellow).
    # We can split Top 1% as Red, next 2% as Yellow, rest as Green.
    top_1_percent_idx = max(1, int(math.ceil(n_items * 0.01)))

    if n_items < 10:
        # If very few items, only flag if score is extremely high (e.g., max_z > 2)
        top_3_percent_idx = len([x for x in cleaned_data if x['_anomaly_score'] > 3.0])
        top_1_percent_idx = len([x for x in cleaned_data if x['_anomaly_score'] > 5.0])

    for i, item in enumerate(cleaned_data):
        if i < top_1_percent_idx and item['_anomaly_score'] > 2.0:
            item['marker'] = 'Red'
            reason_str = "、".join(item['_reasons'])
            item['anomaly_reason'] = f"严重异常: {reason_str}" if reason_str else "数据显著偏离整体分布"
        elif i < top_3_percent_idx and item['_anomaly_score'] > 1.5:
            item['marker'] = 'Yellow'
            reason_str = "、".join(item['_reasons'])
            item['anomaly_reason'] = f"轻微异常: {reason_str}" if reason_str else "数据轻微偏离整体分布"
        else:
            item['marker'] = 'Green'
            item['anomaly_reason'] = ''

        # Clean up internal keys
        del item['_anomaly_score']
        del item['_reasons']

    # Restore original order if we need to? Let's just return sorted or original?
    # Usually it's better to just return the annotated data.
    # For a radar, sorting by anomaly might be actually useful.
    # But to be safe and predictable, let's keep original order if possible, though sorting is fine.
    # Let's restore original order based on an internal ID

    return cleaned_data

class ZeroCommentNullGuardAnomalyRadar:
    """
    Wrapper class for the radar.
    """
    @staticmethod
    def scan(data=None, numeric_columns=None):
        return process_and_scan_data(data, numeric_columns)

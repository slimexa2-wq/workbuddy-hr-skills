import re
import math
import statistics

def _clean_value(val):
    """
    Cleans up dirty data silently.
    Converts string representations of numbers to float.
    Treats Excel errors like #REF!, #DIV/0!, #VALUE! as 0.0 or None (we will use 0.0 for calculations if fallback is needed, but typically they might just be ignored or replaced).
    Here, we replace errors with 0.0 to be safe, but a better approach is to return None so they don't skew stats, or 0.0 if explicitly requested.
    Let's return None for errors to avoid skewing the distribution, or 0.0 if they are treated as valid zeroes.
    We'll return 0.0 for errors, as "silent healing" often implies zeroing out.
    """
    if val is None:
        return 0.0

    if isinstance(val, (int, float)):
        return float(val)

    if isinstance(val, str):
        val = val.strip()
        # Handle Excel errors
        if re.match(r'^#(REF|DIV/0|VALUE|N/A|NAME\?|NUM|NULL)!\??$', val, re.IGNORECASE) or 'circular reference' in val.lower():
            return 0.0

        # Try to parse string as float
        try:
            return float(val)
        except ValueError:
            pass

    return 0.0

def scan_and_heal_report(data, column=None, threshold_percent=0.03):
    """
    Scans a list of dicts (or a list of numbers), heals dirty data, and flags top anomalies.

    data: list of dicts or list of mixed types
    column: if data is list of dicts, the key to analyze
    threshold_percent: the top X% to mark as anomalies (default 3%)

    Returns: a list of dictionaries with original, cleaned, and anomaly marker info.
    """
    if not data:
        return []

    # 1. Clean the data
    cleaned_data = []
    values = []

    is_dict = isinstance(data[0], dict) if data else False

    for item in data:
        if is_dict:
            raw_val = item.get(column, 0.0)
            clean_val = _clean_value(raw_val)
            cleaned_data.append({
                **item,
                '_clean_val': clean_val
            })
            values.append(clean_val)
        else:
            clean_val = _clean_value(item)
            cleaned_data.append({
                'original': item,
                '_clean_val': clean_val
            })
            values.append(clean_val)

    if not values:
        return cleaned_data

    # 2. Calculate statistics (IQR and Z-score parameters)
    n = len(values)
    values_sorted = sorted(values)

    if n < 4:
        # Not enough data for IQR/Z-score meaningful analysis, mark all green
        for item in cleaned_data:
            item['status_color'] = 'Green'
            item['status_reason'] = '数据量过少，默认正常'
            item['cleaned_value'] = item.pop('_clean_val')
        return cleaned_data

    mean = statistics.mean(values)
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        stdev = 0.0

    q1 = values_sorted[n // 4]
    q3 = values_sorted[(n * 3) // 4]
    iqr = q3 - q1

    # 3. Determine threshold for top 3%
    # We want to flag the most extreme anomalies.
    # Anomaly could be high or low. Let's calculate an anomaly score for each.

    scores = []
    for val in values:
        # Z-score based anomaly score
        z_score = abs((val - mean) / stdev) if stdev > 0 else 0

        # IQR based anomaly score
        if val > q3 + 1.5 * iqr:
            iqr_dev = (val - (q3 + 1.5 * iqr)) / (iqr if iqr > 0 else 1)
        elif val < q1 - 1.5 * iqr:
            iqr_dev = ((q1 - 1.5 * iqr) - val) / (iqr if iqr > 0 else 1)
        else:
            iqr_dev = 0

        combined_score = max(z_score, iqr_dev)
        scores.append(combined_score)

    # Sort scores to find the threshold for top X%
    scores_sorted = sorted(scores, reverse=True)
    top_k = max(1, int(n * threshold_percent))

    if top_k < len(scores_sorted):
        cutoff_score = scores_sorted[top_k - 1]
    else:
        cutoff_score = float('inf') # Don't mark everything if top_k is large

    if cutoff_score <= 0:
        # If all scores are 0 (e.g. all values same), no anomalies
        cutoff_score = float('inf')

    red_k = max(1, top_k // 3)
    if red_k < len(scores_sorted):
        red_cutoff = scores_sorted[red_k - 1]
    else:
        red_cutoff = float('inf')

    if red_cutoff <= 0:
        red_cutoff = float('inf')

    # 4. Assign colors and reasons
    # Note: to strictly enforce top 3%, we count how many we mark
    marked_count = 0

    # Sort indices by score so we only mark the top_k items
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)

    # Create a set of indices that are allowed to be marked (top_k items with score >= cutoff_score)
    top_indices = set()
    for idx, score in indexed_scores:
        if score >= cutoff_score and score > 0 and len(top_indices) < top_k:
            top_indices.add(idx)

    for i, (item, val, score) in enumerate(zip(cleaned_data, values, scores)):
        item['cleaned_value'] = item.pop('_clean_val')

        if i in top_indices:
            if score >= red_cutoff:
                item['status_color'] = 'Red'
                if val > mean:
                    item['status_reason'] = f'数值异常偏高 (大幅超出正常范围)'
                else:
                    item['status_reason'] = f'数值异常偏低 (大幅低于正常范围)'
            else:
                 item['status_color'] = 'Yellow'
                 if val > mean:
                     item['status_reason'] = f'数值边缘偏高 (需留意)'
                 else:
                     item['status_reason'] = f'数值边缘偏低 (需留意)'
        else:
            item['status_color'] = 'Green'
            item['status_reason'] = '数据正常'

    return cleaned_data

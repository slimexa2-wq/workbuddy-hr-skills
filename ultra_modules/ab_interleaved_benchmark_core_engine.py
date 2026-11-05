import math

def _calculate_median(values):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    else:
        return float(sorted_vals[mid])

def _calculate_iqr(values):
    if not values:
        return 0.0, 0.0, 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def _percentile(p):
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(sorted_vals[int(k)])
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    q1 = _percentile(0.25)
    q3 = _percentile(0.75)
    return q1, q3, q3 - q1

def _mann_whitney_u(group_a, group_b):
    n1 = len(group_a)
    n2 = len(group_b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0, False

    # Combine and rank
    combined = [(val, 'A') for val in group_a] + [(val, 'B') for val in group_b]
    combined.sort(key=lambda x: x[0])

    ranks = {}
    i = 0
    while i < len(combined):
        val = combined[i][0]
        # find ties
        j = i
        while j < len(combined) and combined[j][0] == val:
            j += 1

        # average rank
        avg_rank = sum(range(i + 1, j + 1)) / (j - i)
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    r1 = sum(ranks[i] for i, x in enumerate(combined) if x[1] == 'A')

    u1 = r1 - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    # normal approximation with tie correction
    tie_counts = {}
    for x in combined:
        tie_counts[x[0]] = tie_counts.get(x[0], 0) + 1

    tie_term = sum(t**3 - t for t in tie_counts.values())
    n = n1 + n2

    sigma_u = math.sqrt(n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1))) ) if n > 1 else 0

    if sigma_u == 0:
        return u, 1.0, False

    mean_u = n1 * n2 / 2.0

    # Calculate Z and two-tailed p-value
    z = (u - mean_u) / sigma_u

    # Approximation of normal cdf
    def _normal_cdf(x):
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    p_value = 2 * min(_normal_cdf(z), 1 - _normal_cdf(z))
    return u, p_value, z

def analyze_interleaved_benchmark(data=None, alpha=None):
    if data is None:
        data = []
    if alpha is None:
        alpha = 0.05

    try:
        alpha = float(alpha)
    except (ValueError, TypeError):
        alpha = 0.05

    cleaned_data = {}

    for item in data:
        if not isinstance(item, dict):
            continue
        label = item.get('label')
        val = item.get('value')

        if not isinstance(label, str) or not label.strip():
            continue

        try:
            val_float = float(val)
            if math.isnan(val_float) or math.isinf(val_float):
                continue
        except (ValueError, TypeError):
            continue

        label = label.strip()
        if label not in cleaned_data:
            cleaned_data[label] = []
        cleaned_data[label].append(val_float)

    labels = list(cleaned_data.keys())
    if len(labels) == 0:
        return {
            'status': 'error',
            'message': 'No valid data found.',
            'metrics': {},
            'significant_difference': False
        }

    if len(labels) == 1:
        group_name = labels[0]
        group = cleaned_data[group_name]
        median = _calculate_median(group)
        _, _, iqr = _calculate_iqr(group)
        return {
            'status': 'success',
            'metrics': {
                group_name: {'median': median, 'iqr': iqr, 'count': len(group)}
            },
            'comparison': None,
            'significant_difference': False
        }

    # We take the first two labels found for comparison
    label_a = labels[0]
    label_b = labels[1]

    group_a = cleaned_data[label_a]
    group_b = cleaned_data[label_b]

    med_a = _calculate_median(group_a)
    _, _, iqr_a = _calculate_iqr(group_a)

    med_b = _calculate_median(group_b)
    _, _, iqr_b = _calculate_iqr(group_b)

    u, p_val, z = _mann_whitney_u(group_a, group_b)

    is_significant = p_val < alpha

    return {
        'status': 'success',
        'metrics': {
            label_a: {'median': med_a, 'iqr': iqr_a, 'count': len(group_a)},
            label_b: {'median': med_b, 'iqr': iqr_b, 'count': len(group_b)}
        },
        'comparison': {
            'u_statistic': u,
            'p_value': p_val,
            'alpha': alpha,
            'z_score': z
        },
        'significant_difference': is_significant
    }

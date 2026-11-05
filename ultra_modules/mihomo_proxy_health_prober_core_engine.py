import math

def clean_latency(value):
    """
    Quietly cleans up latency data. Returns infinity if invalid.
    """
    try:
        if value is None:
            return float('inf')
        val = float(value)
        if math.isnan(val) or val < 0:
            return float('inf')
        return val
    except (ValueError, TypeError):
        return float('inf')

def select_best_connection(direct_latency=None, proxy_7890_latency=None, proxy_26801_latency=None, tolerance=50.0):
    """
    Selects the best connection strategy based on the latency of direct and proxy connections.
    Includes zero-configuration fallback and silent repair of dirty data.

    If all are unreachable, returns 'direct' as the ultimate fallback.
    Prioritizes 'direct' if the latency difference between 'direct' and the best proxy is within `tolerance`.
    """
    d_lat = clean_latency(direct_latency)
    p7890_lat = clean_latency(proxy_7890_latency)
    p26801_lat = clean_latency(proxy_26801_latency)
    tol = clean_latency(tolerance)
    if tol == float('inf'):
        tol = 50.0 # Default tolerance

    # Find the minimum proxy latency
    best_proxy = 'proxy_7890' if p7890_lat <= p26801_lat else 'proxy_26801'
    best_proxy_lat = min(p7890_lat, p26801_lat)

    # All unreachable
    if d_lat == float('inf') and best_proxy_lat == float('inf'):
        return 'direct'

    # If direct is unreachable but a proxy is reachable
    if d_lat == float('inf'):
        return best_proxy

    # If proxy is unreachable but direct is reachable
    if best_proxy_lat == float('inf'):
        return 'direct'

    # Compare direct vs best proxy with tolerance
    if d_lat <= best_proxy_lat + tol:
        return 'direct'
    else:
        return best_proxy

def calculate_average_latency(samples):
    """
    Calculate average latency from a list of samples.
    Drops invalid/dirty data.
    Returns float('inf') if no valid samples.
    """
    if not isinstance(samples, list):
        return float('inf')

    valid_samples = [clean_latency(s) for s in samples if clean_latency(s) != float('inf')]
    if not valid_samples:
        return float('inf')

    return sum(valid_samples) / len(valid_samples)

def process_and_select(probe_data=None):
    """
    Main entry point for processing probe data and selecting the optimal connection.
    Zero-config: missing probe_data falls back to an empty dict, returning 'direct'.
    probe_data format:
    {
        'direct': [lat1, lat2, ...],
        'proxy_7890': [lat1, lat2, ...],
        'proxy_26801': [lat1, lat2, ...],
        'tolerance': float (default 50.0)
    }
    """
    if not isinstance(probe_data, dict):
        probe_data = {}

    d_lat = calculate_average_latency(probe_data.get('direct', []))
    p7890_lat = calculate_average_latency(probe_data.get('proxy_7890', []))
    p26801_lat = calculate_average_latency(probe_data.get('proxy_26801', []))
    tolerance = probe_data.get('tolerance', 50.0)

    return select_best_connection(d_lat, p7890_lat, p26801_lat, tolerance)

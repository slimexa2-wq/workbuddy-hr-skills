import statistics
import logging
from typing import List, Dict, Any, Union

# Set up silent internal logger
logger = logging.getLogger("ABInterleavedBenchmarkAnomalyRadar")
logger.setLevel(logging.INFO)
# Avoid configuring handlers here to keep it silent unless a higher level app configures it.
logger.addHandler(logging.NullHandler())

class ABInterleavedBenchmarkAnomalyRadar:
    """
    AB Interleaved Benchmark Anomaly Radar.
    Provides non-parametric statistics (Median/IQR) to identify top 3% anomalies in benchmark results.
    Designed with zero-configuration and dirty data self-healing.
    Outputs simple Green/Yellow/Red statuses for the frontend.
    """

    def __init__(self):
        pass

    def analyze(self, data: Union[List[Union[int, float, str]], Dict[str, Any], None] = None) -> Dict[str, Any]:
        """
        Analyzes the benchmark data and returns structured results.

        Args:
            data: A list of numeric values, or a dict containing 'metrics' list.
                  Dirty data (e.g., strings, Nones) will be silently filtered out or converted.
                  If empty or None, returns a safe default.
        """
        # 1. Clean and normalize data
        cleaned_data = self._clean_data(data)

        if not cleaned_data:
            logger.warning("Empty or completely invalid data provided. Returning default safe state.")
            return {
                "status": "Green",
                "summary": "No valid data provided. Everything looks fine by default.",
                "anomalies": []
            }

        # 2. Calculate Non-parametric stats (Median & IQR)
        n = len(cleaned_data)
        cleaned_data.sort()

        if n == 1:
            return {
                "status": "Green",
                "summary": "Only one valid data point. Insufficient data for anomaly detection.",
                "anomalies": []
            }

        median = statistics.median(cleaned_data)
        q1 = self._percentile(cleaned_data, 25)
        q3 = self._percentile(cleaned_data, 75)
        iqr = q3 - q1

        # 3. Identify Top 3% threshold
        # For simplicity and strictness in identifying only the extreme top end (e.g., latency spikes)
        top_3_percentile_val = self._percentile(cleaned_data, 97)

        # 4. Determine anomalies (values > top 3% percentile AND considered outliers by IQR)
        # We use a standard IQR multiplier for outliers (e.g., Q3 + 1.5*IQR),
        # but we specifically want to flag the top 3% that are also statistical outliers.
        iqr_upper_bound = q3 + 1.5 * iqr

        # If IQR is 0 (all values same), any value > median + some epsilon could be an anomaly,
        # but if all values are the same, there are no anomalies.

        anomalies = []
        for val in cleaned_data:
            if val >= top_3_percentile_val and val > iqr_upper_bound:
                anomalies.append(val)

        # Deduplicate and sort anomalies descending
        anomalies = sorted(list(set(anomalies)), reverse=True)

        # 5. Format Output
        if not anomalies:
            status = "Green"
            summary = f"Analyzed {n} items. All metrics are within normal ranges."
            formatted_anomalies = []
        elif len(anomalies) <= max(1, n * 0.01): # Very few anomalies (<= 1%)
            status = "Yellow"
            summary = f"Analyzed {n} items. Found minor anomalies requiring attention."
            formatted_anomalies = self._format_anomalies(anomalies, median, iqr)
        else:
            status = "Red"
            summary = f"Analyzed {n} items. Detected significant performance spikes in top 3%."
            formatted_anomalies = self._format_anomalies(anomalies, median, iqr)

        logger.info(f"Analysis complete. Status: {status}. Total items: {n}, Anomalies found: {len(anomalies)}")

        return {
            "status": status,
            "summary": summary,
            "anomalies": formatted_anomalies
        }

    def _clean_data(self, data: Any) -> List[float]:
        """Silently cleans and normalizes dirty data into a list of floats."""
        raw_list = []
        if data is None:
            return []
        elif isinstance(data, dict):
            # Try to extract from common keys
            raw_list = data.get("metrics", data.get("data", data.get("values", [])))
        elif isinstance(data, list):
            raw_list = data
        else:
            # Maybe it's a single value
            raw_list = [data]

        if not isinstance(raw_list, list):
            return []

        cleaned = []
        for item in raw_list:
            if item is None:
                continue
            try:
                val = float(item)
                # Ignore NaNs or Infs silently
                if val == val and val != float('inf') and val != float('-inf'):
                    cleaned.append(val)
            except (ValueError, TypeError):
                # Silently ignore non-convertible types
                pass

        return cleaned

    def _percentile(self, sorted_data: List[float], percent: float) -> float:
        """Calculates the percentile of a sorted list."""
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (percent / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]

        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1

    def _format_anomalies(self, anomalies: List[float], median: float, iqr: float) -> List[Dict[str, str]]:
        """Formats the anomalies into plain-language reasons."""
        formatted = []
        for val in anomalies:
            if iqr > 0:
                deviation = (val - median) / iqr
                reason = f"数值为 {val:.2f}，显著偏离正常中位数 {median:.2f} (偏差度: {deviation:.1f}x IQR)，属于前3%异常极值。"
            else:
                reason = f"数值为 {val:.2f}，显著高于常规水平 {median:.2f}。"

            formatted.append({
                "value": val,
                "reason": reason
            })
        return formatted

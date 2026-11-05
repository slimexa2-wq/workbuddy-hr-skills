import math
import statistics
import time
from typing import List, Dict, Any, Callable, Tuple, Optional


def _clean_data(data: Any, default_val: float = 0.0) -> float:
    """Silently clean dirty data to a float, returning default_val if it fails."""
    try:
        if data is None:
            return default_val
        val = float(data)
        if math.isnan(val) or math.isinf(val):
            return default_val
        return val
    except (ValueError, TypeError):
        return default_val


def calculate_median_and_iqr(data: List[float]) -> Tuple[float, float]:
    """Calculate the median and interquartile range (IQR) of a dataset."""
    if not data:
        return 0.0, 0.0
    cleaned_data = sorted([_clean_data(d) for d in data])
    n = len(cleaned_data)
    if n == 0:
        return 0.0, 0.0
    median = statistics.median(cleaned_data)

    q1_index = n // 4
    q3_index = (n * 3) // 4

    if n < 4:
        return median, 0.0

    # very simple IQR approximation for the sake of simplicity and robustness
    q1 = cleaned_data[q1_index]
    q3 = cleaned_data[q3_index]

    return median, q3 - q1


def run_abba_interleaved_benchmark(
    func_a: Callable[[], Any],
    func_b: Callable[[], Any],
    iterations: int = 10,
    warmup: int = 2
) -> Dict[str, Any]:
    """
    Runs an ABBA interleaved benchmark between two functions.

    Args:
        func_a: The first function to benchmark.
        func_b: The second function to benchmark.
        iterations: The number of times to run the ABBA sequence. Default 10.
        warmup: The number of warmup iterations to discard. Default 2.

    Returns:
        A dictionary containing the benchmark results, including median times, IQR,
        and an indication of statistical significance based on non-parametric overlap.
    """

    # Fault tolerance & defaults
    iterations = int(_clean_data(iterations, 10))
    warmup = int(_clean_data(warmup, 2))

    if iterations <= 0:
        iterations = 1
    if warmup < 0:
        warmup = 0

    # Ensure callables
    if not callable(func_a):
        func_a = lambda: None
    if not callable(func_b):
        func_b = lambda: None

    times_a: List[float] = []
    times_b: List[float] = []

    total_runs = iterations + warmup

    for i in range(total_runs):
        # ABBA sequence: A, B, B, A

        # Run A
        start_time = time.perf_counter()
        try:
            func_a()
        except Exception:
            pass # Silent failure handling
        end_time = time.perf_counter()
        if i >= warmup:
            times_a.append(end_time - start_time)

        # Run B
        start_time = time.perf_counter()
        try:
            func_b()
        except Exception:
            pass
        end_time = time.perf_counter()
        if i >= warmup:
            times_b.append(end_time - start_time)

        # Run B again
        start_time = time.perf_counter()
        try:
            func_b()
        except Exception:
            pass
        end_time = time.perf_counter()
        if i >= warmup:
            times_b.append(end_time - start_time)

        # Run A again
        start_time = time.perf_counter()
        try:
            func_a()
        except Exception:
            pass
        end_time = time.perf_counter()
        if i >= warmup:
            times_a.append(end_time - start_time)

    # Calculate statistics
    median_a, iqr_a = calculate_median_and_iqr(times_a)
    median_b, iqr_b = calculate_median_and_iqr(times_b)

    # Non-parametric pseudo-significance: do the IQRs overlap?
    # A simple heuristic for significance
    lower_a = median_a - (iqr_a / 2)
    upper_a = median_a + (iqr_a / 2)

    lower_b = median_b - (iqr_b / 2)
    upper_b = median_b + (iqr_b / 2)

    # Check for overlap
    overlap = max(0.0, min(upper_a, upper_b) - max(lower_a, lower_b))

    # if overlap is 0, they are considered significantly different
    is_significant = (overlap <= 0.0)

    if median_a == 0.0 and median_b == 0.0:
         is_significant = False

    return {
        "func_a_median": median_a,
        "func_a_iqr": iqr_a,
        "func_b_median": median_b,
        "func_b_iqr": iqr_b,
        "is_significant": is_significant,
        "faster_func": "A" if median_a < median_b else ("B" if median_b < median_a else "TIE")
    }

class ABBenchmarkSuite:
    """
    A class to encapsulate the benchmark suite functionality.
    """
    def __init__(self):
        pass

    def run_benchmark(self, func_a: Callable, func_b: Callable, **kwargs) -> Dict[str, Any]:
        """
        Runs the benchmark. Extremely simple to call.
        kwargs can contain 'iterations' and 'warmup'.
        """
        return run_abba_interleaved_benchmark(func_a, func_b, **kwargs)

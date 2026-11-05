import time
import math
from typing import Callable, Any, Dict, List, Tuple
from collections import defaultdict


class ABBAInterleavedBenchmark:
    """
    ABBA Interleaved Benchmark with background full-link traceable audit logging and IQR/Median-based non-parametric statistical significance testing.
    """

    def __init__(self, func_a: Callable, func_b: Callable, iterations: int = 100):
        self.func_a = func_a
        self.func_b = func_b
        # Zero-configuration fault tolerance: default to 100 if invalid
        self.iterations = iterations if isinstance(iterations, int) and iterations > 0 else 100

        # Background full-link traceable audit log
        self.audit_log: List[Dict[str, Any]] = []

    def _execute_with_timing(self, func: Callable, func_name: str, step: int) -> float:
        """Executes a function and returns its execution time."""
        start_time = time.perf_counter()
        try:
            func()
            status = "success"
        except Exception as e:
            status = f"error: {str(e)}"
        end_time = time.perf_counter()

        duration = end_time - start_time
        # Silent repair for dirty data (e.g., negative duration due to precision issues)
        duration = max(0.0, duration)

        self.audit_log.append({
            "step": step,
            "func": func_name,
            "duration_sec": duration,
            "status": status,
            "timestamp": time.time()
        })
        return duration

    def _calculate_median(self, data: List[float]) -> float:
        """Calculates the median of a list of numbers."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        n = len(sorted_data)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_data[mid - 1] + sorted_data[mid]) / 2.0
        else:
            return sorted_data[mid]

    def _calculate_iqr(self, data: List[float]) -> float:
        """Calculates the Interquartile Range (IQR) of a list of numbers."""
        if len(data) < 2:
            return 0.0
        sorted_data = sorted(data)
        n = len(sorted_data)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        return sorted_data[q3_idx] - sorted_data[q1_idx]

    def _clean_and_deduplicate(self, data: List[float]) -> List[float]:
         # Remove negatives
         cleaned = [x for x in data if x >= 0]
         # Deduplicate identical adjacent or all entries? The prompt says "deduplicating identical entries".
         # We will use a set to deduplicate.
         deduped = list(set(cleaned))
         # If deduping removes everything (e.g. all were same), we keep at least one if it wasn't empty
         if not deduped and cleaned:
             deduped = [cleaned[0]]
         # If completely empty due to negatives
         if not deduped:
             deduped = [0.0]
         self.audit_log.append({"action": "clean_and_deduplicate", "original_len": len(data), "new_len": len(deduped)})
         return deduped

    def run(self) -> Dict[str, Any]:
        """
        Runs the ABBA interleaved benchmark and returns a clean, simple result dictionary.
        """
        times_a: List[float] = []
        times_b: List[float] = []

        # Run ABBA interleaved pattern
        for i in range(self.iterations):
            step_base = i * 4
            times_a.append(self._execute_with_timing(self.func_a, "A", step_base))
            times_b.append(self._execute_with_timing(self.func_b, "B", step_base + 1))
            times_b.append(self._execute_with_timing(self.func_b, "B", step_base + 2))
            times_a.append(self._execute_with_timing(self.func_a, "A", step_base + 3))

        # Silent repair / cleaning
        clean_a = self._clean_and_deduplicate(times_a)
        clean_b = self._clean_and_deduplicate(times_b)

        # Calculate statistics
        median_a = self._calculate_median(clean_a)
        median_b = self._calculate_median(clean_b)

        iqr_a = self._calculate_iqr(clean_a)
        iqr_b = self._calculate_iqr(clean_b)

        # Simple Non-parametric check: if medians differ by more than the max IQR, we consider it significant.
        # This is a very simplified heuristic for significance to keep it zero-config and robust.
        max_iqr = max(iqr_a, iqr_b)
        diff = abs(median_a - median_b)

        is_significant = False
        if max_iqr > 0 and diff > (max_iqr * 1.5): # 1.5 IQR rule of thumb
            is_significant = True
        elif max_iqr == 0 and diff > 0:
            is_significant = True

        winner = "A" if median_a < median_b else ("B" if median_b < median_a else "Tie")

        # Frontend gets a clean net result
        return {
            "winner": winner,
            "median_A": median_a,
            "median_B": median_b,
            "iqr_A": iqr_a,
            "iqr_B": iqr_b,
            "is_significant": is_significant,
            "iterations_run": self.iterations
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Returns the background full-link traceable audit log."""
        return self.audit_log

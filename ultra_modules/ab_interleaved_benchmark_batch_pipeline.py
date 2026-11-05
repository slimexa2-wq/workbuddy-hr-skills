import concurrent.futures
import time
import math
import threading
from typing import List, Callable, Any, Dict, Optional, Tuple

class ABInterleavedBenchmarkBatchPipeline:
    """
    ABBA Interleaved Benchmark Batch Pipeline.
    Supports high-throughput streaming (10~1000 records), progress snapshot, non-blocking summary,
    and median/IQR non-parametric significance testing.
    """
    def __init__(self,
                 func_a: Optional[Callable] = None,
                 func_b: Optional[Callable] = None,
                 concurrency: int = 4):
        # 缺参自动设合理默认值 (Fallback for missing params)
        self.func_a = func_a if callable(func_a) else (lambda x: time.sleep(0.001))
        self.func_b = func_b if callable(func_b) else (lambda x: time.sleep(0.001))

        # Handle invalid concurrency parameter
        if not isinstance(concurrency, int) or concurrency <= 0:
            self.concurrency = 4
        else:
            self.concurrency = concurrency

        self.results_a: List[float] = []
        self.results_b: List[float] = []
        self.errors: List[str] = []

        self.processed_count = 0
        self.total_count = 0

        self._lock = threading.Lock()
        self._executor = None
        self._futures = []

    def add_batch(self, inputs: Any) -> None:
        """支持单次拖入10~1000条记录的批量流式处理"""
        # 脏数据自愈 (Self-healing dirty data)
        if inputs is None:
            return
        if not isinstance(inputs, list):
            inputs = [inputs]

        if not inputs:
            return

        with self._lock:
            start_index = self.total_count
            self.total_count += len(inputs)

            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency)

        # ABBA sequence pattern: A B B A
        abba_sequence = ['AB', 'BA', 'BA', 'AB']

        for i, item in enumerate(inputs):
            pattern = abba_sequence[(start_index + i) % 4]
            future = self._executor.submit(self._process_item, item, pattern)
            with self._lock:
                self._futures.append(future)

    def _process_item(self, item: Any, pattern: str) -> None:
        try:
            time_a = 0.0
            time_b = 0.0

            if pattern == 'AB':
                start = time.perf_counter()
                self.func_a(item)
                time_a = time.perf_counter() - start

                start = time.perf_counter()
                self.func_b(item)
                time_b = time.perf_counter() - start
            else:
                start = time.perf_counter()
                self.func_b(item)
                time_b = time.perf_counter() - start

                start = time.perf_counter()
                self.func_a(item)
                time_a = time.perf_counter() - start

            with self._lock:
                self.results_a.append(time_a)
                self.results_b.append(time_b)
                self.processed_count += 1
        except Exception as e:
            with self._lock:
                self.errors.append(f"Error processing item: {str(e)}")
                self.processed_count += 1

    def get_snapshot(self) -> Dict[str, Any]:
        """进度快照与零阻塞结果汇总"""
        with self._lock:
            processed = self.processed_count
            total = self.total_count
            a_times = list(self.results_a)
            b_times = list(self.results_b)
            err_count = len(self.errors)

        progress = (processed / total) if total > 0 else 1.0

        stats = self._compute_stats(a_times, b_times)

        return {
            "progress": progress,
            "processed": processed,
            "total": total,
            "errors": err_count,
            "stats": stats
        }

    def wait_completion(self) -> None:
        """Wait for all tasks to complete"""
        if self._futures:
            concurrent.futures.wait(self._futures)

    def shutdown(self) -> None:
        """Shutdown the executor"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    def _compute_stats(self, a_times: List[float], b_times: List[float]) -> Dict[str, Any]:
        if not a_times or not b_times:
            return {
                "a_median": 0.0, "a_iqr": 0.0,
                "b_median": 0.0, "b_iqr": 0.0,
                "significant": False, "p_value": 1.0
            }

        def get_median_iqr(data: List[float]) -> Tuple[float, float]:
            n = len(data)
            if n == 0: return 0.0, 0.0
            if n == 1: return data[0], 0.0
            sdata = sorted(data)

            def quantile(q: float) -> float:
                pos = (n - 1) * q
                idx = int(pos)
                frac = pos - idx
                if idx + 1 < n:
                    return sdata[idx] + (sdata[idx+1] - sdata[idx]) * frac
                return sdata[idx]

            median = quantile(0.5)
            q1 = quantile(0.25)
            q3 = quantile(0.75)
            return median, (q3 - q1)

        a_med, a_iqr = get_median_iqr(a_times)
        b_med, b_iqr = get_median_iqr(b_times)

        # Mann-Whitney U test (asymptotic normal approximation)
        n1 = len(a_times)
        n2 = len(b_times)

        if n1 == 0 or n2 == 0:
            return {
                "a_median": a_med, "a_iqr": a_iqr,
                "b_median": b_med, "b_iqr": b_iqr,
                "significant": False, "p_value": 1.0
            }

        combined = [(v, 1) for v in a_times] + [(v, 2) for v in b_times]
        combined.sort(key=lambda x: x[0])

        ranks = [0.0] * len(combined)
        i = 0
        while i < len(combined):
            j = i
            while j < len(combined) and combined[j][0] == combined[i][0]:
                j += 1
            avg_rank = sum(range(i + 1, j + 1)) / (j - i)
            for k in range(i, j):
                ranks[k] = avg_rank
            i = j

        rank_sum_a = sum(ranks[k] for k, x in enumerate(combined) if x[1] == 1)

        u1 = rank_sum_a - n1 * (n1 + 1) / 2
        u2 = n1 * n2 - u1

        u = min(u1, u2)

        mean_u = n1 * n2 / 2.0
        std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)

        if std_u == 0:
            p_value = 1.0
            significant = False
        else:
            z = (u - mean_u) / std_u
            p_value = math.erfc(abs(z) / math.sqrt(2))
            significant = bool(p_value < 0.05)

        return {
            "a_median": a_med,
            "a_iqr": a_iqr,
            "b_median": b_med,
            "b_iqr": b_iqr,
            "significant": significant,
            "p_value": p_value
        }

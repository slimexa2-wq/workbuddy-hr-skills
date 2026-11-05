import time
import math
from typing import Dict, List, Any

class _Snapshot:
    def __init__(self, data_a: List[float], data_b: List[float], timestamp: float):
        self.data_a = list(data_a)
        self.data_b = list(data_b)
        self.timestamp = timestamp

class ABInterleavedBenchmarkGuard:
    """
    AB Interleaved Benchmark Self-Healing Guard.
    Silent self-healing of data with non-parametric statistics (Median, IQR, Mann-Whitney U).
    Includes a 5-second lightweight snapshot undo mechanism.
    """
    def __init__(self, undo_window: float = 5.0):
        self.data_a: List[float] = []
        self.data_b: List[float] = []
        self.snapshots: List[_Snapshot] = []
        self.undo_window = undo_window

    def _save_snapshot(self) -> None:
        current_time = time.time()
        self.snapshots.append(_Snapshot(self.data_a, self.data_b, current_time))
        # Keep only snapshots within the time window
        self.snapshots = [s for s in self.snapshots if current_time - s.timestamp <= self.undo_window]

    def add_data(self, group: Any = 'A', value: Any = 0.0) -> None:
        self._save_snapshot()

        # Self-healing group name
        try:
            group_str = str(group).strip().upper()
            if group_str not in ('A', 'B'):
                group_str = 'A'  # default fallback
        except Exception:
            group_str = 'A'

        # Self-healing value
        try:
            val_float = float(value)
            if math.isnan(val_float) or math.isinf(val_float):
                val_float = 0.0
        except Exception:
            val_float = 0.0

        if group_str == 'A':
            self.data_a.append(val_float)
        else:
            self.data_b.append(val_float)

    def undo(self) -> bool:
        """
        Reverts the state to the most recent snapshot within the undo window.
        Returns True if successful, False otherwise.
        """
        current_time = time.time()
        self.snapshots = [s for s in self.snapshots if current_time - s.timestamp <= self.undo_window]

        if not self.snapshots:
            return False

        last_snapshot = self.snapshots.pop()
        self.data_a = list(last_snapshot.data_a)
        self.data_b = list(last_snapshot.data_b)
        return True

    def analyze(self) -> Dict[str, Any]:
        """
        Performs non-parametric analysis (Median, IQR, simplified Mann-Whitney U).
        """
        def get_median_iqr(arr: List[float]):
            if not arr:
                return 0.0, 0.0
            sorted_arr = sorted(arr)
            n = len(sorted_arr)
            def _median(lst: List[float]) -> float:
                ln = len(lst)
                if ln == 0: return 0.0
                if ln % 2 == 1:
                    return lst[ln // 2]
                return (lst[ln // 2 - 1] + lst[ln // 2]) / 2.0

            med = _median(sorted_arr)
            if n == 1:
                return med, 0.0

            q1 = _median(sorted_arr[:n // 2])
            q3 = _median(sorted_arr[(n + 1) // 2:])
            return med, q3 - q1

        med_a, iqr_a = get_median_iqr(self.data_a)
        med_b, iqr_b = get_median_iqr(self.data_b)

        u_stat = 0.0
        p_value = 1.0
        n1, n2 = len(self.data_a), len(self.data_b)

        if n1 > 0 and n2 > 0:
            combined = [(val, 1) for val in self.data_a] + [(val, 2) for val in self.data_b]
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

            rank_sum_1 = sum(r for k, r in enumerate(ranks) if combined[k][1] == 1)
            u1 = rank_sum_1 - n1 * (n1 + 1) / 2
            u2 = n1 * n2 - u1
            u_stat = min(u1, u2)

            mean_u = n1 * n2 / 2.0
            std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)

            if std_u > 0:
                z = (u_stat - mean_u) / std_u
                # 2-tailed p-value from normal CDF
                p_value = 2.0 * (0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))

        return {
            'group_a': {'median': med_a, 'iqr': iqr_a, 'count': n1},
            'group_b': {'median': med_b, 'iqr': iqr_b, 'count': n2},
            'u_statistic': u_stat,
            'p_value': p_value,
            'significant': p_value < 0.05
        }

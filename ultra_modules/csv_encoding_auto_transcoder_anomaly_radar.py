import csv
import io
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class CSVTranscoderAnomalyRadar:
    """
    GBK/GB18030/UTF-8-SIG Salary & Attendance CSV One-Click Transcoder & Anomaly Cleaner.
    Features:
    1. Zero-config encoding fallback.
    2. Z-Score/IQR-based anomaly detection on numeric data.
    3. Silent cleaning for normal data (97%), red/yellow tags for top 3% anomalies.
    """
    def __init__(self, target_encoding: str = 'utf-8', anomaly_threshold_percent: float = 3.0):
        self.target_encoding = target_encoding
        self.anomaly_threshold_percent = anomaly_threshold_percent

    def _auto_decode(self, raw_bytes: bytes) -> str:
        """
        Zero-config encoding fallback.
        Tries UTF-8-SIG, UTF-8, GB18030, GBK, etc., silently repairing dirty text.
        """
        encodings_to_try = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'gb2312', 'latin1']
        for enc in encodings_to_try:
            try:
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        # Fallback to replace
        return raw_bytes.decode('utf-8', errors='replace')

    def _clean_numeric(self, val: str) -> Optional[float]:
        if val is None:
            return None
        try:
            # Silent dirty data self-healing: handle commas, currency symbols, spaces
            cleaned = str(val).replace(',', '').replace('$', '').replace('¥', '').strip()
            if not cleaned:
                return None
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _percentile(self, data: List[float], percentile: float) -> float:
        n = len(data)
        if n == 0:
            return 0.0
        if n == 1:
            return data[0]
        data_sorted = sorted(data)
        k = (n - 1) * percentile
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data_sorted[int(k)]
        d0 = data_sorted[int(f)] * (c - k)
        d1 = data_sorted[int(c)] * (k - f)
        return d0 + d1

    def _detect_anomalies(self, data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using IQR on numeric columns.
        Mark Top N% as Red/Yellow, others Green (silent pass).
        """
        if not data:
            return []

        # 1. Identify numeric columns robustly
        columns = list(data[0].keys())
        numeric_cols = []
        for col in columns:
            if not col:
                continue
            valid_count = 0
            total_count = 0
            for row in data:
                val = row.get(col, '')
                if val:
                    total_count += 1
                    if self._clean_numeric(val) is not None:
                        valid_count += 1
            if total_count > 0 and (valid_count / total_count) > 0.5:
                numeric_cols.append(col)

        # 2. Extract values and compute statistics without external libs like pandas/numpy
        col_stats = {}
        for col in numeric_cols:
            vals = []
            for i, row in enumerate(data):
                val = self._clean_numeric(row.get(col, ''))
                if val is not None:
                    vals.append((i, val))

            if len(vals) < 3:
                continue # Need minimum data points for meaningful IQR

            just_vals = [v for _, v in vals]
            q1 = self._percentile(just_vals, 0.25)
            q3 = self._percentile(just_vals, 0.75)
            iqr = q3 - q1

            # Using standard IQR method
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            deviations = []
            for idx, val in vals:
                dev = 0
                if val > upper_bound and iqr > 0:
                    dev = (val - upper_bound) / iqr
                elif val < lower_bound and iqr > 0:
                    dev = (lower_bound - val) / iqr
                deviations.append((idx, val, dev))

            col_stats[col] = {
                'q1': q1,
                'q3': q3,
                'iqr': iqr,
                'lower': lower_bound,
                'upper': upper_bound,
                'deviations': deviations
            }

        # 3. Highlight top N% anomalies and auto-mark the rest as normal
        results = []
        total_rows = len(data)
        top_k = max(1, math.ceil(total_rows * (self.anomaly_threshold_percent / 100.0)))

        all_anomalies = []
        for col, stats in col_stats.items():
            for idx, val, dev in stats['deviations']:
                if dev > 0:
                    all_anomalies.append({
                        'idx': idx,
                        'col': col,
                        'val': val,
                        'dev': dev,
                        'stats': stats
                    })

        # Sort globally by severity deviation
        all_anomalies.sort(key=lambda x: x['dev'], reverse=True)

        top_unique_rows = []
        seen_idx = set()
        for anomaly in all_anomalies:
            if anomaly['idx'] not in seen_idx:
                top_unique_rows.append(anomaly)
                seen_idx.add(anomaly['idx'])
            if len(top_unique_rows) >= top_k:
                break

        top_anomalies = top_unique_rows
        top_indices = {x['idx']: x for x in top_anomalies}

        for i, row in enumerate(data):
            processed_row = {
                'original_data': row,
                'status': '🟢正常',
                'anomaly_reason': '',
            }

            if i in top_indices:
                anomaly = top_indices[i]
                col = anomaly['col']
                val = anomaly['val']
                stats = anomaly['stats']

                rank = top_anomalies.index(anomaly)
                is_red = rank < max(1, (len(top_anomalies) / 2))

                status_color = '🔴严重异常' if is_red else '🟡关注异常'

                if val > stats['upper']:
                    reason = f"【{col}】数值({val})畸高，远超正常上限({stats['upper']:.2f})，请核实是否多发或录入错误。"
                else:
                    reason = f"【{col}】数值({val})畸低，低于正常下限({stats['lower']:.2f})，请核实是否少发或扣款异常。"

                processed_row['status'] = status_color
                processed_row['anomaly_reason'] = reason

            results.append(processed_row)

        return results

    def process_csv_bytes(self, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """
        One-click entry point. Handles transcoding, cleaning, and anomaly scanning silently.
        """
        if not raw_bytes:
            return []

        decoded_text = self._auto_decode(raw_bytes)

        reader = csv.DictReader(io.StringIO(decoded_text))
        if not reader.fieldnames:
            return []

        # Clean BOM and whitespace from headers
        fieldnames = [str(f).strip('\ufeff').strip() for f in reader.fieldnames if f]
        reader.fieldnames = fieldnames

        data = []
        for row in reader:
            clean_row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
            if any(clean_row.values()): # Ignore completely empty rows
                data.append(clean_row)

        return self._detect_anomalies(data)

def process_payroll_csv(raw_csv_bytes: bytes = b'', target_encoding: str = 'utf-8', anomaly_threshold: float = 3.0) -> List[Dict[str, Any]]:
    """
    Zero-config global API function for external usage.
    Missing parameter fallbacks apply by default.
    """
    radar = CSVTranscoderAnomalyRadar(target_encoding, anomaly_threshold)
    return radar.process_csv_bytes(raw_csv_bytes)

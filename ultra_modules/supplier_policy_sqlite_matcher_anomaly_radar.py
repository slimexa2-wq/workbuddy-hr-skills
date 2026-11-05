import sqlite3
import math
import logging

logger = logging.getLogger(__name__)

class SupplierPolicyAnomalyRadar:
    """
    SQLite-based policy matcher and anomaly radar.
    Matches supplier policies in milliseconds, strictly handles dirty data (missing parameters default safely),
    and silently scans for anomalies using Z-Score and IQR to find absolute deviations.
    Highlights true anomalies within the top 3% deviations.
    """
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_role TEXT,
                tier INTEGER,
                start_date TEXT,
                end_date TEXT,
                standard_price REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_policies ON policies (job_role, tier, start_date, end_date)")
        self.conn.commit()

    def load_policies(self, policies):
        """
        Loads policies, handling dirty data silently.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM policies")
        for policy in policies:
            if not isinstance(policy, dict):
                continue

            job_role = policy.get('job_role')
            if not job_role or not isinstance(job_role, str):
                job_role = '通用工种'

            try:
                tier = int(policy.get('tier', 1))
            except (ValueError, TypeError):
                tier = 1

            start_date = policy.get('start_date')
            if not start_date or not isinstance(start_date, str):
                start_date = '1970-01-01'

            end_date = policy.get('end_date')
            if not end_date or not isinstance(end_date, str):
                end_date = '2999-12-31'

            try:
                standard_price = float(policy.get('standard_price', 0.0))
            except (ValueError, TypeError):
                standard_price = 0.0

            cursor.execute("""
                INSERT INTO policies (job_role, tier, start_date, end_date, standard_price)
                VALUES (?, ?, ?, ?, ?)
            """, (job_role, tier, start_date, end_date, standard_price))
        self.conn.commit()

    def process_records(self, records):
        """
        Matches incoming records, calculates deviations, flags top 3% anomalies.
        Returns a clean list of dicts.
        """
        if not records:
            return []

        cursor = self.conn.cursor()

        processed_records = []
        deviations = []

        for record in records:
            if not isinstance(record, dict):
                record = {}

            job_role = record.get('job_role')
            if not job_role or not isinstance(job_role, str):
                job_role = '通用工种'

            try:
                tier = int(record.get('tier', 1))
            except (ValueError, TypeError):
                tier = 1

            date = record.get('date')
            if not date or not isinstance(date, str):
                date = '2099-01-01'

            try:
                unit_price = float(record.get('unit_price', 0.0))
            except (ValueError, TypeError):
                unit_price = 0.0

            # Find matching policy
            cursor.execute("""
                SELECT standard_price
                FROM policies
                WHERE job_role = ? AND tier = ? AND ? >= start_date AND ? <= end_date
                ORDER BY standard_price DESC
                LIMIT 1
            """, (job_role, tier, date, date))

            row = cursor.fetchone()
            standard_price = row['standard_price'] if row else 0.0

            deviation = abs(unit_price - standard_price)

            processed_record = {
                'original_record': record,
                'job_role': job_role,
                'tier': tier,
                'date': date,
                'unit_price': unit_price,
                'standard_price': standard_price,
                'deviation': deviation
            }
            processed_records.append(processed_record)
            deviations.append(deviation)

        # Anomaly Detection stats
        n = len(deviations)
        if n > 1:
            mean = sum(deviations) / n
            variance = sum((x - mean) ** 2 for x in deviations) / n
            std_dev = math.sqrt(variance)

            sorted_devs = sorted(deviations)
            q1_idx = int(0.25 * n)
            q3_idx = int(0.75 * n)
            q1 = sorted_devs[q1_idx]
            q3 = sorted_devs[q3_idx]
            iqr = q3 - q1
            upper_bound_iqr = q3 + 1.5 * iqr
        else:
            mean = deviations[0] if deviations else 0.0
            std_dev = 0.0
            upper_bound_iqr = deviations[0] if deviations else 0.0

        top_3_count = max(1, math.ceil(n * 0.03)) if n >= 33 else (1 if n > 0 else 0)

        sorted_records = sorted(processed_records, key=lambda x: x['deviation'], reverse=True)
        top_3_ids = {id(r) for r in sorted_records[:top_3_count]}

        result = []
        for record in processed_records:
            is_top_3 = id(record) in top_3_ids
            dev = record['deviation']
            std_price = record['standard_price']

            status = 'green'
            reason = ''

            if is_top_3 and n > 1 and dev > 0:
                z_score = (dev - mean) / std_dev if std_dev > 0 else 0
                is_iqr_anomaly = dev > upper_bound_iqr

                # Big deviation rules
                if z_score > 3 or (is_iqr_anomaly and (std_price == 0 or dev / std_price > 0.5)):
                    status = 'red'
                    reason = '单价严重偏离标准价，偏差非常大，建议重点核对是否填错'
                elif z_score > 2 or (is_iqr_anomaly and (std_price == 0 or dev / std_price > 0.2)):
                    status = 'yellow'
                    reason = '单价与标准价相差较大，存在异常波动，需要人工关注'

            clean_record = record['original_record'].copy()
            clean_record['status'] = status
            if status != 'green':
                clean_record['reason'] = reason

            result.append(clean_record)

        return result

    def close(self):
        self.conn.close()

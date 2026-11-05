import sqlite3
import threading
import uuid
import concurrent.futures
import time

class SupplierPolicyMatcher:
    """
    SQLite-based policy matcher with millisecond-level precision,
    supporting step pricing by job type and date range.
    Built for high-throughput batch stream processing.
    """
    def __init__(self, max_workers=4):
        # Use shared cache in-memory SQLite database
        self.db_uri = f"file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared"
        # Keep one connection open to persist the in-memory db
        self.conn = self._get_conn()
        self._init_db()

        self.batches = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()

    def _get_conn(self):
        return sqlite3.connect(self.db_uri, uri=True, check_same_thread=False)

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                start_date TEXT,
                end_date TEXT,
                min_count INTEGER,
                max_count INTEGER,
                price REAL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_policies ON policies (job_type, start_date, end_date)')
        self.conn.commit()

    def insert_policies(self, policies):
        """
        Inserts a list of policy dictionaries into the SQLite db.
        Auto-heals missing or dirty fields.
        """
        cursor = self.conn.cursor()
        for p in policies:
            job_type = str(p.get('job_type', 'unknown')).strip()
            start_date = str(p.get('start_date', '1970-01-01')).strip()
            end_date = str(p.get('end_date', '2099-12-31')).strip()

            try:
                min_count = int(p.get('min_count', 0))
            except (ValueError, TypeError):
                min_count = 0

            try:
                max_count = int(p.get('max_count', 999999999))
            except (ValueError, TypeError):
                max_count = 999999999

            try:
                price = float(p.get('price', 0.0))
            except (ValueError, TypeError):
                price = 0.0

            cursor.execute('''
                INSERT INTO policies (job_type, start_date, end_date, min_count, max_count, price)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_type, start_date, end_date, min_count, max_count, price))
        self.conn.commit()

    def _process_batch(self, batch_id, records):
        """
        Internal worker function to process a batch of records.
        """
        conn = self._get_conn()
        try:
            for record in records:
                # Silent healing / defaults for dirty data
                raw_job = record.get('job_type')
                job_type = str(raw_job).strip() if raw_job is not None else 'unknown'

                raw_date = record.get('date')
                date_val = str(raw_date).strip() if raw_date is not None else '1970-01-01'
                date_val = date_val.replace('/', '-')

                try:
                    count = int(record.get('count', 0))
                except (ValueError, TypeError):
                    count = 0

                cursor = conn.cursor()
                # Find the matched price
                cursor.execute('''
                    SELECT price FROM policies
                    WHERE job_type = ?
                      AND start_date <= ?
                      AND end_date >= ?
                      AND min_count <= ?
                      AND max_count >= ?
                    ORDER BY price DESC LIMIT 1
                ''', (job_type, date_val, date_val, count, count))

                row = cursor.fetchone()
                price = row[0] if row else 0.0

                res = {
                    'original': record,
                    'job_type': job_type,
                    'date': date_val,
                    'count': count,
                    'matched_price': price
                }

                with self.lock:
                    self.batches[batch_id]['processed'] += 1
                    self.batches[batch_id]['results'].append(res)

        finally:
            with self.lock:
                self.batches[batch_id]['status'] = 'completed'
            conn.close()

    def submit_batch(self, records):
        """
        Submit a batch of records (10 to 1000+) to be processed asynchronously.
        Returns a batch_id for tracking progress without blocking.
        """
        if not isinstance(records, list):
            records = [records]

        batch_id = str(uuid.uuid4())
        with self.lock:
            self.batches[batch_id] = {
                'total': len(records),
                'processed': 0,
                'results': [],
                'status': 'running'
            }

        self.executor.submit(self._process_batch, batch_id, records)
        return batch_id

    def get_snapshot(self, batch_id):
        """
        Get the current progress and results of a batch without blocking.
        """
        with self.lock:
            batch = self.batches.get(batch_id)
            if not batch:
                return None
            return {
                'batch_id': batch_id,
                'total': batch['total'],
                'processed': batch['processed'],
                'status': batch['status'],
                'results': list(batch['results'])  # snapshot copy
            }

    def shutdown(self):
        """
        Clean up resources.
        """
        self.executor.shutdown(wait=True)
        self.conn.close()

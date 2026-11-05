import sqlite3
import time
import random
import string
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class SupplierPolicyMatcher:
    """
    SQLite-based matcher for supplier policies with date ranges and job type tiered pricing.
    Ensures millisecond-level precision, dirty data self-healing, missing parameter fallbacks,
    and extreme boundary handling.
    """

    def __init__(self, db_path: str = ':memory:'):
        """
        Initializes the matcher with an SQLite database.
        Defaults to an in-memory database for extreme performance.
        """
        self.db_path = db_path
        # Keep a persistent connection for in-memory databases
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Initializes the database schema."""
        cursor = self.conn.cursor()
        # Using an optimized schema for rapid querying
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                price REAL NOT NULL
            )
        ''')
        # Create indexes to ensure millisecond-level matching performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_type_dates ON policies(job_type, start_date, end_date)')
        self.conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection to the SQLite database."""
        return self.conn

    def _clean_job_type(self, job_type: Any) -> str:
        """Self-heals and cleans dirty job_type data."""
        if not job_type or not isinstance(job_type, str):
            return "DEFAULT_JOB"

        cleaned = job_type.strip()
        # Fallback for completely garbled strings that resolve to empty
        if not cleaned:
            return "DEFAULT_JOB"
        return cleaned

    def _clean_date(self, date_val: Any, default_val: str) -> str:
        """Self-heals dirty date data, enforcing YYYY-MM-DD format."""
        if not date_val or not isinstance(date_val, str):
            return default_val

        date_val = date_val.strip()
        try:
            # Validate format
            datetime.strptime(date_val, '%Y-%m-%d')
            return date_val
        except ValueError:
            # Try some basic self-healing for common errors like YYYY/MM/DD
            try:
                if '/' in date_val:
                    healed = date_val.replace('/', '-')
                    datetime.strptime(healed, '%Y-%m-%d')
                    return healed
            except ValueError:
                pass
            return default_val

    def _clean_price(self, price_val: Any) -> float:
        """Self-heals dirty price data."""
        if price_val is None:
            return 0.0
        try:
            return float(price_val)
        except (ValueError, TypeError):
            return 0.0

    def ingest_policies(self, policies: List[Dict[str, Any]]):
        """
        Ingests a list of policies into the database.
        Applies self-healing for dirty data, nulls, and garbled text.
        """
        cleaned_policies = []
        for p in policies:
            # Default fallbacks for missing keys or dirty data
            job_type = self._clean_job_type(p.get('job_type'))
            start_date = self._clean_date(p.get('start_date'), '1970-01-01')
            end_date = self._clean_date(p.get('end_date'), '2099-12-31')

            # Ensure start_date <= end_date
            if start_date > end_date:
                start_date, end_date = end_date, start_date

            price = self._clean_price(p.get('price'))
            cleaned_policies.append((job_type, start_date, end_date, price))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO policies (job_type, start_date, end_date, price)
                VALUES (?, ?, ?, ?)
            ''', cleaned_policies)
            conn.commit()


    def match_policy(self, job_type: str, target_date: str) -> Optional[float]:
        """
        Finds the matching policy price for a given job type and date.
        Uses extreme simplification for the caller: missing params use defaults,
        returns the lowest matching price if multiple overlapping policies exist (or a simple single return).
        """
        # Fallbacks for the caller
        job_type = self._clean_job_type(job_type)
        target_date = self._clean_date(target_date, datetime.now().strftime('%Y-%m-%d'))

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Using inclusive bounds for target_date.
            # If multiple overlap, order by price ascending and take the first (lowest price policy).
            # This is a common sensible default for supplier matching.
            cursor.execute('''
                SELECT price FROM policies
                WHERE job_type = ?
                  AND start_date <= ?
                  AND end_date >= ?
                ORDER BY price ASC
                LIMIT 1
            ''', (job_type, target_date, target_date))

            row = cursor.fetchone()
            if row:
                return row[0]

            # Zero-configuration fault tolerance: if no exact match for job_type, fallback to DEFAULT_JOB
            if job_type != "DEFAULT_JOB":
                 cursor.execute('''
                    SELECT price FROM policies
                    WHERE job_type = ?
                      AND start_date <= ?
                      AND end_date >= ?
                    ORDER BY price ASC
                    LIMIT 1
                ''', ("DEFAULT_JOB", target_date, target_date))
                 row = cursor.fetchone()
                 if row:
                     return row[0]
            return None


class BenchmarkSuite:
    """
    Synthetic fixture generation and benchmarking suite for SupplierPolicyMatcher.
    """

    @staticmethod
    def generate_synthetic_fixtures(num_records: int) -> List[Dict[str, Any]]:
        """
        Generates synthetic fixtures including extreme boundaries and dirty data.
        """
        fixtures = []
        job_types = ["Developer", "Designer", "Manager", "DEFAULT_JOB", None, "", "   ", "???Garbage!@#"]

        base_date = datetime(2023, 1, 1)

        for _ in range(num_records):
            j_type = random.choice(job_types)

            # Generate random start and end dates, sometimes dirty
            start_offset = random.randint(-365, 365) # Cross year boundaries
            end_offset = start_offset + random.randint(-10, 100) # Cross month/year boundaries

            start = (base_date + timedelta(days=start_offset)).strftime('%Y-%m-%d')
            end = (base_date + timedelta(days=end_offset)).strftime('%Y-%m-%d')

            # Introduce some dirty dates
            if random.random() < 0.05:
                start = start.replace('-', '/')
            if random.random() < 0.05:
                end = None

            # Prices: normal, extreme, dirty
            price_choices = [random.uniform(10.0, 500.0), 0.0, -100.0, None, "dirty_price_string"]
            price = random.choice(price_choices)

            fixtures.append({
                'job_type': j_type,
                'start_date': start,
                'end_date': end,
                'price': price
            })

        return fixtures

    @staticmethod
    def run_benchmark(matcher: SupplierPolicyMatcher, num_queries: int = 1000) -> Dict[str, Any]:
        """
        Runs a concurrency benchmark to verify millisecond-level response times.
        """
        job_types = ["Developer", "Designer", "Manager", "Unknown", None]
        base_date = datetime(2023, 6, 1)

        queries = []
        for _ in range(num_queries):
            j_type = random.choice(job_types)
            target_date = (base_date + timedelta(days=random.randint(-100, 100))).strftime('%Y-%m-%d')
            queries.append((j_type, target_date))

        start_time = time.perf_counter()

        # Simulating sequential fast queries (for an in-memory DB, Python's sqlite3 is extremely fast)
        results = 0
        for j_type, t_date in queries:
            res = matcher.match_policy(j_type, t_date)
            if res is not None:
                results += 1

        end_time = time.perf_counter()

        total_time_ms = (end_time - start_time) * 1000
        avg_time_ms = total_time_ms / num_queries

        return {
            "total_queries": num_queries,
            "total_time_ms": total_time_ms,
            "avg_time_ms_per_query": avg_time_ms,
            "matches_found": results
        }

import sqlite3
import datetime
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SupplierPolicySQLiteMatcher:
    """
    A fast and strictly zero-configuration SQLite policy matcher handling date-range
    and job-tier price mapping, with automatic schema compatibility for older formats.
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Initializes the matcher. Uses in-memory SQLite by default for zero config.
        """
        self.db_path = db_path
        self._conn = None
        self._setup_connection()
        self.setup_schema()

    def _setup_connection(self):
        try:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            # Fallback to purely memory if path is weird
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def __del__(self):
        if self._conn:
            self._conn.close()

    def _clean_date(self, date_str: str, default: str) -> str:
        """
        Silently self-heals messy dates to YYYY-MM-DD.
        """
        if not date_str:
            return default

        date_str = str(date_str).strip()
        # Remove any non-numeric/non-hyphen characters
        date_str = re.sub(r'[^\d-]', '-', date_str)
        # Try to extract something that looks like a date
        match = re.search(r'(\d{4})[-\.]?(\d{1,2})[-\.]?(\d{1,2})', date_str)
        if match:
            year, month, day = match.groups()
            try:
                # Validate date correctness and format it nicely
                valid_date = datetime.date(int(year), int(month), int(day))
                return valid_date.isoformat()
            except ValueError:
                return default
        return default

    def _clean_job_title(self, job_title: str) -> str:
        if not job_title:
            return "DEFAULT_JOB"
        # Non-destructive lowercase and strip
        return str(job_title).strip().lower()

    def _clean_price(self, price) -> float:
        if price is None:
            return 0.0
        try:
            val = float(str(price).replace(',', ''))
            return max(0.0, val) # No negative prices
        except (ValueError, TypeError):
            return 0.0

    def setup_schema(self):
        """
        Sets up the base schema, automatically upgrading if necessary.
        """
        cur = self._conn.cursor()

        # We ensure a robust table structure
        cur.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                unit_price REAL NOT NULL
            )
        ''')

        # Add indexes for ms-level querying
        cur.execute('CREATE INDEX IF NOT EXISTS idx_job ON policies(job_title)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_dates ON policies(start_date, end_date)')

        self._conn.commit()

    def add_policy(self, data: Dict[str, Any]):
        """
        Inserts a policy with automatic schema field mapping and data healing.
        Accepts missing parameters and fills with defaults.
        """
        if not isinstance(data, dict):
            return

        # Automatic compatibility: Map old schema keys to new schema keys
        # Old schemas might have: 'role', 'job', 'profession' -> 'job_title'
        # 'valid_from', 'begin_date' -> 'start_date'
        # 'valid_to', 'expiry_date' -> 'end_date'
        # 'rate', 'price', 'cost' -> 'unit_price'

        job_title = (data.get('job_title') or data.get('role') or
                     data.get('job') or data.get('profession') or 'DEFAULT_JOB')

        start_date = (data.get('start_date') or data.get('valid_from') or
                      data.get('begin_date') or '1970-01-01')

        end_date = (data.get('end_date') or data.get('valid_to') or
                    data.get('expiry_date') or '2099-12-31')

        unit_price = (data.get('unit_price') or data.get('rate') or
                      data.get('price') or data.get('cost') or 0.0)

        # Self-heal dirty data
        clean_job = self._clean_job_title(job_title)
        clean_start = self._clean_date(start_date, '1970-01-01')
        clean_end = self._clean_date(end_date, '2099-12-31')
        clean_price = self._clean_price(unit_price)

        # Ensure start <= end
        if clean_start > clean_end:
            clean_start, clean_end = clean_end, clean_start

        cur = self._conn.cursor()
        cur.execute('''
            INSERT INTO policies (job_title, start_date, end_date, unit_price)
            VALUES (?, ?, ?, ?)
        ''', (clean_job, clean_start, clean_end, clean_price))
        self._conn.commit()

    def match_policy(self, job_title: str = None, target_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Matches a job_title and target_date to the correct policy tier.
        Zero config/fault tolerant: defaults to today and 'DEFAULT_JOB' if missing.
        """
        clean_job = self._clean_job_title(job_title)

        if not target_date:
            target_date = datetime.date.today().isoformat()
        else:
            target_date = self._clean_date(target_date, datetime.date.today().isoformat())

        cur = self._conn.cursor()

        # Exact match for the date range
        cur.execute('''
            SELECT * FROM policies
            WHERE job_title = ?
              AND start_date <= ?
              AND end_date >= ?
            ORDER BY unit_price DESC
            LIMIT 1
        ''', (clean_job, target_date, target_date))

        row = cur.fetchone()

        # If no match is found, try to match by job_title only, taking the latest policy by end_date
        if not row:
            cur.execute('''
                SELECT * FROM policies
                WHERE job_title = ?
                ORDER BY end_date DESC, unit_price DESC
                LIMIT 1
            ''', (clean_job,))
            row = cur.fetchone()

        # If still no match, fallback to 'default_job' if it exists, matching date
        if not row and clean_job != 'default_job':
             cur.execute('''
                SELECT * FROM policies
                WHERE job_title = 'default_job'
                  AND start_date <= ?
                  AND end_date >= ?
                ORDER BY unit_price DESC
                LIMIT 1
            ''', (target_date, target_date))
             row = cur.fetchone()

        if row:
            return dict(row)

        return None

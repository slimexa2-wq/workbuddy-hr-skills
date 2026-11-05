import sqlite3
import time
import shutil
import os
import datetime
import re
from typing import Any

class SupplierPolicyMatcher:
    """
    SQLite原始政策库按日期区间与工种阶梯单价毫秒级精确匹配器。
    具备异常输入静默自愈与5秒一键撤回(Undo)快照机制。
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._is_memory = (db_path == ":memory:")
        self.snapshot_path = f"{db_path}.snapshot" if not self._is_memory else None
        self.last_modify_time = 0.0

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

        self.snapshot_conn = None
        if self._is_memory:
            self.snapshot_conn = sqlite3.connect(":memory:", check_same_thread=False)

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS supplier_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    step_min INTEGER NOT NULL,
                    step_max INTEGER NOT NULL,
                    unit_price REAL NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_policy_match ON supplier_policies
                (supplier_name, job_type, start_date, end_date)
            """)

    def _take_snapshot(self):
        self.last_modify_time = time.time()
        if self._is_memory:
            self.snapshot_conn.close()
            self.snapshot_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.conn.backup(self.snapshot_conn)
        else:
            self.conn.commit()
            if os.path.exists(self.db_path):
                try:
                    if os.path.exists(self.snapshot_path):
                        os.remove(self.snapshot_path)
                    bck = sqlite3.connect(self.snapshot_path)
                    self.conn.backup(bck)
                    bck.close()
                except Exception:
                    pass

    def _heal_date(self, date_val: Any, is_start: bool) -> str:
        default_date = "1970-01-01" if is_start else "2099-12-31"
        if not date_val:
            return default_date

        s = str(date_val).strip()

        m = re.search(r'(\d{4})[-\./]?(\d{1,2})[-\./]?(\d{1,2})', s)
        if m:
            y, m_str, d = m.groups()
            try:
                dt = datetime.date(int(y), int(m_str), int(d))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return default_date
        return default_date

    def _heal_number(self, val: Any, default_val: float) -> float:
        if val is None or val == "":
            return default_val
        try:
            if isinstance(val, str):
                m = re.search(r'-?\d+(\.\d+)?', val)
                if m:
                    res = float(m.group(0))
                    if res == float('inf') or res == float('-inf'):
                        return default_val
                    return res
                return default_val
            res = float(val)
            if res == float('inf') or res == float('-inf'):
                return default_val
            return res
        except Exception:
            return default_val

    def add_policy(self, supplier_name: Any = None, job_type: Any = None,
                   start_date: Any = None, end_date: Any = None,
                   step_min: Any = None, step_max: Any = None,
                   unit_price: Any = None):
        """添加政策，包含自动修复与缺参兜底机制，自动生成快照用于撤回。"""
        self._take_snapshot()

        supplier_name = str(supplier_name).strip() if supplier_name else "DEFAULT_SUPPLIER"
        job_type = str(job_type).strip() if job_type else "DEFAULT_JOB"

        sd = self._heal_date(start_date, is_start=True)
        ed = self._heal_date(end_date, is_start=False)

        if sd > ed:
            sd, ed = ed, sd

        smin = int(self._heal_number(step_min, 0))
        smax = int(self._heal_number(step_max, 999999999))

        if smin > smax:
            smin, smax = smax, smin

        price = self._heal_number(unit_price, 0.0)

        with self.conn:
            self.conn.execute("""
                INSERT INTO supplier_policies (supplier_name, job_type, start_date, end_date, step_min, step_max, unit_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (supplier_name, job_type, sd, ed, smin, smax, price))

        return True

    def undo(self) -> bool:
        """一键撤回，时效5秒，零确认不打断"""
        if time.time() - self.last_modify_time > 5.0:
            return False

        if self._is_memory:
            if not self.snapshot_conn:
                return False
            self.conn.close()
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.snapshot_conn.backup(self.conn)
            self.last_modify_time = 0.0
            return True
        else:
            if not os.path.exists(self.snapshot_path):
                return False

            self.conn.close()
            try:
                shutil.copy(self.snapshot_path, self.db_path)
            except Exception:
                pass

            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.last_modify_time = 0.0
            return True

    def match(self, supplier_name: Any = None, job_type: Any = None, target_date: Any = None, count: Any = None) -> float:
        """按工种阶梯单价与日期区间进行毫秒级匹配"""
        supplier_name = str(supplier_name).strip() if supplier_name else "DEFAULT_SUPPLIER"
        job_type = str(job_type).strip() if job_type else "DEFAULT_JOB"

        if not target_date:
            dt_str = datetime.date.today().strftime("%Y-%m-%d")
        else:
            dt_str = self._heal_date(target_date, is_start=True)

        c = int(self._heal_number(count, 0))

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT unit_price FROM supplier_policies
            WHERE supplier_name = ?
              AND job_type = ?
              AND start_date <= ?
              AND end_date >= ?
              AND step_min <= ?
              AND step_max >= ?
            ORDER BY id DESC LIMIT 1
        """, (supplier_name, job_type, dt_str, dt_str, c, c))

        row = cursor.fetchone()
        if row:
            return row[0]
        return 0.0

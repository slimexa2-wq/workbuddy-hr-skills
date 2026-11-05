import sqlite3
import json
import uuid
import time
from datetime import datetime

class SupplierPolicyMatcher:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        # 政策表，记录各工种在各日期区间的单价
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY,
                supplier_id TEXT,
                job_type TEXT,
                start_date TEXT,
                end_date TEXT,
                price REAL
            )
        ''')
        # 审计日志表，全链路追踪
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                trace_id TEXT,
                timestamp REAL,
                action TEXT,
                details TEXT
            )
        ''')
        self.conn.commit()

    def _log_audit(self, trace_id, action, details):
        self.cursor.execute('''
            INSERT INTO audit_logs (trace_id, timestamp, action, details)
            VALUES (?, ?, ?, ?)
        ''', (trace_id, time.time(), action, json.dumps(details, ensure_ascii=False)))
        self.conn.commit()

    def _clean_date(self, date_str, default="2000-01-01"):
        if not date_str:
            return default
        try:
            # 简单验证一下格式
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            return default

    def add_policy(self, supplier_id, job_type, start_date, end_date, price):
        trace_id = str(uuid.uuid4())
        original_data = {
            "supplier_id": supplier_id,
            "job_type": job_type,
            "start_date": start_date,
            "end_date": end_date,
            "price": price
        }

        # 数据自愈：缺参默认兜底
        supplier_id = supplier_id or "default_supplier"
        job_type = job_type or "general"

        # 数据自愈：日期格式与大小校验
        cleaned_start = self._clean_date(start_date, "1970-01-01")
        cleaned_end = self._clean_date(end_date, "2099-12-31")

        if cleaned_start > cleaned_end:
            cleaned_start, cleaned_end = cleaned_end, cleaned_start # 日期反转自愈
            self._log_audit(trace_id, "data_heal", {"reason": "inverted_dates", "original": [start_date, end_date], "healed": [cleaned_start, cleaned_end]})

        # 数据自愈：价格兜底
        try:
            price = float(price)
            if price < 0:
                price = 0.0 # 负数自愈为0
                self._log_audit(trace_id, "data_heal", {"reason": "negative_price", "original": original_data["price"], "healed": price})
        except (ValueError, TypeError):
            price = 0.0
            self._log_audit(trace_id, "data_heal", {"reason": "invalid_price", "original": original_data["price"], "healed": price})

        # 去重处理，如果有完全重叠的，更新旧的
        self.cursor.execute('''
            SELECT id, price FROM policies
            WHERE supplier_id=? AND job_type=? AND start_date=? AND end_date=?
        ''', (supplier_id, job_type, cleaned_start, cleaned_end))
        existing = self.cursor.fetchone()

        policy_id = str(uuid.uuid4())
        if existing:
            old_id, old_price = existing
            if old_price != price:
                self.cursor.execute('UPDATE policies SET price=? WHERE id=?', (price, old_id))
                self._log_audit(trace_id, "dedup_update", {"old_price": old_price, "new_price": price})
            policy_id = old_id
        else:
            self.cursor.execute('''
                INSERT INTO policies (id, supplier_id, job_type, start_date, end_date, price)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (policy_id, supplier_id, job_type, cleaned_start, cleaned_end, price))
            self._log_audit(trace_id, "insert_policy", {"id": policy_id, "price": price})

        self.conn.commit()
        return policy_id

    def match_policy(self, supplier_id, job_type, target_date):
        # 匹配单价，毫秒级精确匹配
        trace_id = str(uuid.uuid4())
        supplier_id = supplier_id or "default_supplier"
        job_type = job_type or "general"
        target_date = self._clean_date(target_date, datetime.now().strftime("%Y-%m-%d"))

        start_time = time.time()

        self.cursor.execute('''
            SELECT price FROM policies
            WHERE supplier_id=? AND job_type=? AND ? >= start_date AND ? <= end_date
            ORDER BY price DESC LIMIT 1
        ''', (supplier_id, job_type, target_date, target_date))

        result = self.cursor.fetchone()
        matched_price = result[0] if result else 0.0

        cost_ms = (time.time() - start_time) * 1000

        self._log_audit(trace_id, "match_policy", {
            "params": {"supplier_id": supplier_id, "job_type": job_type, "target_date": target_date},
            "matched_price": matched_price,
            "cost_ms": cost_ms
        })

        # 前端仅展示清爽净结果
        return matched_price

    def get_audit_logs(self):
        # 用于复盘审计，前端不直接依赖
        self.cursor.execute('SELECT trace_id, timestamp, action, details FROM audit_logs ORDER BY timestamp ASC')
        return self.cursor.fetchall()

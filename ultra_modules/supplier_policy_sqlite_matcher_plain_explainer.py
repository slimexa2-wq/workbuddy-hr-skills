import sqlite3
import datetime
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SupplierPolicyMatcher:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                role TEXT NOT NULL,
                start_date DATETIME NOT NULL,
                end_date DATETIME NOT NULL,
                min_tier_count INTEGER NOT NULL,
                max_tier_count INTEGER,
                unit_price REAL NOT NULL
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_policy_search ON supplier_policies(supplier_name, role, start_date, end_date)')
        self.conn.commit()

    def insert_policy(self, supplier_name: str, role: str, start_date: str, end_date: str, min_tier_count: int, unit_price: float, max_tier_count: Optional[int] = None):
        """Insert a policy into the database."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO supplier_policies (supplier_name, role, start_date, end_date, min_tier_count, max_tier_count, unit_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (supplier_name, role, start_date, end_date, min_tier_count, max_tier_count, unit_price))
        self.conn.commit()

    def _normalize_date(self, target_date: Any) -> str:
        """Self-healing for date input. Normalizes dirty dates to a clean ISO format string."""
        if not target_date:
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        if isinstance(target_date, str):
            try:
                # Try parsing as ISO
                dt = datetime.datetime.fromisoformat(target_date.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    # Try basic date format
                    dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
                    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    # Fallback to current time if unparseable
                    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(target_date, datetime.datetime):
            return target_date.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(target_date, datetime.date):
             return datetime.datetime.combine(target_date, datetime.datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S.%f")

        # Absolute fallback
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    def _normalize_tier_count(self, tier_count: Any) -> int:
        """Self-healing for tier count. Ensures an integer."""
        if tier_count is None:
            return 0
        try:
            return int(float(tier_count))
        except (ValueError, TypeError):
            return 0

    def match(self, supplier_name: str, role: str, target_date: Any, tier_count: Any = 0) -> Optional[Dict[str, Any]]:
        """Matches a policy given the criteria."""

        clean_date = self._normalize_date(target_date)
        clean_tier_count = self._normalize_tier_count(tier_count)

        # Self-healing for basic string inputs
        supplier_name = str(supplier_name).strip() if supplier_name else "Unknown"
        role = str(role).strip() if role else "Unknown"

        cursor = self.conn.cursor()

        # We find a policy where:
        # 1. Supplier and role match
        # 2. Target date is between start_date and end_date
        # 3. tier_count is between min_tier_count and max_tier_count (or max_tier_count is null)

        cursor.execute('''
            SELECT supplier_name, role, start_date, end_date, min_tier_count, max_tier_count, unit_price
            FROM supplier_policies
            WHERE supplier_name = ?
              AND role = ?
              AND start_date <= ?
              AND end_date >= ?
              AND min_tier_count <= ?
              AND (max_tier_count IS NULL OR max_tier_count >= ?)
            ORDER BY min_tier_count DESC, start_date DESC
            LIMIT 1
        ''', (supplier_name, role, clean_date, clean_date, clean_tier_count, clean_tier_count))

        row = cursor.fetchone()

        if row:
            return {
                "supplier_name": row[0],
                "role": row[1],
                "start_date": row[2],
                "end_date": row[3],
                "min_tier_count": row[4],
                "max_tier_count": row[5],
                "unit_price": row[6],
                "matched_date": clean_date,
                "matched_tier_count": clean_tier_count
            }
        return None

    def explain(self, match_result: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Formats the match result into plain explainer text (JSON, HTML, Markdown)."""
        if not match_result:
            msg = "⚠️ 未找到匹配的供应商报价政策。请核对供应商名称、工种、日期或数量是否在有效范围内。"
            return {
                "json": json.dumps({"status": "no_match", "message": msg}, ensure_ascii=False),
                "html": f"<div class='policy-card no-match'><p>{msg}</p></div>",
                "markdown": f"> {msg}"
            }

        sup = match_result['supplier_name']
        role = match_result['role']
        price = match_result['unit_price']
        min_c = match_result['min_tier_count']
        max_c = match_result['max_tier_count']
        max_str = f"{max_c} 个" if max_c is not None else "不限"

        plain_text = f"✅ 匹配成功！【{sup}】提供的【{role}】服务，在您的需求数量（{match_result['matched_tier_count']}个，落在 {min_c} 到 {max_str} 的阶梯内）及指定日期下，适用单价为：{price} 元。"

        # JSON Output
        json_out = json.dumps({
            "status": "matched",
            "summary": plain_text,
            "details": match_result
        }, ensure_ascii=False)

        # HTML Output
        html_out = f"""
        <div class="policy-card matched" style="border: 1px solid #4CAF50; border-radius: 8px; padding: 16px; font-family: sans-serif;">
            <h3 style="color: #4CAF50; margin-top: 0;">✅ 政策匹配成功</h3>
            <p style="font-size: 16px; line-height: 1.5;">{plain_text}</p>
            <ul style="color: #666; font-size: 14px;">
                <li><strong>供应商:</strong> {sup}</li>
                <li><strong>工种:</strong> {role}</li>
                <li><strong>单价:</strong> <span style="color: #E91E63; font-weight: bold;">¥{price}</span></li>
                <li><strong>阶梯区间:</strong> {min_c} - {max_str}</li>
            </ul>
        </div>
        """

        # Markdown Output
        md_out = f"""
### ✅ 政策匹配成功

> **{plain_text}**

- **供应商**: `{sup}`
- **工种**: `{role}`
- **适用单价**: **¥{price}**
- **阶梯区间**: {min_c} - {max_str}
        """

        return {
            "json": json_out,
            "html": html_out.strip(),
            "markdown": md_out.strip()
        }

    def close(self):
        self.conn.close()

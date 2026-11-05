import sqlite3
import json
import re
import datetime
from typing import Dict, List, Any, Optional

try:
    import openpyxl
except ImportError:
    openpyxl = None


class SupplierPolicyMatcher:
    def __init__(self, db_path: str = ':memory:'):
        # Memory rule: Persist connection for in-memory DB
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                unit_price REAL NOT NULL
            )
        ''')
        self.conn.commit()

    def add_policy(self, supplier_name: str, job_type: str, start_date: str, end_date: str, unit_price: float):
        # Self-healing: basic strip and defaults
        supplier_name = (supplier_name or 'Unknown Supplier').strip()
        job_type = (job_type or 'General').strip()

        # Self-healing for dates
        start_date = self._normalize_date(start_date, default='1970-01-01 00:00:00.000')
        end_date = self._normalize_date(end_date, default='2099-12-31 23:59:59.999')

        unit_price = float(unit_price) if unit_price is not None else 0.0

        self.cursor.execute('''
            INSERT INTO policies (supplier_name, job_type, start_date, end_date, unit_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (supplier_name, job_type, start_date, end_date, unit_price))
        self.conn.commit()

    def _normalize_date(self, date_str: str, default: str) -> str:
        if not date_str:
            return default
        # Attempt to parse and standardize
        try:
            # If it's just a date, append time
            if len(date_str) == 10:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            else:
                # Try to parse with or without milliseconds
                if '.' in date_str:
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
                else:
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # milliseconds
        except ValueError:
            return default

    def match(self, target_date: str, job_type: str = None) -> List[Dict[str, Any]]:
        # Self-healing for target date
        target_date = self._normalize_date(target_date, default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000"))

        query = '''
            SELECT supplier_name, job_type, start_date, end_date, unit_price
            FROM policies
            WHERE ? >= start_date AND ? <= end_date
        '''
        params = [target_date, target_date]

        if job_type:
            # Use LIKE or exact match, handling dirty data
            query += " AND job_type = ?"
            params.append(job_type.strip())

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'supplier_name': row[0],
                'job_type': row[1],
                'start_date': row[2],
                'end_date': row[3],
                'unit_price': row[4]
            })
        return results

    def export_json(self, results: List[Dict[str, Any]], filepath: str = 'output.json'):
        if not filepath:
            filepath = 'output.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    def _strip_control_characters(self, s: str) -> str:
        if not isinstance(s, str):
            return s
        # Remove control characters like \x00
        return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)

    def export_excel(self, results: List[Dict[str, Any]], filepath: str = 'output.xlsx'):
        if not filepath:
            filepath = 'output.xlsx'

        if not openpyxl:
            raise ImportError("openpyxl is required for Excel export")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Match Results"

        headers = ['Supplier Name', 'Job Type', 'Start Date', 'End Date', 'Unit Price']
        ws.append(headers)

        for res in results:
            row = [
                self._strip_control_characters(res.get('supplier_name', '')),
                self._strip_control_characters(res.get('job_type', '')),
                self._strip_control_characters(res.get('start_date', '')),
                self._strip_control_characters(res.get('end_date', '')),
                res.get('unit_price', 0.0)
            ]
            ws.append(row)

        wb.save(filepath)

    def run_cli_one_click(self, target_date: str = None, job_type: str = None, export_json_path: str = 'output.json', export_excel_path: str = 'output.xlsx') -> Dict[str, Any]:
        """
        One-click run that fetches results and optionally exports to JSON/Excel.
        Zero config, sensible defaults.
        """
        if not target_date:
            target_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")

        results = self.match(target_date, job_type)

        if results:
            self.export_json(results, export_json_path)
            if openpyxl:
                self.export_excel(results, export_excel_path)

        return {
            "status": "success",
            "matched_count": len(results),
            "results": results
        }


def main():
    # Example minimal run
    matcher = SupplierPolicyMatcher()
    matcher.add_policy("TechCorp", "Developer", "2023-01-01", "2023-12-31", 150.5)
    print(matcher.run_cli_one_click("2023-06-15"))

if __name__ == '__main__':
    main()

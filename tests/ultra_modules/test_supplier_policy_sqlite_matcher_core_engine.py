import unittest
import sqlite3
import os
import datetime
from ultra_modules.supplier_policy_sqlite_matcher_core_engine import match_supplier_policy, _cleanse_date

class TestSupplierPolicySqliteMatcherCoreEngine(unittest.TestCase):
    db_path = "test_policies.db"

    def setUp(self):
        # Create an in-memory db or temporary file db for tests
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE supplier_policies (
                policy_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                min_quantity INTEGER NOT NULL,
                max_quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL
            )
        """)
        # Insert test data
        test_data = [
            ("P1", "ENGINEER", "2023-01-01", "2023-12-31", 1, 10, 50.0),
            ("P2", "ENGINEER", "2023-01-01", "2023-12-31", 11, 100, 45.0),
            ("P3", "DESIGNER", "2023-01-01", "2023-06-30", 1, 50, 60.0),
            ("P4", "GENERAL", "2023-01-01", "2023-12-31", 1, 1000, 30.0),
        ]
        cursor.executemany("INSERT INTO supplier_policies VALUES (?, ?, ?, ?, ?, ?, ?)", test_data)
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_normal_exact_matching(self):
        """测试用例 1: 正常匹配 (精确匹配)"""
        result = match_supplier_policy(
            db_path=self.db_path,
            target_date="2023-05-15",
            job_type="ENGINEER",
            quantity=5
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_price"], 50.0)
        self.assertEqual(result["policy_id"], "P1")

        # 阶梯数量边界
        result_tier_2 = match_supplier_policy(
            db_path=self.db_path,
            target_date="2023-05-15",
            job_type="ENGINEER",
            quantity=15
        )
        self.assertEqual(result_tier_2["status"], "success")
        self.assertEqual(result_tier_2["matched_price"], 45.0)
        self.assertEqual(result_tier_2["policy_id"], "P2")

    def test_dirty_data_cleansing(self):
        """测试用例 2: 脏数据静默清洗"""
        # 日期带有斜杠，工种带有小写和空格，数量是浮点字符串
        result = match_supplier_policy(
            db_path=self.db_path,
            target_date="2023/05/15",
            job_type="   designer  ",
            quantity=" 20.5 "
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_price"], 60.0)
        self.assertEqual(result["policy_id"], "P3")

    def test_missing_params_fallback(self):
        """测试用例 3: 缺参默认兜底"""
        # 未提供工种（回退到 GENERAL），未提供数量（回退到 1），未提供日期（回退到今日）
        # 为了让日期匹配，我们需要插入一条包含今日日期的策略
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO supplier_policies VALUES ('P5', 'GENERAL', '2000-01-01', ?, 1, 9999, 25.0)", (f"{datetime.date.today().year + 10}-12-31",))
        conn.commit()
        conn.close()

        result = match_supplier_policy(self.db_path)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_price"], 25.0)
        self.assertEqual(result["policy_id"], "P5")

    def test_extreme_boundary_and_no_match(self):
        """测试用例 4: 极端边界和未匹配回退"""
        # 超出时间范围
        result = match_supplier_policy(
            db_path=self.db_path,
            target_date="2025-01-01",
            job_type="ENGINEER",
            quantity=5
        )
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["matched_price"], 100.0)
        self.assertEqual(result["policy_id"], "DEFAULT_FALLBACK")

        # 负数数量（应被清洗为1）
        result_neg = match_supplier_policy(
            db_path=self.db_path,
            target_date="2023-05-15",
            job_type="ENGINEER",
            quantity=-10
        )
        self.assertEqual(result_neg["status"], "success")
        self.assertEqual(result_neg["matched_price"], 50.0)
        self.assertEqual(result_neg["policy_id"], "P1")

    def test_db_auto_creation(self):
        """测试用例 5: 零配置容错，数据库自动创建"""
        new_db = "auto_create_test.db"
        if os.path.exists(new_db):
            os.remove(new_db)

        # 第一次调用会自动建表，然后返回 fallback 因为没有数据
        result = match_supplier_policy(new_db, job_type="ANY")
        self.assertEqual(result["status"], "fallback")

        self.assertTrue(os.path.exists(new_db))
        os.remove(new_db)

    def test_invalid_db_path(self):
        """测试用例 6: 数据库连接错误兜底"""
        # 用非法路径触发错误
        result = match_supplier_policy("/root/invalid/path/db.db")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["policy_id"], "ERROR_FALLBACK")

    def test_date_cleansing_edge_cases(self):
        """测试用例 7: 日期清洗边缘用例"""
        # 无法解析的日期字符串
        today = datetime.date.today().isoformat()
        self.assertEqual(_cleanse_date("invalid_date"), today)
        # 过长的日期字符串截断
        self.assertEqual(_cleanse_date("2023-01-01T12:00:00Z"), "2023-01-01")
        # 传入 datetime.date 对象
        self.assertEqual(_cleanse_date(datetime.date(2023, 1, 1)), "2023-01-01")

if __name__ == '__main__':
    unittest.main()

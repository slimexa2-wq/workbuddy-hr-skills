import unittest
import json
import datetime
from ultra_modules.supplier_policy_sqlite_matcher_plain_explainer import SupplierPolicyMatcher

class TestSupplierPolicyMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = SupplierPolicyMatcher(db_path=":memory:")
        # Seed test data
        self.matcher.insert_policy(
            supplier_name="供应商A",
            role="前端开发",
            start_date="2023-01-01 00:00:00.000000",
            end_date="2023-12-31 23:59:59.999999",
            min_tier_count=1,
            max_tier_count=10,
            unit_price=1000.0
        )
        self.matcher.insert_policy(
            supplier_name="供应商A",
            role="前端开发",
            start_date="2023-01-01 00:00:00.000000",
            end_date="2023-12-31 23:59:59.999999",
            min_tier_count=11,
            max_tier_count=None,
            unit_price=800.0
        )

    def tearDown(self):
        self.matcher.close()

    def test_normal_successful_matching(self):
        """1. Normal successful matching"""
        match = self.matcher.match("供应商A", "前端开发", "2023-06-15 12:00:00.000000", tier_count=5)
        self.assertIsNotNone(match)
        self.assertEqual(match["unit_price"], 1000.0)

        explanation = self.matcher.explain(match)
        self.assertIn("1000.0 元", explanation["json"])
        self.assertIn("1000.0", explanation["html"])
        self.assertIn("1000.0", explanation["markdown"])

        # Test unbounded tier
        match2 = self.matcher.match("供应商A", "前端开发", "2023-06-15 12:00:00.000000", tier_count=15)
        self.assertIsNotNone(match2)
        self.assertEqual(match2["unit_price"], 800.0)

    def test_missing_parameters_fallback(self):
        """2. Missing parameters (falling back to defaults)"""
        # Missing date -> falls back to current time (which is likely 2024+ and won't match 2023 policy)
        # However, to test the missing parameter matching logic, we'll add a future policy
        self.matcher.insert_policy("供应商B", "后端", "2020-01-01 00:00:00.000", "2099-12-31 00:00:00.000", 0, 1500.0, None)

        match = self.matcher.match("供应商B", "后端", None, None)
        self.assertIsNotNone(match)
        self.assertEqual(match["unit_price"], 1500.0)
        self.assertEqual(match["matched_tier_count"], 0) # Fallback tier_count is 0

    def test_dirty_data_self_healing(self):
        """3. Dirty data self-healing (invalid numbers or dates)"""
        # Invalid date format string
        # Added a broad date policy to catch the fallback (which falls to current time)
        self.matcher.insert_policy("供应商C", "测试", "2000-01-01 00:00:00.000", "2099-12-31 00:00:00.000", 0, 500.0, None)

        match = self.matcher.match("  供应商C  ", " 测试 ", "not-a-date", tier_count="invalid_number")
        self.assertIsNotNone(match)
        self.assertEqual(match["supplier_name"], "供应商C")
        self.assertEqual(match["role"], "测试")
        self.assertEqual(match["matched_tier_count"], 0) # invalid_number becomes 0
        self.assertEqual(match["unit_price"], 500.0)

        # Test float as tier count
        match2 = self.matcher.match("供应商C", "测试", "2023-01-01", tier_count=5.9)
        self.assertIsNotNone(match2)
        self.assertEqual(match2["matched_tier_count"], 5)

    def test_edge_case_handling(self):
        """4. Edge case handling (e.g., tier bounds)"""
        # Exactly on the bound min=1, max=10
        match1 = self.matcher.match("供应商A", "前端开发", "2023-12-31 23:59:59.999999", tier_count=1)
        self.assertIsNotNone(match1)
        self.assertEqual(match1["unit_price"], 1000.0)

        match10 = self.matcher.match("供应商A", "前端开发", "2023-12-31 23:59:59.999999", tier_count=10)
        self.assertIsNotNone(match10)
        self.assertEqual(match10["unit_price"], 1000.0)

        match11 = self.matcher.match("供应商A", "前端开发", "2023-12-31 23:59:59.999999", tier_count=11)
        self.assertIsNotNone(match11)
        self.assertEqual(match11["unit_price"], 800.0)

    def test_unmatched_case_behavior(self):
        """5. Unmatched case behavior"""
        match = self.matcher.match("供应商X", "未知", "2023-01-01 12:00:00.000000", tier_count=5)
        self.assertIsNone(match)

        explanation = self.matcher.explain(match)

        json_data = json.loads(explanation["json"])
        self.assertEqual(json_data["status"], "no_match")
        self.assertIn("未找到匹配的供应商", explanation["html"])
        self.assertIn("未找到匹配的供应商", explanation["markdown"])

if __name__ == '__main__':
    unittest.main()

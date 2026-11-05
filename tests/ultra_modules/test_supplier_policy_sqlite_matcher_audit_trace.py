import unittest
from ultra_modules.supplier_policy_sqlite_matcher_audit_trace import SupplierPolicyMatcher
import json

class TestSupplierPolicyMatcher(unittest.TestCase):
    def setUp(self):
        # 初始化时自动采用 :memory:，保证隔离性与零配置
        self.matcher = SupplierPolicyMatcher()

    def test_normal_match(self):
        """测试正常插入和匹配逻辑"""
        self.matcher.add_policy("sup_001", "dev", "2023-01-01", "2023-06-30", 100.5)
        self.matcher.add_policy("sup_001", "dev", "2023-07-01", "2023-12-31", 120.0)

        # 命中上半年
        price1 = self.matcher.match_policy("sup_001", "dev", "2023-05-15")
        self.assertEqual(price1, 100.5)

        # 命中下半年
        price2 = self.matcher.match_policy("sup_001", "dev", "2023-10-01")
        self.assertEqual(price2, 120.0)

        # 边界外：无匹配，返回 0.0
        price3 = self.matcher.match_policy("sup_001", "dev", "2024-01-01")
        self.assertEqual(price3, 0.0)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈功能（日期颠倒、负数价格、格式错误）"""
        # 颠倒的日期、负数价格
        self.matcher.add_policy("sup_002", "tester", "2023-12-31", "2023-01-01", -50.0)

        # 匹配其中的日期
        price = self.matcher.match_policy("sup_002", "tester", "2023-06-01")
        self.assertEqual(price, 0.0)  # 负数自愈为 0.0

        logs = self.matcher.get_audit_logs()
        # 验证审计日志中记录了数据自愈
        heal_logs = [log for log in logs if log[2] == "data_heal"]
        self.assertTrue(len(heal_logs) >= 2) # 至少包含 inverted_dates 和 negative_price

    def test_missing_params_default(self):
        """测试缺参自动设为合理默认值兜底"""
        self.matcher.add_policy(None, None, "2023-01-01", "2023-12-31", 80.0)

        price = self.matcher.match_policy(None, None, "2023-05-05")
        self.assertEqual(price, 80.0)

        # 验证默认值被存储和匹配
        price2 = self.matcher.match_policy("default_supplier", "general", "2023-05-05")
        self.assertEqual(price2, 80.0)

    def test_deduplication_and_update(self):
        """测试去重及更新逻辑"""
        self.matcher.add_policy("sup_003", "pm", "2023-01-01", "2023-12-31", 150.0)
        # 插入相同主键记录但价格不同
        self.matcher.add_policy("sup_003", "pm", "2023-01-01", "2023-12-31", 160.0)

        price = self.matcher.match_policy("sup_003", "pm", "2023-05-05")
        self.assertEqual(price, 160.0) # 应该更新为新价格

        logs = self.matcher.get_audit_logs()
        dedup_logs = [log for log in logs if log[2] == "dedup_update"]
        self.assertEqual(len(dedup_logs), 1)

    def test_extreme_boundaries(self):
        """测试极端边界条件（空值，无效格式，重叠但价格不同取最高等情况）"""
        self.matcher.add_policy("sup_004", "ui", "invalid_start", "invalid_end", "not_a_number")

        # invalid_start 会被自愈为 1970-01-01, invalid_end 自愈为 2099-12-31, not_a_number 自愈为 0.0
        price = self.matcher.match_policy("sup_004", "ui", "2023-05-05")
        self.assertEqual(price, 0.0)

        # 测试重叠区间取最高价逻辑 (ORDER BY price DESC)
        self.matcher.add_policy("sup_overlap", "dev", "2023-01-01", "2023-12-31", 100.0)
        self.matcher.add_policy("sup_overlap", "dev", "2023-06-01", "2023-08-31", 150.0)

        # 6月15日落在两个区间，应取最高的 150.0
        price_overlap = self.matcher.match_policy("sup_overlap", "dev", "2023-06-15")
        self.assertEqual(price_overlap, 150.0)

if __name__ == '__main__':
    unittest.main()

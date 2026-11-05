import unittest
import json
from ultra_modules.monthly_254_baseline_auditor_plain_explainer import audit_and_explain, process_records

class TestMonthly254BaselineAuditorPlainExplainer(unittest.TestCase):

    def test_normal_passing_scenario(self):
        """测试正常达标场景"""
        records = [
            {"channel": "自招", "status": "在职", "days_employed": 10} for _ in range(260)
        ]
        result = audit_and_explain(records, baseline=254, format_type='dict')
        self.assertTrue(result["is_passed"])
        self.assertEqual(result["qualified_count"], 260)
        self.assertIn("达标", result["title"])
        self.assertIn("超过", result["conclusion"])
        self.assertEqual(result["baseline"], 254)

    def test_normal_failing_scenario(self):
        """测试正常未达标场景"""
        records = [
            {"channel": "自招", "status": "在职", "days_employed": 10} for _ in range(200)
        ]
        result = audit_and_explain(records, baseline=254, format_type='dict')
        self.assertFalse(result["is_passed"])
        self.assertEqual(result["qualified_count"], 200)
        self.assertIn("预警", result["title"])
        self.assertIn("还差 54 人", result["conclusion"])
        self.assertEqual(result["baseline"], 254)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈：缺参、错误类型、嵌套数据"""
        # 测试 None, 字符串, 以及含有非字典、缺参字典的列表
        mixed_records = {
            "data": [
                {"channel": "self", "status": "active", "days": "8"}, # 合格
                {"channel": "自招", "status": "在岗", "days_employed": 7}, # 合格
                {"is_self_recruited": True, "status": "在职", "days": 10}, # 合格
                {"channel": "内推", "status": "在职", "days_employed": 10}, # 不合格（渠道）
                {"channel": "自招", "status": "离职", "days_employed": 10}, # 不合格（状态）
                {"channel": "自招", "status": "在职", "days_employed": 5}, # 不合格（天数）
                {"channel": "自招", "status": "在职", "days_employed": "invalid_num"}, # 不合格（天数无法解析）
                "invalid string item", # 不合格（非字典）
                None # 不合格（None）
            ]
        }
        result = audit_and_explain(mixed_records, baseline=2, format_type='dict')
        self.assertTrue(result["is_passed"])
        self.assertEqual(result["qualified_count"], 3)

        # 测试直接传入字典
        single_dict_record = {"channel": "自招", "status": "在职", "days": 10}
        result2 = audit_and_explain(single_dict_record, baseline=1, format_type='dict')
        self.assertEqual(result2["qualified_count"], 1)

        # 测试不可迭代类型
        result3 = audit_and_explain(123, baseline=1, format_type='dict')
        self.assertEqual(result3["qualified_count"], 0)

        # 测试 keys records
        mixed_records2 = {
            "records": [
                {"channel": "self", "status": "active", "days": "8"}, # 合格
            ]
        }
        result4 = audit_and_explain(mixed_records2, baseline=1, format_type='dict')
        self.assertEqual(result4["qualified_count"], 1)

    def test_default_fallback_for_missing_parameters(self):
        """测试缺参和错误参数的默认兜底"""
        records = [
            {"channel": "自招", "status": "在职", "days_employed": 10} for _ in range(5)
        ]
        # 测试默认 baseline 和 json 格式
        json_result_str = audit_and_explain(records)
        json_result = json.loads(json_result_str)
        self.assertEqual(json_result["baseline"], 254)
        self.assertEqual(json_result["qualified_count"], 5)
        self.assertFalse(json_result["is_passed"])

        # 测试异常 baseline 和异常 format_type
        dict_result = audit_and_explain(records, baseline="invalid_baseline", format_type=123)
        json_result2 = json.loads(dict_result) # 因为 format_type=123 回退为 json
        self.assertEqual(json_result2["baseline"], 254)

        # 测试 baseline 为负数
        dict_result2 = audit_and_explain(records, baseline=-10, format_type='dict')
        self.assertEqual(dict_result2["baseline"], 254)

    def test_extreme_edge_cases_and_formats(self):
        """测试极端边界条件和不同输出格式"""
        # 测试 baseline 为 0 的情况（通常不会发生，但需防零除）
        records = [{"channel": "自招", "status": "在职", "days_employed": 10}]
        dict_res = audit_and_explain(records, baseline=0, format_type='dict')
        self.assertEqual(dict_res["achievement_rate_percent"], 100.0)
        self.assertTrue(dict_res["is_passed"])

        # 测试 baseline 很大的情况，不合格
        md_res = audit_and_explain(records, baseline=1000, format_type='markdown')
        self.assertIn("### ⚠️ 未达标", md_res)
        self.assertIn("1000 人", md_res)

        # 测试 HTML 格式
        html_res = audit_and_explain(records, baseline=1000, format_type='html')
        self.assertIn("<div", html_res)
        self.assertIn("#dc3545", html_res) # 红色预警

        # 测试 HTML 格式 达标情况
        html_res2 = audit_and_explain(records, baseline=1, format_type='html')
        self.assertIn("#28a745", html_res2) # 绿色达标

        # 测试未知格式，回退到 json
        res_unknown = audit_and_explain(records, baseline=100, format_type='unknown')
        self.assertTrue(isinstance(res_unknown, str))
        json_data = json.loads(res_unknown)
        self.assertEqual(json_data["baseline"], 100)

if __name__ == '__main__':
    unittest.main()

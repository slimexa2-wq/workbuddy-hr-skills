import unittest
import json
from ultra_modules.csv_encoding_auto_transcoder_plain_explainer import generate_explainer_card

class TestCSVEncodingAutoTranscoderPlainExplainer(unittest.TestCase):

    def test_normal_markdown_output(self):
        result_data = {
            "success": True,
            "original_encoding": "GBK",
            "rows_processed": 150,
            "dirty_data_fixed": 2
        }
        res = generate_explainer_card(result_data, "markdown")
        self.assertIn("✅ 考勤数据解析成功", res)
        self.assertIn("【GBK】格式", res)
        self.assertIn("150 条考勤记录", res)
        self.assertIn("修补了 2 处小瑕疵", res)
        self.assertTrue(res.startswith("###"))

    def test_normal_html_output(self):
        result_data = {
            "success": False,
            "original_encoding": "未知",
            "rows_processed": 0,
            "dirty_data_fixed": 0
        }
        res = generate_explainer_card(result_data, "html")
        self.assertIn("❌ 考勤数据解析遇到点小麻烦", res)
        self.assertIn("<div", res)
        self.assertIn("遇到点小麻烦", res)

    def test_normal_json_output(self):
        result_data = {
            "success": True,
            "original_encoding": "UTF-8-SIG",
            "rows_processed": 999,
            "dirty_data_fixed": 0
        }
        res = generate_explainer_card(result_data, "json")
        data = json.loads(res)
        self.assertEqual(data["title"], "✅ 考勤数据解析成功")
        self.assertEqual(data["metrics"]["rows"], 999)
        self.assertEqual(data["metrics"]["fixed"], 0)
        self.assertEqual(data["metrics"]["encoding"], "UTF-8-SIG")

    def test_missing_parameters_fallback(self):
        # Empty parameters
        res1 = generate_explainer_card()
        self.assertIn("✅ 考勤数据解析成功", res1)
        self.assertIn("【未知】格式", res1)
        self.assertIn("0 条考勤记录", res1)

        # Empty dict
        res2 = generate_explainer_card({}, "markdown")
        self.assertEqual(res1, res2)

    def test_dirty_data_self_healing(self):
        result_data = {
            "success": "yes",  # Not a boolean, will be evaluated as boolean True by Python bool() but normally we might want strict, our code does bool("yes") -> True
            "original_encoding": 12345,  # Not a string
            "rows_processed": "many",  # Not an int, should fallback to 0
            "dirty_data_fixed": None   # None, should fallback to 0
        }
        # In our code, bool("yes") is True.
        # str(12345) -> "12345"
        # int("many") -> Exception -> 0
        # int(None) -> Exception -> 0
        res = generate_explainer_card(result_data, "markdown")
        self.assertIn("✅ 考勤数据解析成功", res)
        self.assertIn("【12345】格式", res)
        self.assertIn("0 条考勤记录", res)
        self.assertIn("数据非常健康，没有发现乱码", res)

    def test_extreme_edge_cases(self):
        # Negative numbers and unknown output format
        result_data = {
            "success": True,
            "rows_processed": -50,
            "dirty_data_fixed": -10
        }
        res = generate_explainer_card(result_data, "pdf_or_something_weird")
        # Should fallback to markdown with 0s
        self.assertIn("### ✅ 考勤数据解析成功", res)
        self.assertIn("0 条考勤记录", res)
        self.assertIn("数据非常健康", res)

if __name__ == '__main__':
    unittest.main()

import unittest
from ultra_modules.zhaopin_greeting_personalizer_audit_trace import GreetingPersonalizer, DiffHighlighter

class TestGreetingPersonalizerAuditTrace(unittest.TestCase):
    def setUp(self):
        self.personalizer = GreetingPersonalizer()

    def test_normal_path(self):
        # Test 1: Normal path with complete data
        candidate_info = {
            "name": "张三",
            "experiences": ["腾讯", "阿里"],
            "expected_locations": ["深圳", "广州"]
        }
        result = self.personalizer.generate_greeting(candidate_info)
        greeting = result["greeting"]
        logs = result["audit_logs"]

        self.assertIn("张三", greeting)
        self.assertIn("腾讯、阿里", greeting)
        self.assertIn("深圳或广州", greeting)

        # Verify diff logger
        self.assertTrue(any(log["step"] == "generate_greeting" and "Original:" in log["details"]["diff"] for log in logs))

    def test_missing_parameter_defaults(self):
        # Test 2: Missing parameters (None input)
        result = self.personalizer.generate_greeting(None)
        greeting = result["greeting"]
        logs = result["audit_logs"]

        self.assertEqual(greeting, "你好！很高兴认识你。")
        self.assertTrue(any(log["action"] == "missing info" for log in logs))

        # Empty dict input
        result_empty = self.personalizer.generate_greeting({})
        greeting_empty = result_empty["greeting"]

        self.assertIn("候选人", greeting_empty)
        self.assertIn("觉得您的背景很不错", greeting_empty)
        self.assertIn("期待能与您进一步交流沟通", greeting_empty)

    def test_dirty_data_self_healing(self):
        # Test 3: Dirty data (whitespace, incorrect types, duplicates)
        candidate_info = {
            "name": "  李四  \n\t",
            "experiences": ["百度", "百度", "  字节跳动  ", 123, None],
            "expected_locations": "北京" # Should be a list, testing invalid type
        }
        result = self.personalizer.generate_greeting(candidate_info)
        greeting = result["greeting"]
        logs = result["audit_logs"]

        self.assertIn("你好，李四！", greeting)
        self.assertIn("百度、字节跳动、123", greeting)
        self.assertNotIn("北京", greeting) # Invalid type defaults to empty list

        # Verify self healing logs
        self.assertTrue(any(log["action"] == "cleaned whitespace" for log in logs))
        self.assertTrue(any(log["action"] == "auto-fixed non-string" for log in logs))
        self.assertTrue(any(log["action"] == "invalid input type" for log in logs))
        self.assertTrue(any(log["action"] == "deduplicated items" for log in logs))

    def test_extreme_boundary_cases(self):
        # Test 4: Extreme boundaries (huge lists, long strings)
        long_name = "王" * 100
        candidate_info = {
            "name": long_name,
            "experiences": [f"公司{i}" for i in range(1000)],
            "expected_locations": []
        }
        result = self.personalizer.generate_greeting(candidate_info)
        greeting = result["greeting"]

        self.assertIn(long_name, greeting)
        self.assertIn("公司999", greeting)
        self.assertIn("期待能与您进一步交流沟通", greeting)

    def test_diff_highlighter(self):
        # Test 5: DiffHighlighter static method functionality
        diff_none = DiffHighlighter.highlight_diff("abc", "abc")
        self.assertEqual(diff_none, "No changes.")

        diff_some = DiffHighlighter.highlight_diff("abc", "def")
        self.assertIn("Original: abc", diff_some)
        self.assertIn("Modified: def", diff_some)

if __name__ == '__main__':
    unittest.main()

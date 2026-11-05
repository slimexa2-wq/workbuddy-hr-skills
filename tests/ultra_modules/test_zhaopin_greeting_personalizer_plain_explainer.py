import unittest
import json
from ultra_modules.zhaopin_greeting_personalizer_plain_explainer import ZhaopinGreetingPersonalizer

class TestZhaopinGreetingPersonalizer(unittest.TestCase):
    def setUp(self):
        self.personalizer = ZhaopinGreetingPersonalizer()

    def test_normal_case_full_data(self):
        data = {
            "name": "张三",
            "past_companies": ["富士康", "立讯精密"],
            "expected_locations": ["深圳", "东莞"]
        }

        # Test greeting
        greeting = self.personalizer.generate_greeting(data)
        self.assertIn("张三", greeting)
        self.assertIn("富士康、立讯精密", greeting)
        self.assertIn("深圳", greeting)

        # Test JSON card
        json_card = self.personalizer.generate_explainer_card(data, "json")
        card_data = json.loads(json_card)
        self.assertEqual(card_data["candidate_name"], "张三")
        self.assertTrue(any("富士康" in h for h in card_data["key_highlights"]))
        self.assertTrue(any("深圳" in h for h in card_data["key_highlights"]))

        # Test HTML card
        html_card = self.personalizer.generate_explainer_card(data, "html")
        self.assertIn("<li>有【富士康, 立讯精密】等厂区经验", html_card)

        # Test Markdown card
        md_card = self.personalizer.generate_explainer_card(data, "markdown")
        self.assertIn("- 候选人期望地包含【深圳, 东莞】", md_card)

    def test_normal_case_partial_data(self):
        data = {
            "name": "李四",
            "past_companies": ["比亚迪"]
            # No expected_locations
        }

        greeting = self.personalizer.generate_greeting(data)
        self.assertIn("李四", greeting)
        self.assertIn("比亚迪", greeting)
        self.assertIn("刚好我们这边有几个合适的岗位", greeting)

        card_data = json.loads(self.personalizer.generate_explainer_card(data, "json"))
        self.assertTrue(any("比亚迪" in h for h in card_data["key_highlights"]))
        self.assertTrue(any("未明确期望地" in h for h in card_data["key_highlights"]))

    def test_dirty_data_self_healing(self):
        # Passing entirely wrong type for dict
        greeting_none = self.personalizer.generate_greeting(None)
        self.assertIn("你好，同学！", greeting_none)

        # Passing weird types inside dict
        data = {
            "name": 12345, # Int instead of str
            "past_companies": "单独一个公司作为字符串而不是列表",
            "expected_locations": [None, 999, ""] # Dirty list
        }

        greeting = self.personalizer.generate_greeting(data)
        self.assertIn("12345", greeting)
        self.assertIn("单独一个公司作为字符串而不是列表", greeting)
        self.assertIn("999", greeting)

    def test_missing_params_default_fallback(self):
        data = {} # Empty input

        greeting = self.personalizer.generate_greeting(data)
        self.assertIn("你好，同学！", greeting)
        self.assertIn("我看你的简历挺不错的", greeting)
        self.assertIn("刚好我们这边有几个合适的岗位", greeting)

        card_data = json.loads(self.personalizer.generate_explainer_card(data, "json"))
        self.assertEqual(card_data["candidate_name"], "同学")
        self.assertTrue(any("暂无具体厂区经验记录" in h for h in card_data["key_highlights"]))

    def test_extreme_boundary_cases(self):
        # Very long name and many companies
        data = {
            "name": "A" * 1000,
            "past_companies": [f"公司{i}" for i in range(100)],
            "expected_locations": ["城市A", "城市B"]
        }

        greeting = self.personalizer.generate_greeting(data)
        self.assertIn("A" * 1000, greeting)
        self.assertIn("公司0、公司1等做过", greeting) # Check truncation of companies

        # Test unknown output format fallback to json
        card = self.personalizer.generate_explainer_card(data, "unknown_format_xyz")
        try:
            parsed = json.loads(card)
            self.assertEqual(parsed["candidate_name"], "A" * 1000)
        except json.JSONDecodeError:
            self.fail("Card format did not fallback to JSON when given an unknown format.")

if __name__ == '__main__':
    unittest.main()

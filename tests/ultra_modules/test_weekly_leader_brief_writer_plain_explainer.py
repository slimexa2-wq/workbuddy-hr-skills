import unittest
import json
from ultra_modules.weekly_leader_brief_writer_plain_explainer import generate_brief

class TestWeeklyLeaderBriefWriterPlainExplainer(unittest.TestCase):

    def test_normal_input(self):
        """Test with valid integer inputs."""
        data = {
            "onboarding_count": 5,
            "offboarding_count": 2,
            "total_headcount": 100
        }
        result = generate_brief(data)

        self.assertIn("html", result)
        self.assertIn("markdown", result)
        self.assertIn("json", result)

        json_data = json.loads(result["json"])
        self.assertEqual(json_data["onboarding_count"], 5)
        self.assertEqual(json_data["offboarding_count"], 2)
        self.assertEqual(json_data["total_headcount"], 100)

        self.assertIn("5人", result["html"])
        self.assertIn("2人", result["html"])
        self.assertIn("100人", result["html"])

    def test_dirty_data_healing(self):
        """Test with negative numbers and invalid strings, expects self-healing to 0."""
        data = {
            "onboarding_count": -5,
            "offboarding_count": "invalid",
            "total_headcount": "100"
        }
        result = generate_brief(data)
        json_data = json.loads(result["json"])

        self.assertEqual(json_data["onboarding_count"], 0)
        self.assertEqual(json_data["offboarding_count"], 0)
        self.assertEqual(json_data["total_headcount"], 100)

    def test_missing_params(self):
        """Test when parameter is None or fields are missing."""
        # Test None input
        result1 = generate_brief(None)
        json_data1 = json.loads(result1["json"])
        self.assertEqual(json_data1["onboarding_count"], 0)
        self.assertEqual(json_data1["offboarding_count"], 0)
        self.assertEqual(json_data1["total_headcount"], 0)

        # Test empty dict input
        result2 = generate_brief({})
        json_data2 = json.loads(result2["json"])
        self.assertEqual(json_data2["onboarding_count"], 0)
        self.assertEqual(json_data2["offboarding_count"], 0)
        self.assertEqual(json_data2["total_headcount"], 0)

    def test_extreme_boundary_cases(self):
        """Test with extremely large numbers."""
        data = {
            "onboarding_count": 999999999999,
            "offboarding_count": 0,
            "total_headcount": 1000000000000
        }
        result = generate_brief(data)
        json_data = json.loads(result["json"])
        self.assertEqual(json_data["onboarding_count"], 999999999999)
        self.assertEqual(json_data["total_headcount"], 1000000000000)

    def test_proper_formatting(self):
        """Test the correctness of returned data structure and strings formatting."""
        data = {
            "onboarding_count": 10,
            "offboarding_count": 3,
            "total_headcount": 50
        }
        result = generate_brief(data)

        # Validate HTML
        self.assertTrue(result["html"].startswith("<div>"))
        self.assertTrue(result["html"].endswith("</div>"))
        self.assertIn("<h1>每周人员流动摘要</h1>", result["html"])

        # Validate Markdown
        self.assertTrue(result["markdown"].startswith("# 每周人员流动摘要\n"))
        self.assertIn("- **本周入职人数:** 10人", result["markdown"])

        # Validate JSON
        parsed_json = json.loads(result["json"])
        self.assertEqual(parsed_json, {
            "onboarding_count": 10,
            "offboarding_count": 3,
            "total_headcount": 50
        })

if __name__ == '__main__':
    unittest.main()

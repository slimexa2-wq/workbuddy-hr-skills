import unittest
import json
from ultra_modules.monday_3reports_runner_plain_explainer import generate_plain_explanation

class TestMonday3ReportsRunnerPlainExplainer(unittest.TestCase):
    def setUp(self):
        self.normal_data = {
            "summary": {
                "total_projects": 3,
                "total_students": 5,
                "total_campus_hires": 10
            },
            "project_requirements": [
                {"status": "Active", "headcount": 2},
                {"status": "Open", "headcount": 3},
                {"status": "Closed", "headcount": 1}
            ],
            "student_workers": [
                {"working_hours": 10.5},
                {"working_hours": 20.0},
                {"working_hours": 15.0}
            ],
            "campus_recruitment_performance": [
                {"performance_score": "S"},
                {"performance_score": "A"},
                {"performance_score": "B"}
            ]
        }

    def test_normal_data_markdown(self):
        """Test Case 1: Normal data processing (Markdown output)"""
        result = generate_plain_explanation(self.normal_data, output_format="markdown")

        self.assertIn("# 每周一报表极简摘要", result)
        self.assertIn("本周共追踪到 3 个项目需求。其中活跃项目 2 个，总计需要 6 人。", result)
        self.assertIn("本周共有 5 名学生工在岗，累计贡献工时 45.5 小时。", result)
        self.assertIn("本周共评估了 10 名存量校招生的绩效，其中表现优异（S/A级）的有 2 人。", result)

    def test_output_formats_html_json(self):
        """Test Case 2: Output format rendering (HTML/JSON output)"""
        # JSON
        result_json = generate_plain_explanation(self.normal_data, output_format="json")
        data = json.loads(result_json)
        self.assertEqual(data["title"], "每周一报表极简摘要")
        self.assertIn("3 个项目需求", data["section_projects"])

        # HTML
        result_html = generate_plain_explanation(self.normal_data, output_format="html")
        self.assertIn('<div class="monday-report-card"', result_html)
        self.assertIn('【项目需求】本周共追踪到 3 个项目需求。其中活跃项目 2 个，总计需要 6 人。</p>', result_html)

    def test_dirty_data_self_healing(self):
        """Test Case 3: Dirty data self-healing (handling incorrect types/values within the input data)"""
        dirty_data = {
            "summary": {
                "total_projects": "invalid",  # should become 0
                "total_students": -5,         # should become 0
                "total_campus_hires": " 12 "  # should become 12
            },
            "project_requirements": [
                {"status": ["invalid"], "headcount": " 3 "},
                {"status": "ACTIVE", "headcount": -5} # -5 will become 0
            ],
            "student_workers": [
                {"working_hours": "100.5"},
                {"working_hours": None}
            ],
            "campus_recruitment_performance": [
                {"performance_score": 123},
                {"performance_score": " s "}
            ]
        }

        result = generate_plain_explanation(dirty_data, output_format="markdown")
        self.assertIn("本周共追踪到 0 个项目需求。其中活跃项目 1 个，总计需要 3 人。", result)
        self.assertIn("本周共有 0 名学生工在岗，累计贡献工时 100.5 小时。", result)
        self.assertIn("本周共评估了 12 名存量校招生的绩效，其中表现优异（S/A级）的有 1 人。", result)

    def test_missing_arguments_fallback(self):
        """Test Case 4: Missing arguments (falling back to empty/default)"""
        result = generate_plain_explanation()
        self.assertIn("本周共追踪到 0 个项目需求。其中活跃项目 0 个，总计需要 0 人。", result)
        self.assertIn("本周共有 0 名学生工在岗，累计贡献工时 0.0 小时。", result)
        self.assertIn("本周共评估了 0 名存量校招生的绩效，其中表现优异（S/A级）的有 0 人。", result)

    def test_extreme_boundary_conditions(self):
        """Test Case 5: Extreme boundary conditions (invalid outer data types, negative numbers, etc)"""
        result_invalid_input = generate_plain_explanation(report_data="not a dict", output_format=["not a string"])
        self.assertIn("本周共追踪到 0 个项目需求。其中活跃项目 0 个，总计需要 0 人。", result_invalid_input)

        extreme_data = {
            "summary": [],
            "project_requirements": "not a list",
            "student_workers": None,
            "campus_recruitment_performance": {}
        }
        result_extreme = generate_plain_explanation(extreme_data)
        self.assertIn("本周共追踪到 0 个项目需求。其中活跃项目 0 个，总计需要 0 人。", result_extreme)

if __name__ == "__main__":
    unittest.main()

import unittest
import math
from ultra_modules.monday_3reports_runner_export_formatter import format_monday_reports

class TestMonday3ReportsRunnerExportFormatter(unittest.TestCase):

    def test_normal_behavior(self):
        """Test normal execution with valid lists of dicts."""
        res = format_monday_reports(
            project_needs=[{"id": 1}],
            student_workers=[{"id": 2}, {"id": 3}],
            campus_recruitment=[{"id": 4}]
        )
        self.assertEqual(len(res["project_needs"]), 1)
        self.assertEqual(len(res["student_workers"]), 2)
        self.assertEqual(len(res["campus_recruitment"]), 1)
        self.assertEqual(res["project_needs"][0]["comments"], 0)

        expected_briefing = (
            "项目需求报表已就绪：共 1 条数据\n"
            "学生工报表已就绪：共 2 条数据\n"
            "校招绩效报表已就绪：共 1 条数据"
        )
        self.assertEqual(res["briefing"], expected_briefing)

    def test_missing_parameters_fallback(self):
        """Test missing parameters automatic fallback."""
        res = format_monday_reports()
        self.assertEqual(res["project_needs"], [])
        self.assertEqual(res["student_workers"], [])
        self.assertEqual(res["campus_recruitment"], [])
        expected_briefing = (
            "项目需求报表已就绪：共 0 条数据\n"
            "学生工报表已就绪：共 0 条数据\n"
            "校招绩效报表已就绪：共 0 条数据"
        )
        self.assertEqual(res["briefing"], expected_briefing)

    def test_dirty_data_self_healing_scalar_to_list(self):
        """Test dirty data self healing converting scalar dicts to lists."""
        res = format_monday_reports(
            project_needs={"id": 1},
            student_workers="invalid_string",
            campus_recruitment=None
        )
        self.assertEqual(len(res["project_needs"]), 1)
        self.assertEqual(len(res["student_workers"]), 0) # Dropped invalid
        self.assertEqual(len(res["campus_recruitment"]), 0) # Fallback to empty list

    def test_dirty_data_self_healing_non_dict_elements(self):
        """Test dirty data ignoring non-dict elements in lists."""
        res = format_monday_reports(
            project_needs=[{"id": 1}, "wrong_item", 42, ["nested"]],
            student_workers=[],
            campus_recruitment=[]
        )
        self.assertEqual(len(res["project_needs"]), 1)
        self.assertEqual(res["project_needs"][0]["id"], 1)

    def test_extreme_boundary_nan_and_none_values(self):
        """Test extreme boundary cases like NaN and None in dataset values."""
        res = format_monday_reports(
            project_needs=[{"val1": math.nan, "val2": None, "val3": "string", "comments": "some text"}]
        )
        item = res["project_needs"][0]
        self.assertEqual(item["val1"], 0)
        self.assertEqual(item["val2"], 0)
        self.assertEqual(item["val3"], "string")
        self.assertEqual(item["comments"], 0) # Asserts comments is strictly overridden to 0

if __name__ == '__main__':
    unittest.main()

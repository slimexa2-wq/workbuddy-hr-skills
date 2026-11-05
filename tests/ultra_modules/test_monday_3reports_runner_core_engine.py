import unittest
from ultra_modules.monday_3reports_runner_core_engine import synthesize_monday_reports

class TestMonday3ReportsRunnerCoreEngine(unittest.TestCase):
    def test_normal_data(self):
        """Test Case 1: Normal data processing for all 3 reports."""
        project_reqs = [{"project_name": "Alpha", "status": "Active", "headcount": 5}]
        student_workers = [{"name": "Alice", "department": "Engineering", "working_hours": 20.5}]
        campus_perf = [{"employee_name": "Bob", "performance_score": "A", "feedback": "Great job"}]

        result = synthesize_monday_reports(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["summary"]["total_projects"], 1)
        self.assertEqual(result["project_requirements"][0]["project_name"], "Alpha")
        self.assertEqual(result["project_requirements"][0]["headcount"], 5)

        self.assertEqual(result["summary"]["total_students"], 1)
        self.assertEqual(result["student_workers"][0]["name"], "Alice")
        self.assertEqual(result["student_workers"][0]["working_hours"], 20.5)

        self.assertEqual(result["summary"]["total_campus_hires"], 1)
        self.assertEqual(result["campus_recruitment_performance"][0]["employee_name"], "Bob")
        self.assertEqual(result["campus_recruitment_performance"][0]["performance_score"], "A")

    def test_dirty_data_self_healing(self):
        """Test Case 2: Dirty data silent cleaning (auto-fault-tolerance)."""
        project_reqs = [{"project_name": "  ", "status": None, "headcount": "invalid"}]
        student_workers = [{"name": "", "department": 123, "working_hours": -5.0}]
        campus_perf = [{"employee_name": " Charlie  ", "performance_score": "Z", "feedback": "   "}]

        result = synthesize_monday_reports(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["project_requirements"][0]["project_name"], "Unknown Project")
        self.assertEqual(result["project_requirements"][0]["status"], "None")
        self.assertEqual(result["project_requirements"][0]["headcount"], 0)

        self.assertEqual(result["student_workers"][0]["name"], "Unknown Student")
        self.assertEqual(result["student_workers"][0]["department"], "123")
        self.assertEqual(result["student_workers"][0]["working_hours"], 0.0)

        self.assertEqual(result["campus_recruitment_performance"][0]["employee_name"], "Charlie")
        self.assertEqual(result["campus_recruitment_performance"][0]["performance_score"], "C")
        self.assertEqual(result["campus_recruitment_performance"][0]["feedback"], "")

    def test_missing_arguments_default_fallback(self):
        """Test Case 3: Missing arguments fallback to defaults."""
        result = synthesize_monday_reports()

        self.assertEqual(result["summary"]["total_projects"], 0)
        self.assertEqual(result["summary"]["total_students"], 0)
        self.assertEqual(result["summary"]["total_campus_hires"], 0)
        self.assertEqual(result["project_requirements"], [])
        self.assertEqual(result["student_workers"], [])
        self.assertEqual(result["campus_recruitment_performance"], [])

    def test_invalid_argument_types(self):
        """Test Case 4: Invalid argument types fallback to empty lists."""
        result = synthesize_monday_reports(project_reqs="string", student_workers=123, campus_perf={"dict": "val"})

        self.assertEqual(result["summary"]["total_projects"], 0)
        self.assertEqual(result["summary"]["total_students"], 0)
        self.assertEqual(result["summary"]["total_campus_hires"], 0)
        self.assertEqual(result["project_requirements"], [])
        self.assertEqual(result["student_workers"], [])
        self.assertEqual(result["campus_recruitment_performance"], [])

    def test_extreme_boundaries_and_mixed_invalid_items(self):
        """Test Case 5: Lists with mixed valid/invalid item types (e.g., list of strings instead of dicts)."""
        project_reqs = ["not_a_dict", {"headcount": -10}]
        student_workers = [None, {"working_hours": "15.5"}]
        campus_perf = [{"employee_name": None, "performance_score": " s "}, [1, 2, 3]]

        result = synthesize_monday_reports(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["summary"]["total_projects"], 1)
        self.assertEqual(result["project_requirements"][0]["headcount"], 0)
        self.assertEqual(result["project_requirements"][0]["project_name"], "Unknown Project")

        self.assertEqual(result["summary"]["total_students"], 1)
        self.assertEqual(result["student_workers"][0]["working_hours"], 15.5)

        self.assertEqual(result["summary"]["total_campus_hires"], 1)
        self.assertEqual(result["campus_recruitment_performance"][0]["employee_name"], "None")
        self.assertEqual(result["campus_recruitment_performance"][0]["performance_score"], "S")

if __name__ == "__main__":
    unittest.main()

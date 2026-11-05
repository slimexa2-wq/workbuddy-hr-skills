import unittest
from ultra_modules.monday_3reports_runner_integration_bridge import run_3reports_synthesis, Monday3ReportsIntegrationBridge

class TestMonday3ReportsRunnerIntegrationBridge(unittest.TestCase):

    def setUp(self):
        self.bridge = Monday3ReportsIntegrationBridge()

    def test_normal_usage(self):
        """Test standard normal usage with valid data."""
        project_reqs = [{"project_name": "Project A", "hc": 5, "department": "Engineering"}]
        student_workers = [{"full_name": "John Doe", "status": "Active", "university": "MIT"}]
        campus_perf = [{"employee_id": "EMP001", "perf_score": "A"}]

        result = run_3reports_synthesis(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["synthesis_status"], "success")
        self.assertEqual(result["summary"]["total_projects"], 1)
        self.assertEqual(result["summary"]["total_students"], 1)
        self.assertEqual(result["summary"]["total_campus_records"], 1)

        self.assertEqual(result["data"]["project_requirements"][0]["project_name"], "Project A")
        self.assertEqual(result["data"]["student_workers"][0]["full_name"], "John Doe")
        self.assertEqual(result["data"]["campus_recruitment_performance"][0]["performance_rating"], "A")

    def test_dirty_data_self_healing(self):
        """Test dirty data self-healing and schema conversion."""
        project_reqs = [{"req_name": "Project \x00B", "headcount": " 10  ", "department": None}]
        student_workers = [{"student_name": "Jane Smith\t", "status": "working now", "university": "Stanford"}]
        campus_perf = [{"emp_id": "EMP002", "perf_score": "85"}]

        result = run_3reports_synthesis(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["data"]["project_requirements"][0]["project_name"], "Project B")
        self.assertEqual(result["data"]["project_requirements"][0]["hc"], 10)
        self.assertEqual(result["data"]["project_requirements"][0]["department"], "")

        self.assertEqual(result["data"]["student_workers"][0]["full_name"], "Jane Smith")
        self.assertEqual(result["data"]["student_workers"][0]["status"], "Active")

        self.assertEqual(result["data"]["campus_recruitment_performance"][0]["employee_id"], "EMP002")
        self.assertEqual(result["data"]["campus_recruitment_performance"][0]["performance_rating"], "B")

    def test_missing_parameter_fallbacks(self):
        """Test that missing parameters fallback to sensible defaults without crashing."""
        # Empty calls
        result_empty = run_3reports_synthesis()

        self.assertEqual(result_empty["synthesis_status"], "success")
        self.assertEqual(result_empty["summary"]["total_projects"], 0)
        self.assertEqual(result_empty["summary"]["total_students"], 0)
        self.assertEqual(result_empty["summary"]["total_campus_records"], 0)
        self.assertEqual(len(result_empty["data"]["project_requirements"]), 0)
        self.assertEqual(len(result_empty["data"]["student_workers"]), 0)
        self.assertEqual(len(result_empty["data"]["campus_recruitment_performance"]), 0)

        # Partial data missing fields
        project_reqs = [{}]
        student_workers = [{"status": None}]
        campus_perf = [{"perf_score": None}]

        result_partial = run_3reports_synthesis(project_reqs, student_workers, campus_perf)

        self.assertEqual(result_partial["data"]["project_requirements"][0]["project_name"], "Untitled Project")
        self.assertEqual(result_partial["data"]["project_requirements"][0]["hc"], 1)
        self.assertEqual(result_partial["data"]["student_workers"][0]["full_name"], "Anonymous")
        self.assertEqual(result_partial["data"]["student_workers"][0]["status"], "Active")
        self.assertEqual(result_partial["data"]["campus_recruitment_performance"][0]["employee_id"], "UNKNOWN_ID")
        self.assertEqual(result_partial["data"]["campus_recruitment_performance"][0]["performance_rating"], "N/A")

    def test_extreme_boundary_conditions(self):
        """Test extreme boundaries like malformed inputs, extreme numbers, unexpected types."""
        project_reqs = [{"req_name": 12345, "headcount": "xyz", "department": {"complex": "dict"}}]
        student_workers = ["Not a dict", None, 123, {"name": "Bob", "status": "Unknown state 123"}]
        campus_perf = [{"emp_id": None, "perf_score": -999}, {"rating": 99999}]

        result = run_3reports_synthesis(project_reqs, student_workers, campus_perf)

        # Should silently ignore invalid non-dict entries
        self.assertEqual(result["summary"]["total_projects"], 1)
        self.assertEqual(result["summary"]["total_students"], 1)  # Only 1 valid dict
        self.assertEqual(result["summary"]["total_campus_records"], 2)

        self.assertEqual(result["data"]["project_requirements"][0]["project_name"], "12345")
        self.assertEqual(result["data"]["project_requirements"][0]["hc"], 1) # Fallback because 'xyz' has no numbers
        self.assertEqual(result["data"]["project_requirements"][0]["department"], "{'complex': 'dict'}")

        self.assertEqual(result["data"]["student_workers"][0]["full_name"], "Bob")
        self.assertEqual(result["data"]["student_workers"][0]["status"], "Unknown state 123")

        self.assertEqual(result["data"]["campus_recruitment_performance"][0]["employee_id"], "UNKNOWN_ID")
        self.assertEqual(result["data"]["campus_recruitment_performance"][0]["performance_rating"], "N/A")
        self.assertEqual(result["data"]["campus_recruitment_performance"][1]["performance_rating"], "A") # 99999 >= 90

    def test_schema_conversion_edge_cases(self):
        """Test specific edge cases in schema conversion."""
        campus_perf = [
            {"rating": "a"},  # Valid lowercase grade
            {"rating": "F"},  # Unmapped uppercase string
            {"rating": 75.5}, # Float mapping
            {"perf_score": 59} # E grade edge case
        ]

        result = run_3reports_synthesis(campus_perf=campus_perf)
        records = result["data"]["campus_recruitment_performance"]

        self.assertEqual(records[0]["performance_rating"], "a") # Preserves case
        self.assertEqual(records[1]["performance_rating"], "N/A") # Not a valid score and F not in A-E
        self.assertEqual(records[2]["performance_rating"], "C") # >= 70
        self.assertEqual(records[3]["performance_rating"], "E") # < 60 but > -1

if __name__ == '__main__':
    unittest.main()

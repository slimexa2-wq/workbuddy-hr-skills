import unittest
from ultra_modules.monday_3reports_runner_audit_trace import run_monday_reports_with_audit

class TestMonday3ReportsRunnerAuditTrace(unittest.TestCase):
    def test_normal_inputs(self):
        project_reqs = [{"project_name": "Project Alpha", "status": "Approved", "headcount": 5}]
        student_workers = [{"name": "Alice", "department": "Engineering", "working_hours": 20.5}]
        campus_perf = [{"employee_name": "Bob", "performance_score": "A", "feedback": "Great work"}]

        result, audit = run_monday_reports_with_audit(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["summary"]["total_projects"], 1)
        self.assertEqual(result["summary"]["total_students"], 1)
        self.assertEqual(result["summary"]["total_campus_hires"], 1)
        self.assertEqual(len(audit), 0)

    def test_missing_parameters_fallback(self):
        # Calling with None
        result, audit = run_monday_reports_with_audit(None, None, None)

        self.assertEqual(result["summary"]["total_projects"], 0)
        self.assertEqual(result["summary"]["total_students"], 0)
        self.assertEqual(result["summary"]["total_campus_hires"], 0)
        self.assertTrue(any(log["entity_id"] == "project_reqs" for log in audit))
        self.assertTrue(any(log["entity_id"] == "student_workers" for log in audit))
        self.assertTrue(any(log["entity_id"] == "campus_perf" for log in audit))

    def test_dirty_data_self_healing(self):
        # Invalid types for fields, leading/trailing whitespace
        project_reqs = [{"project_name": "  Dirty Project  ", "headcount": -10}]
        student_workers = [{"name": "Charlie", "working_hours": "not_a_number"}]
        campus_perf = [{"employee_name": "Dave", "performance_score": "Z"}]

        result, audit = run_monday_reports_with_audit(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["project_requirements"][0]["project_name"], "Dirty Project")
        self.assertEqual(result["project_requirements"][0]["headcount"], 0)
        self.assertEqual(result["student_workers"][0]["working_hours"], 0.0)
        self.assertEqual(result["campus_recruitment_performance"][0]["performance_score"], "C")

        # Verify audits were generated for corrections
        self.assertTrue(any(log["field"] == "headcount" and log["corrected"] == 0 for log in audit))
        self.assertTrue(any(log["field"] == "working_hours" and log["corrected"] == 0.0 for log in audit))
        self.assertTrue(any(log["field"] == "performance_score" and log["corrected"] == "C" for log in audit))

    def test_extreme_boundary_conditions(self):
        # Passing completely invalid data (e.g. string instead of list of dicts)
        # and lists with non-dict elements
        project_reqs = "invalid_string"
        student_workers = [123, 456]
        campus_perf = [{"employee_name": "Eve"}, {"employee_name": "Eve"}] # Duplicate name

        result, audit = run_monday_reports_with_audit(project_reqs, student_workers, campus_perf)

        self.assertEqual(result["summary"]["total_projects"], 0)
        self.assertEqual(result["summary"]["total_students"], 0)
        self.assertEqual(result["summary"]["total_campus_hires"], 1) # Second 'Eve' is a duplicate

        self.assertTrue(any(log["entity_id"] == "project_reqs" and log["reason"] == "Invalid type, defaulted to empty list" for log in audit))
        self.assertTrue(any(log["entity_type"] == "student_workers" and log["reason"] == "Entry is not a dictionary" for log in audit))
        self.assertTrue(any(log["field"] == "duplicate" and log["original"] == "Eve" for log in audit))

    def test_audit_trace_correctness(self):
        project_reqs = [{"project_name": "P1", "headcount": "5"}, {"project_name": "P1", "headcount": 10}]

        result, audit = run_monday_reports_with_audit(project_reqs, [], [])
        self.assertEqual(result["summary"]["total_projects"], 1)

        # Verify deduplication audit
        dup_logs = [log for log in audit if log["field"] == "duplicate" and log["original"] == "P1"]
        self.assertEqual(len(dup_logs), 1)

if __name__ == '__main__':
    unittest.main()

import unittest
from datetime import datetime
from ultra_modules.weekly_leader_brief_writer_audit_trace import generate_weekly_hr_brief, WeeklyLeaderBriefWriter

class TestWeeklyLeaderBriefWriterAuditTrace(unittest.TestCase):

    def setUp(self):
        self.writer = WeeklyLeaderBriefWriter()
        self.report_date = "2023-10-27"

    def test_normal_data_flow(self):
        """Test normal data flow with valid inputs."""
        onboarding = [
            {"id": "E001", "name": "Alice", "department": "Engineering", "status": "active"},
            {"id": "E002", "name": "Bob", "department": "Sales", "status": "active"}
        ]
        offboarding = [
            {"id": "E003", "name": "Charlie", "department": "Marketing", "status": "inactive"}
        ]

        result = generate_weekly_hr_brief(onboarding, offboarding, self.report_date)
        report = result["report"]
        audit_log = result["audit_log"]

        self.assertIn("本周总计入职人数: 2人", report)
        self.assertIn("本周总计离职人数: 1人", report)
        self.assertIn("本周人员净增减: 1人", report)
        self.assertIn("Alice (ID: E001)", report)
        self.assertIn("Charlie (ID: E003)", report)
        self.assertTrue(any("Calculated statistics: Onboarding=2, Offboarding=1, Net=1" in log for log in audit_log))

    def test_dirty_data_self_healing(self):
        """Test deduplication and fixing missing fields."""
        onboarding = [
            {"id": "E001", "name": "Alice", "department": "Engineering"},
            {"id": "E001", "name": "Alice Duplicate", "department": "Engineering"}, # Duplicate ID
            {"id": "E004"} # Missing name and department
        ]

        result = generate_weekly_hr_brief(onboarding_data=onboarding, report_date=self.report_date)
        report = result["report"]
        audit_log = result["audit_log"]

        self.assertIn("本周总计入职人数: 2人", report)
        self.assertIn("Unknown (ID: E004)", report)
        self.assertIn("Unassigned", report)
        self.assertTrue(any("Deduplicated onboarding record for ID: E001" in log for log in audit_log))

    def test_missing_parameters_defaults(self):
        """Test zero-configuration by passing None or missing data."""
        result = generate_weekly_hr_brief()
        report = result["report"]
        audit_log = result["audit_log"]

        self.assertIn("本周总计入职人数: 0人", report)
        self.assertIn("本周总计离职人数: 0人", report)
        self.assertIn("本周人员净增减: 0人", report)
        self.assertIn("本周无新入职人员", report)
        self.assertIn("本周无离职人员", report)

        # Check if default date was used (today's date)
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(f"汇报日期: {today}", report)

        self.assertTrue(any("Onboarding data is missing" in log for log in audit_log))
        self.assertTrue(any("Offboarding data is missing" in log for log in audit_log))
        self.assertTrue(any("Report date is missing" in log for log in audit_log))

    def test_extreme_edge_cases(self):
        """Test extreme cases like passing non-list types for data."""
        result = generate_weekly_hr_brief(onboarding_data="not a list", offboarding_data={"dict": "invalid"})
        report = result["report"]
        audit_log = result["audit_log"]

        self.assertIn("本周总计入职人数: 0人", report)
        self.assertIn("本周总计离职人数: 0人", report)

        self.assertTrue(any("Warning: onboarding data is not a list" in log for log in audit_log))
        self.assertTrue(any("Warning: offboarding data is not a list" in log for log in audit_log))

    def test_list_with_invalid_items(self):
        """Test lists containing non-dictionary items."""
        onboarding = [
            {"id": "E005", "name": "Dave"},
            "invalid_string_item",
            12345
        ]

        result = generate_weekly_hr_brief(onboarding_data=onboarding)
        report = result["report"]
        audit_log = result["audit_log"]

        self.assertIn("本周总计入职人数: 1人", report)
        self.assertIn("Dave (ID: E005)", report)

        self.assertTrue(any("Warning: Item at index 1 in onboarding is not a dictionary" in log for log in audit_log))
        self.assertTrue(any("Warning: Item at index 2 in onboarding is not a dictionary" in log for log in audit_log))

if __name__ == '__main__':
    unittest.main()

import unittest
import os
import datetime
from ultra_modules.monthly_254_baseline_auditor_cli_one_click import run, strip_control_chars

class TestMonthly254BaselineAuditor(unittest.TestCase):

    def setUp(self):
        # Ensure test output files are cleaned up before and after tests
        self.output_files = ["test_report.json", "test_report.xlsx"]
        for f in self.output_files:
            if os.path.exists(f):
                os.remove(f)

    def tearDown(self):
        for f in self.output_files:
            if os.path.exists(f):
                os.remove(f)

    def test_normal_functionality(self):
        # Test Case 1: Normal data processing and metrics calculation
        data = [
            {"id": "1", "hire_date": "2023-10-01", "status": "active"},
            {"id": "2", "hire_date": "2023-10-01", "status": "resigned", "resign_date": "2023-10-10"}
        ]
        # Using a fixed report date for predictable results
        report_date = datetime.date(2023, 10, 15)

        results = run(data=data, output_format="both", output_prefix="test_report", report_date=report_date)

        self.assertEqual(results["total_hires"], 2)
        self.assertEqual(results["retained_7_days"], 2) # Both were retained for at least 7 days
        self.assertEqual(results["7_day_retention_rate"], 1.0)
        self.assertAlmostEqual(results["baseline_254_achievement_rate"], 2 / 254.0)

        # Check file outputs
        self.assertTrue(os.path.exists("test_report.json"))
        # Excel might not be created if openpyxl is not installed, so we gracefully handle that
        # But if openpyxl is installed, it should be there.
        try:
            import openpyxl
            self.assertTrue(os.path.exists("test_report.xlsx"))
        except ImportError:
            pass

    def test_dirty_data_self_healing(self):
        # Test Case 2: Dirty data (missing dates, invalid dates, empty dict)
        data = [
            {"id": "1", "hire_date": "invalid_date", "status": "active"},
            {"id": "2"}, # Missing hire_date and status
            {} # Empty dict should be ignored
        ]
        report_date = datetime.date(2023, 10, 15)

        results = run(data=data, output_format="json", output_prefix="test_report", report_date=report_date)

        self.assertEqual(results["total_hires"], 2)
        # Because hire_date is invalid/missing, fallback sets it to report_date.
        # Thus, retention will be 0 days (< 7 days)
        self.assertEqual(results["retained_7_days"], 0)
        self.assertEqual(results["7_day_retention_rate"], 0.0)

    def test_missing_parameter_default_fallback(self):
        # Test Case 3: Calling run() with zero parameters
        # Should use DEFAULT_DATA and not crash
        results = run(output_prefix="test_report_default")

        self.assertTrue("total_hires" in results)
        self.assertTrue("baseline_254_achievement_rate" in results)

        if os.path.exists("test_report_default.json"):
            os.remove("test_report_default.json")
        if os.path.exists("test_report_default.xlsx"):
            os.remove("test_report_default.xlsx")

    def test_extreme_boundaries(self):
        # Test Case 4: Extreme boundaries (e.g., 254+ hires for 100%+ achievement, 0 hires)

        # Zero hires
        results_zero = run(data=[], output_format="json", output_prefix="test_report")
        self.assertEqual(results_zero["total_hires"], 0)
        self.assertEqual(results_zero["baseline_254_achievement_rate"], 0.0)
        self.assertEqual(results_zero["7_day_retention_rate"], 0.0)

        # 254 hires
        data_full = [{"id": str(i), "hire_date": "2023-10-01"} for i in range(254)]
        report_date = datetime.date(2023, 10, 15)
        results_full = run(data=data_full, output_format="json", output_prefix="test_report", report_date=report_date)

        self.assertEqual(results_full["total_hires"], 254)
        self.assertEqual(results_full["baseline_254_achievement_rate"], 1.0)
        self.assertEqual(results_full["7_day_retention_rate"], 1.0) # all active and >7 days

    def test_excel_control_character_strip(self):
        # Test Case 5: Ensure strings with control characters are stripped correctly
        # so Excel export doesn't crash

        dirty_string = "Bob\x00Smith"
        clean_string = strip_control_chars(dirty_string)
        self.assertEqual(clean_string, "BobSmith")

        # Test that running with dirty data defaults doesn't crash the Excel export
        try:
            import openpyxl
            # The DEFAULT_DATA in the module includes a \x00 character for testing this implicitly
            # Let's run it and verify the file is created without errors.
            run(output_format="excel", output_prefix="test_report_excel_clean")
            self.assertTrue(os.path.exists("test_report_excel_clean.xlsx"))
            os.remove("test_report_excel_clean.xlsx")
        except ImportError:
            pass

if __name__ == "__main__":
    unittest.main()

import unittest
import os
import json
import datetime
from ultra_modules.supplier_policy_sqlite_matcher_cli_one_click import SupplierPolicyMatcher


class TestSupplierPolicyMatcher(unittest.TestCase):
    def setUp(self):
        # We use an in-memory database
        self.matcher = SupplierPolicyMatcher()
        self.test_json = "test_output.json"
        self.test_excel = "test_output.xlsx"

    def tearDown(self):
        if os.path.exists(self.test_json):
            os.remove(self.test_json)
        if os.path.exists(self.test_excel):
            os.remove(self.test_excel)
        # Close the connection
        self.matcher.conn.close()

    def test_normal_operation_exact_matching(self):
        """Test normal operation with exact date and job matching."""
        self.matcher.add_policy("Supplier A", "Backend", "2023-01-01 00:00:00.000", "2023-06-30 23:59:59.999", 200.0)
        self.matcher.add_policy("Supplier B", "Backend", "2023-07-01 00:00:00.000", "2023-12-31 23:59:59.999", 220.0)

        # Match for Supplier A
        results_a = self.matcher.match("2023-03-15 12:00:00.000", "Backend")
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0]["supplier_name"], "Supplier A")
        self.assertEqual(results_a[0]["unit_price"], 200.0)

        # Match for Supplier B
        results_b = self.matcher.match("2023-10-01 00:00:00.000", "Backend")
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0]["supplier_name"], "Supplier B")

    def test_dirty_data_self_healing(self):
        """Test dirty data like None values, unformatted dates, or control characters."""
        # None supplier name and job type, invalid dates
        self.matcher.add_policy(None, None, "bad-date", None, None)

        # Should fallback to 'Unknown Supplier' and 'General', '1970-01-01 00:00:00.000' and '2099-12-31 23:59:59.999'
        results = self.matcher.match("2024-01-01 12:00:00.000", "General")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["supplier_name"], "Unknown Supplier")
        self.assertEqual(results[0]["start_date"], "1970-01-01 00:00:00.000")
        self.assertEqual(results[0]["end_date"], "2099-12-31 23:59:59.999")
        self.assertEqual(results[0]["unit_price"], 0.0)

        # Add dirty data with control character
        self.matcher.add_policy("Bad\x00Supplier", "Hacker", "2023-01-01", "2023-12-31", 100.0)
        results2 = self.matcher.match("2023-06-01")
        self.assertEqual(len(results2), 2)  # Should match both policies now

        # Try export to check control character stripping
        self.matcher.export_excel(results2, self.test_excel)
        self.assertTrue(os.path.exists(self.test_excel))

    def test_missing_parameter_fallback(self):
        """Test missing parameter default fallbacks."""
        # Using run_cli_one_click without parameters
        self.matcher.add_policy("Default Supplier", "Any Job", "2023-01-01", "2099-12-31", 50.0)

        result = self.matcher.run_cli_one_click() # No target date, should use current time
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["matched_count"] > 0)

        self.assertTrue(os.path.exists('output.json'))
        if os.path.exists('output.json'):
            os.remove('output.json')
        self.assertTrue(os.path.exists('output.xlsx'))
        if os.path.exists('output.xlsx'):
            os.remove('output.xlsx')

    def test_extreme_boundary_cases(self):
        """Test exact millisecond boundaries."""
        self.matcher.add_policy("Boundary Supplier", "Tester", "2023-01-01 00:00:00.000", "2023-01-01 00:00:00.001", 99.9)

        # Exact match start
        results_start = self.matcher.match("2023-01-01 00:00:00.000", "Tester")
        self.assertEqual(len(results_start), 1)

        # Exact match end
        results_end = self.matcher.match("2023-01-01 00:00:00.001", "Tester")
        self.assertEqual(len(results_end), 1)

        # Just outside end
        results_out = self.matcher.match("2023-01-01 00:00:00.002", "Tester")
        self.assertEqual(len(results_out), 0)

    def test_full_run_cli_one_click_with_exports(self):
        """Test full one-click run with custom export paths."""
        self.matcher.add_policy("Full Run Supplier", "Data Scientist", "2020-01-01", "2025-12-31", 300.0)

        result = self.matcher.run_cli_one_click(
            target_date="2024-05-15",
            job_type="Data Scientist",
            export_json_path=self.test_json,
            export_excel_path=self.test_excel
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["results"][0]["unit_price"], 300.0)

        # Validate JSON export
        self.assertTrue(os.path.exists(self.test_json))
        with open(self.test_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["supplier_name"], "Full Run Supplier")

        # Validate Excel export
        self.assertTrue(os.path.exists(self.test_excel))


if __name__ == '__main__':
    unittest.main()

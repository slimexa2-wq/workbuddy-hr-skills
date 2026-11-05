import unittest
import datetime
from ultra_modules.monthly_254_baseline_auditor_core_engine import audit_254_baseline, parse_date

class TestMonthly254BaselineAuditorCoreEngine(unittest.TestCase):
    def setUp(self):
        self.report_date = "2023-11-01"

    def test_normal_achieved(self):
        # Generate 254 valid records
        records = [
            {"hire_date": "2023-10-01", "leave_date": "2023-10-15"}
            for _ in range(254)
        ]
        result = audit_254_baseline(records, baseline=254, min_days=7, report_date=self.report_date)

        self.assertEqual(result["baseline"], 254)
        self.assertEqual(result["qualified_count"], 254)
        self.assertEqual(result["achievement_rate"], 1.0)
        self.assertTrue(result["is_achieved"])

    def test_normal_not_achieved(self):
        # 100 valid, 150 invalid (< 7 days)
        records = [
            {"hire_date": "2023-10-01", "leave_date": "2023-10-15"} for _ in range(100)
        ] + [
            {"hire_date": "2023-10-01", "leave_date": "2023-10-05"} for _ in range(150)
        ]
        result = audit_254_baseline(records, baseline=254, min_days=7, report_date=self.report_date)

        self.assertEqual(result["qualified_count"], 100)
        self.assertAlmostEqual(result["achievement_rate"], 100 / 254, places=4)
        self.assertFalse(result["is_achieved"])

    def test_dirty_data_self_healing(self):
        records = [
            None, # Invalid type
            "dirty string", # Invalid type
            {"hire_date": "2023/10/01", "leave_date": "2023.10.10"}, # Alternate separators (9 days, valid)
            {"hire_date": "20231001", "leave_date": None}, # YYYYMMDD format, no leave date (valid if report_date is later)
            {"hire_date": "invalid_date", "leave_date": "2023-10-10"}, # Unparseable hire date (invalid)
            {"hire_date": "2023-10-01T12:00:00Z", "leave_date": "2023-10-15 15:30:00"}, # With time component (14 days, valid)
            {}, # Missing dates (invalid)
        ]
        result = audit_254_baseline(records, baseline=10, min_days=7, report_date="2023-10-31")

        # Valid records:
        # 1. 2023/10/01 to 2023.10.10 -> 9 days (valid)
        # 2. 20231001 to 2023-10-31 -> 30 days (valid)
        # 3. 2023-10-01T12:00:00Z to 2023-10-15 15:30:00 -> 14 days (valid)
        self.assertEqual(result["qualified_count"], 3)

    def test_default_parameter_fallback(self):
        # Call with no arguments
        result = audit_254_baseline()
        self.assertEqual(result["baseline"], 254.0)
        self.assertEqual(result["min_days"], 7)
        self.assertEqual(result["qualified_count"], 0)
        self.assertEqual(result["achievement_rate"], 0.0)
        self.assertFalse(result["is_achieved"])
        self.assertEqual(result["report_date"], datetime.date.today().isoformat())

        # Call with invalid parameter types
        result = audit_254_baseline(
            records="not a list",
            baseline="invalid",
            min_days="invalid",
            report_date="invalid"
        )
        self.assertEqual(result["baseline"], 254.0)
        self.assertEqual(result["min_days"], 7)
        self.assertEqual(result["qualified_count"], 0)
        self.assertEqual(result["report_date"], datetime.date.today().isoformat())

        # Call with negative baseline or zero
        result = audit_254_baseline(baseline=-10)
        self.assertEqual(result["baseline"], 254.0)

        result = audit_254_baseline(baseline=0)
        self.assertEqual(result["baseline"], 254.0)

    def test_extreme_boundaries(self):
        # Very large numbers and negative min_days
        records = [
            {"hire_date": "2023-10-05", "leave_date": "2023-10-01"}, # Negative 4 days
        ]

        # If min_days is -5, then -4 days is >= -5, so it should qualify
        result = audit_254_baseline(records, baseline=1, min_days=-5, report_date=self.report_date)
        self.assertEqual(result["qualified_count"], 1)
        self.assertTrue(result["is_achieved"])

        # Extreme large baseline
        result = audit_254_baseline(records, baseline=1e9, min_days=-5, report_date=self.report_date)
        self.assertEqual(result["qualified_count"], 1)
        self.assertAlmostEqual(result["achievement_rate"], 1 / 1e9, places=12)
        self.assertFalse(result["is_achieved"])

        # datetime.date object testing via parse_date helper directly
        d_obj = datetime.date(2023, 1, 1)
        self.assertEqual(parse_date(d_obj), d_obj)
        dt_obj = datetime.datetime(2023, 1, 1, 12, 0)
        self.assertEqual(parse_date(dt_obj), d_obj)

if __name__ == '__main__':
    unittest.main()

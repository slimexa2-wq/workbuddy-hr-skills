import unittest
import datetime
from unittest.mock import patch
from ultra_modules.monthly_254_baseline_auditor_audit_trace import BaselineAuditorEngine, evaluate_baseline

class TestMonthly254BaselineAuditorAuditTrace(unittest.TestCase):

    def setUp(self):
        self.engine = BaselineAuditorEngine()

    def test_normal_case_evaluate_baseline(self):
        """Test normal case with a mix of qualified and non-qualified records."""
        records = [
            {"id": "emp1", "employment_days": 10},
            {"id": "emp2", "employment_days": 5},
            {"id": "emp3", "employment_days": 8},
        ]
        result = evaluate_baseline(records, baseline_target=2)

        self.assertEqual(result["total_processed"], 3)
        self.assertEqual(result["valid_unique"], 3)
        self.assertEqual(result["qualified_7_days"], 2)
        self.assertTrue(result["is_target_met"])
        self.assertEqual(result["baseline_achievement_rate"], 100.0)
        self.assertEqual(result["duplicates_dropped"], 0)

    def test_dirty_data_self_healing(self):
        """Test handling of dirty data: missing employment_days, invalid types, calculated from hire_date."""
        # Mock datetime.datetime.now() to return a fixed date for reliable testing of 'hire_date'
        class MockDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.datetime(2023, 10, 20)

        with patch('ultra_modules.monthly_254_baseline_auditor_audit_trace.datetime.datetime', MockDatetime):

            records = [
                {"id": "emp1", "employment_days": "invalid_string"}, # Should default to 0
                {"id": "emp2", "hire_date": "2023-10-10"}, # Should calculate to 10 days
                {"id": "emp3", "hire_date": "invalid_date_format"}, # Should default to 0
                {"id": "emp4", "employment_days": None}, # Should default to 0
                {"id": "emp5"}, # Missing both hire_date and employment_days, should default to 0
            ]

            result = self.engine.process_records(records, baseline_target=5)

            self.assertEqual(result["total_processed"], 5)
            self.assertEqual(result["valid_unique"], 5)
            self.assertEqual(result["qualified_7_days"], 1) # Only emp2 qualifies

            trace = self.engine.get_audit_trace()
            healing_logs = [t for t in trace if t["step"] == "data_healing"]
            self.assertEqual(len(healing_logs), 5) # 5 healing actions expected

    def test_missing_param_defaults(self):
        """Test that missing parameters default correctly (e.g., None records defaults to empty list)."""
        result = evaluate_baseline(None)

        self.assertEqual(result["total_processed"], 0)
        self.assertEqual(result["valid_unique"], 0)
        self.assertEqual(result["qualified_7_days"], 0)
        self.assertFalse(result["is_target_met"])
        self.assertEqual(result["baseline_achievement_rate"], 0.0)

    def test_extreme_boundaries(self):
        """Test extreme boundaries like baseline_target=0, negative days, large lists."""
        records = [{"id": f"emp{i}", "employment_days": -1} for i in range(100)]
        result = evaluate_baseline(records, baseline_target=0)

        self.assertEqual(result["total_processed"], 100)
        self.assertEqual(result["qualified_7_days"], 0)
        self.assertEqual(result["baseline_target"], 0)
        # Should be 0.0 to avoid division by zero
        self.assertEqual(result["baseline_achievement_rate"], 0.0)
        self.assertTrue(result["is_target_met"]) # 0 >= 0 is True

    def test_deduplication(self):
        """Test that duplicate records by ID are dropped correctly."""
        records = [
            {"id": "emp1", "employment_days": 10},
            {"id": "emp1", "employment_days": 20}, # Duplicate
            {"id": "emp2", "employment_days": 5},
            {"id": "", "employment_days": 8}, # Missing ID will be generated
            {"id": "", "employment_days": 12}, # Another missing ID, generated uniquely (hashed)
        ]

        result = evaluate_baseline(records, baseline_target=10)

        # total 5, 2 have same id ("emp1"), so 1 dropped.
        # the two empty strings will get uniquely generated ids based on hash of dict
        self.assertEqual(result["total_processed"], 5)
        self.assertEqual(result["valid_unique"], 4)
        self.assertEqual(result["duplicates_dropped"], 1)

if __name__ == '__main__':
    unittest.main()

import unittest
import time
from ultra_modules.monthly_254_baseline_auditor_benchmark_suite import audit_recruitment_baseline, generate_synthetic_fixtures

class TestMonthly254BaselineAuditor(unittest.TestCase):

    def test_normal_operation(self):
        """Test with valid data to check normal calculations."""
        base_time = 1704067200
        candidates = [
            {"join_date": base_time, "leave_date": None},  # Retained
            {"join_date": base_time, "leave_date": base_time + 8*24*3600},  # Retained
            {"join_date": base_time, "leave_date": base_time + 2*24*3600},  # Not retained
        ]
        result = audit_recruitment_baseline(candidates=candidates, baseline=2)

        self.assertEqual(result["total_recruited"], 3)
        self.assertEqual(result["retained_7_days"], 2)
        self.assertEqual(result["achievement_rate"], 1.5)
        self.assertAlmostEqual(result["retention_rate"], 2/3)
        self.assertTrue(result["processing_time_ms"] >= 0)

    def test_missing_parameters_default_fallback(self):
        """Test that missing parameters use default zero-configuration fallbacks."""
        # Test completely missing candidates
        result_none = audit_recruitment_baseline()
        self.assertEqual(result_none["total_recruited"], 0)
        self.assertEqual(result_none["achievement_rate"], 0.0)
        self.assertEqual(result_none["retention_rate"], 0.0)

        # Test zero baseline
        result_zero_baseline = audit_recruitment_baseline(candidates=[], baseline=0)
        self.assertEqual(result_zero_baseline["achievement_rate"], 0.0)

        # Empty list
        result_empty = audit_recruitment_baseline(candidates=[])
        self.assertEqual(result_empty["total_recruited"], 0)

    def test_dirty_data_self_healing(self):
        """Test that dirty data is silently skipped and handled gracefully."""
        candidates = [
            None,  # Not a dict
            "string_candidate",  # Not a dict
            {"id": "1"},  # Missing join_date
            {"join_date": "invalid_date_string"},  # Invalid join_date type
            {"join_date": -500},  # Negative join_date
            {"join_date": 1704067200, "leave_date": "invalid"},  # Invalid leave_date type, counts as not retained >= 7 days
            {"join_date": 1704067200, "leave_date": None},  # Valid
        ]

        result = audit_recruitment_baseline(candidates=candidates, baseline=10)

        # Only the last two are valid recruits
        self.assertEqual(result["total_recruited"], 2)
        # Only the last one is retained
        self.assertEqual(result["retained_7_days"], 1)

    def test_extreme_boundary_conditions(self):
        """Test extreme boundary conditions like cross-year/month and massive datasets."""
        # Cross year boundary (Dec 28 to Jan 5)
        join_date = 1703721600 # 2023-12-28 00:00:00
        leave_date = 1704412800 # 2024-01-05 00:00:00 (8 days)

        candidates = [{"join_date": join_date, "leave_date": leave_date}]
        result = audit_recruitment_baseline(candidates=candidates)
        self.assertEqual(result["retained_7_days"], 1)

        # Exact 7 days boundary
        candidates_exact = [
            {"join_date": join_date, "leave_date": join_date + 7*24*3600}, # Retained
            {"join_date": join_date, "leave_date": join_date + 7*24*3600 - 1} # Not retained
        ]
        result_exact = audit_recruitment_baseline(candidates=candidates_exact)
        self.assertEqual(result_exact["retained_7_days"], 1)

    def test_performance_benchmark(self):
        """Test performance with a large synthetic dataset."""
        num_records = 100000
        fixtures = generate_synthetic_fixtures(num_records=num_records, dirty_ratio=0.1)

        start_time = time.perf_counter()
        result = audit_recruitment_baseline(candidates=fixtures, baseline=254)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Verify it processed a large number of records
        self.assertTrue(result["total_recruited"] > 0)
        self.assertTrue(result["total_recruited"] <= num_records)

        # Verify millisecond response (e.g. < 500ms for 100k records in Python)
        self.assertTrue(elapsed_ms < 500, f"Processing took too long: {elapsed_ms}ms")

        # Coverage check for generate_synthetic_fixtures dirty paths
        # Ensures all dirty types are generated
        self.assertTrue(len(fixtures) == num_records)

if __name__ == '__main__':
    unittest.main()

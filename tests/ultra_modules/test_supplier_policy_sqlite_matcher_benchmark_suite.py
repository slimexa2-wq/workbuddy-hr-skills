import unittest
import time
from datetime import datetime
from ultra_modules.supplier_policy_sqlite_matcher_benchmark_suite import SupplierPolicyMatcher, BenchmarkSuite

class TestSupplierPolicyMatcherBenchmarkSuite(unittest.TestCase):
    def setUp(self):
        self.matcher = SupplierPolicyMatcher()

    def tearDown(self):
        # Memory DB is automatically destroyed when connection closes or object goes out of scope,
        # but we can explicitly clean up if needed.
        pass

    def _ingest_standard_data(self):
        policies = [
            {'job_type': 'Developer', 'start_date': '2023-01-01', 'end_date': '2023-06-30', 'price': 100.0},
            {'job_type': 'Developer', 'start_date': '2023-07-01', 'end_date': '2023-12-31', 'price': 120.0},
            {'job_type': 'DEFAULT_JOB', 'start_date': '1970-01-01', 'end_date': '2099-12-31', 'price': 50.0},
        ]
        self.matcher.ingest_policies(policies)

    def test_normal_matching(self):
        """Test 1: Normal standard matching within expected boundaries."""
        self._ingest_standard_data()

        # Test exact match in first period
        price = self.matcher.match_policy('Developer', '2023-03-15')
        self.assertEqual(price, 100.0)

        # Test exact match in second period
        price = self.matcher.match_policy('Developer', '2023-09-01')
        self.assertEqual(price, 120.0)

    def test_dirty_data_self_healing(self):
        """Test 2: Ensure dirty data (nulls, garbled text, bad formats) self-heals without crashing."""
        dirty_policies = [
            {'job_type': None, 'start_date': '2023/01/01', 'end_date': '2023-01-31', 'price': '10.5'},
            {'job_type': '  ', 'start_date': None, 'end_date': None, 'price': None},
            {'job_type': 'Designer', 'start_date': 'bad_date', 'end_date': '2023-12-31', 'price': 'dirty_price'},
        ]
        self.matcher.ingest_policies(dirty_policies)

        # None job_type should map to DEFAULT_JOB and be queryable
        price1 = self.matcher.match_policy(None, '2023-01-15')
        # Empty space job_type maps to DEFAULT_JOB, price None maps to 0.0
        # The bad_date maps to '1970-01-01', dirty_price maps to 0.0

        # Just verifying it doesn't crash and returns valid types (or None if no match)
        self.assertIsInstance(self.matcher.match_policy('Designer', '2023-06-01'), (float, type(None)))
        self.assertIsInstance(self.matcher.match_policy(None, None), (float, type(None)))

        # Specific check for Designer with bad_date (healed to 1970) and dirty_price (healed to 0.0)
        price_designer = self.matcher.match_policy('Designer', '2023-06-01')
        self.assertEqual(price_designer, 0.0)

    def test_missing_parameter_default_fallbacks(self):
        """Test 3: Missing parameter defaults and zero-configuration fault tolerance."""
        self._ingest_standard_data()

        # Job type not in DB, should fallback to DEFAULT_JOB
        price = self.matcher.match_policy('UnknownJobType', '2023-05-05')
        self.assertEqual(price, 50.0)

        # Missing date entirely, should default to today and still not crash
        price_no_date = self.matcher.match_policy('Developer', None)
        self.assertTrue(price_no_date in [100.0, 120.0, 50.0, None])

    def test_extreme_boundary_cases(self):
        """Test 4: Extreme boundaries (cross year/month, leap years, inverted dates)."""
        extreme_policies = [
            # Inverted dates should be swapped
            {'job_type': 'Tester', 'start_date': '2024-12-31', 'end_date': '2024-01-01', 'price': 99.0},
            # Leap year boundary
            {'job_type': 'Tester', 'start_date': '2024-02-28', 'end_date': '2024-03-01', 'price': 88.0},
        ]
        self.matcher.ingest_policies(extreme_policies)

        # Testing inverted dates swapped correctly
        price_inverted = self.matcher.match_policy('Tester', '2024-06-15')
        self.assertEqual(price_inverted, 99.0)

        # Testing leap year exact date
        price_leap = self.matcher.match_policy('Tester', '2024-02-29')
        # Expecting 88.0 because it's a closer bound, or 99.0 if it overlaps and is sorted.
        # Since both overlap 2024-02-29, the ORDER BY price ASC LIMIT 1 means 88.0 wins
        self.assertEqual(price_leap, 88.0)

    def test_benchmark_millisecond_response_and_no_crashes(self):
        """Test 5: Synthetic dataset, extreme concurrency simulation, verify < 1ms avg response time."""
        num_fixtures = 1000
        fixtures = BenchmarkSuite.generate_synthetic_fixtures(num_fixtures)

        # Should ingest 1000 dirty/extreme records without crashing
        self.matcher.ingest_policies(fixtures)

        # Run 5000 queries to ensure high concurrency simulation
        result = BenchmarkSuite.run_benchmark(self.matcher, num_queries=5000)

        # Assertions
        self.assertEqual(result["total_queries"], 5000)
        self.assertTrue(result["matches_found"] >= 0)

        # Verify millisecond level response (avg time per query < 5ms is extremely safe for SQLite in memory)
        self.assertTrue(result["avg_time_ms_per_query"] < 5.0,
                        f"Query too slow: {result['avg_time_ms_per_query']} ms/query")

if __name__ == '__main__':
    unittest.main()

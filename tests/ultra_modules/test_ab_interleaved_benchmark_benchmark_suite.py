import unittest
import time
import math

from ultra_modules.ab_interleaved_benchmark_benchmark_suite import (
    _clean_data,
    calculate_median_and_iqr,
    run_abba_interleaved_benchmark,
    ABBenchmarkSuite
)


class TestABBenchmarkSuite(unittest.TestCase):

    def test_clean_data_normal(self):
        """1. Normal data test for _clean_data"""
        self.assertEqual(_clean_data(10), 10.0)
        self.assertEqual(_clean_data("10.5"), 10.5)

    def test_clean_data_dirty(self):
        """2. Dirty data self-healing test for _clean_data"""
        self.assertEqual(_clean_data(None, 5.0), 5.0)
        self.assertEqual(_clean_data("invalid", 3.0), 3.0)
        self.assertEqual(_clean_data(math.nan, 2.0), 2.0)
        self.assertEqual(_clean_data(math.inf, 1.0), 1.0)
        self.assertEqual(_clean_data({"a": 1}, 4.0), 4.0)

    def test_calculate_median_and_iqr(self):
        """3. Test median and IQR calculation including extreme edge cases"""
        # Empty array
        self.assertEqual(calculate_median_and_iqr([]), (0.0, 0.0))
        # Small array
        self.assertEqual(calculate_median_and_iqr([1.0]), (1.0, 0.0))
        self.assertEqual(calculate_median_and_iqr([1.0, 2.0]), (1.5, 0.0))
        # Normal array
        med, iqr = calculate_median_and_iqr([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(med, 3.0)
        self.assertEqual(iqr, 4.0 - 2.0) # q3 - q1 (approximation index 3 and 1)

    def test_run_benchmark_missing_params(self):
        """4. Missing parameter fallback test for run_abba_interleaved_benchmark"""
        # Test with missing callable parameters
        res = run_abba_interleaved_benchmark(None, None)
        self.assertIn("func_a_median", res)
        self.assertIn("func_b_median", res)
        self.assertIn("is_significant", res)
        self.assertIn("faster_func", res)

        # Test with bad iterations/warmup params
        def dummy(): pass
        res = run_abba_interleaved_benchmark(dummy, dummy, iterations="bad", warmup=None)
        self.assertTrue(res["func_a_median"] >= 0)

    def test_run_benchmark_normal_and_extreme(self):
        """5. Normal benchmark execution and extreme edge case (crashing functions)"""
        def fast_func():
            pass

        def slow_func():
            time.sleep(0.01)

        def crashing_func():
            raise ValueError("I crash")

        suite = ABBenchmarkSuite()

        # Normal execution
        res = suite.run_benchmark(fast_func, slow_func, iterations=2, warmup=1)
        self.assertEqual(res["faster_func"], "A")
        self.assertTrue(res["func_a_median"] < res["func_b_median"])

        # Crashing execution (extreme edge case: zero crash)
        res_crash = suite.run_benchmark(crashing_func, slow_func, iterations=2, warmup=0)
        self.assertTrue(res_crash["func_a_median"] >= 0)

        # Ultra concurrency / large iterations limit test
        res_large = suite.run_benchmark(fast_func, fast_func, iterations=1000, warmup=10)
        self.assertIn(res_large["faster_func"], ["A", "B", "TIE"]) # Both fast, shouldn't crash, result could be anything due to micro-variations.


if __name__ == '__main__':
    unittest.main()

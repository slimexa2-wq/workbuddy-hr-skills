import unittest
import time
from typing import List
from ultra_modules.ab_interleaved_benchmark_audit_trace import ABBAInterleavedBenchmark

class TestABBAInterleavedBenchmark(unittest.TestCase):

    def test_normal_execution_and_significance(self):
        """Test normal execution where B is significantly slower than A"""
        def func_a():
            time.sleep(0.001)

        def func_b():
            time.sleep(0.01) # B is 10x slower

        benchmark = ABBAInterleavedBenchmark(func_a, func_b, iterations=10)
        result = benchmark.run()

        self.assertIn(result["winner"], ["A", "B", "Tie"])
        self.assertGreater(result["iterations_run"], 0)

        # B should be slower, so A should have a smaller median time -> A is the winner
        self.assertEqual(result["winner"], "A")

        # Expect significance because difference is large
        self.assertTrue(result["is_significant"])

        audit_log = benchmark.get_audit_log()
        self.assertTrue(len(audit_log) > 0)
        self.assertTrue(any(log.get("func") == "A" for log in audit_log))
        self.assertTrue(any(log.get("func") == "B" for log in audit_log))

    def test_exception_self_healing(self):
        """Test that exceptions in functions do not crash the benchmark and are logged"""
        def func_a():
            pass

        def func_b_fail():
            raise ValueError("Intentional crash")

        benchmark = ABBAInterleavedBenchmark(func_a, func_b_fail, iterations=5)
        result = benchmark.run()

        audit_log = benchmark.get_audit_log()

        # Check that error is in audit log
        error_logs = [log for log in audit_log if "error" in log.get("status", "")]
        self.assertTrue(len(error_logs) > 0)
        self.assertIn("Intentional crash", error_logs[0]["status"])

        # Benchmark should complete successfully despite errors
        self.assertIn(result["winner"], ["A", "B", "Tie"])
        self.assertIsNotNone(result["median_A"])
        self.assertIsNotNone(result["median_B"])

    def test_missing_parameter_defaults(self):
        """Test zero-configuration default for missing or invalid iterations parameter"""
        def func_a(): pass
        def func_b(): pass

        # Invalid iterations parameter, should default to 100
        benchmark = ABBAInterleavedBenchmark(func_a, func_b, iterations=-5)
        self.assertEqual(benchmark.iterations, 100)

        # Run with a smaller number to save test time
        benchmark.iterations = 2
        result = benchmark.run()
        self.assertEqual(result["iterations_run"], 2)

    def test_exact_identical_timings_deduplication(self):
        """Test that identical timings are deduplicated to avoid zero variance issues"""
        class MockBenchmark(ABBAInterleavedBenchmark):
            def _execute_with_timing(self, func, func_name, step):
                # Hardcode exact same time
                super()._execute_with_timing(func, func_name, step) # Call to trigger audit
                return 0.5

        def func_a(): pass
        def func_b(): pass

        benchmark = MockBenchmark(func_a, func_b, iterations=5)
        result = benchmark.run()

        # All returns are 0.5, after deduplication, clean list should be length 1
        # Therefore IQR should be 0.
        self.assertEqual(result["iqr_A"], 0.0)
        self.assertEqual(result["iqr_B"], 0.0)
        self.assertEqual(result["median_A"], 0.5)
        self.assertEqual(result["median_B"], 0.5)

        # Medians are identical, difference is 0, so not significant, Tie
        self.assertFalse(result["is_significant"])
        self.assertEqual(result["winner"], "Tie")

        # Check audit log for deduplication event
        audit_log = benchmark.get_audit_log()
        dedup_logs = [log for log in audit_log if log.get("action") == "clean_and_deduplicate"]
        self.assertTrue(len(dedup_logs) > 0)
        # Original was 5 iterations * 2 executions per iteration = 10.
        # After deduplication, new_len should be 1.
        for dl in dedup_logs:
            self.assertEqual(dl["original_len"], 10)
            self.assertEqual(dl["new_len"], 1)

    def test_extreme_boundary_negative_values(self):
        """Test silent repair of dirty data: removing/correcting negative time durations"""
        class MockNegativeBenchmark(ABBAInterleavedBenchmark):
            def _execute_with_timing(self, func, func_name, step):
                # Return negative value
                super()._execute_with_timing(func, func_name, step) # Call to trigger audit
                return -1.0

        def func_a(): pass
        def func_b(): pass

        benchmark = MockNegativeBenchmark(func_a, func_b, iterations=3)
        result = benchmark.run()

        # _clean_and_deduplicate should filter out negatives, and return [0.0] as fallback
        self.assertEqual(result["median_A"], 0.0)
        self.assertEqual(result["median_B"], 0.0)
        self.assertEqual(result["winner"], "Tie")
        self.assertFalse(result["is_significant"])

if __name__ == '__main__':
    unittest.main()

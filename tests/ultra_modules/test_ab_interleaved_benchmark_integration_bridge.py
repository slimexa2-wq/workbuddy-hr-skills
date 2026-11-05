import unittest
import math
from ultra_modules.ab_interleaved_benchmark_integration_bridge import (
    _calculate_median,
    _calculate_iqr,
    _safe_float,
    auto_bridge_schema,
    analyze_abba_benchmark
)

class TestABInterleavedBenchmarkIntegrationBridge(unittest.TestCase):

    def test_calculate_median_normal_and_empty(self):
        """Test median calculation with normal and empty lists."""
        self.assertEqual(_calculate_median([]), 0.0)
        self.assertEqual(_calculate_median([5]), 5.0)
        self.assertEqual(_calculate_median([1, 3, 5]), 3.0)
        self.assertEqual(_calculate_median([1, 2, 3, 4]), 2.5)

    def test_calculate_iqr_normal_and_boundary(self):
        """Test IQR calculation with varied lists, including boundaries."""
        self.assertEqual(_calculate_iqr([]), 0.0)
        self.assertEqual(_calculate_iqr([10]), 0.0)
        # Odd number of elements
        # [1, 2, 3, 4, 5] -> Q1=[1,2] med=1.5, Q3=[4,5] med=4.5 -> IQR=3.0
        self.assertEqual(_calculate_iqr([1, 2, 3, 4, 5]), 3.0)
        # Even number of elements
        # [1, 2, 3, 4] -> Q1=[1,2] med=1.5, Q3=[3,4] med=3.5 -> IQR=2.0
        self.assertEqual(_calculate_iqr([1, 2, 3, 4]), 2.0)

    def test_safe_float_dirty_data(self):
        """Test safe float conversion with dirty data, self-healing fallbacks."""
        self.assertEqual(_safe_float(None), 0.0)
        self.assertEqual(_safe_float("invalid"), 0.0)
        self.assertEqual(_safe_float(float('nan')), 0.0)
        self.assertEqual(_safe_float(float('inf')), 0.0)
        self.assertEqual(_safe_float(10), 10.0)
        self.assertEqual(_safe_float("15.5", default=1.0), 15.5)
        self.assertEqual(_safe_float(object(), default=2.0), 2.0)

    def test_auto_bridge_schema_forward_compatibility(self):
        """Test bridging of various old/new schema versions."""
        # Not a dict
        self.assertEqual(auto_bridge_schema(None), {})
        self.assertEqual(auto_bridge_schema([]), {})

        # New schema
        res1 = auto_bridge_schema({'system': 'A', 'latency': 100, 'success': True})
        self.assertEqual(res1, {'system': 'A', 'latency': 100.0, 'success': True})

        # Old schema variations
        res2 = auto_bridge_schema({'sys_name': 'B', 'resp_time_ms': '200', 'is_ok': False})
        self.assertEqual(res2, {'system': 'B', 'latency': 200.0, 'success': False})

        res3 = auto_bridge_schema({'system': 'C', 'time': 50, 'status': 200})
        self.assertEqual(res3, {'system': 'C', 'latency': 50.0, 'success': True})

        res4 = auto_bridge_schema({'system': 'D', 'latency': 10, 'status': 'OK'})
        self.assertEqual(res4, {'system': 'D', 'latency': 10.0, 'success': True})

        res5 = auto_bridge_schema({'system': 'E', 'latency': 10, 'status': 'FAILED'})
        self.assertEqual(res5, {'system': 'E', 'latency': 10.0, 'success': False})

        # Missing or other fields entirely (fallbacks)
        res6 = auto_bridge_schema({'other_field': 123})
        self.assertEqual(res6, {'system': 'unknown', 'latency': 0.0, 'success': False})

    def test_analyze_abba_benchmark_comprehensive(self):
        """Test the main entry point covering normal, missing params, and statistical logic."""
        # Missing or invalid params
        self.assertEqual(analyze_abba_benchmark(None)['total_records'], 0)
        self.assertEqual(analyze_abba_benchmark("bad_data", some_kwarg=1)['total_records'], 0)

        # Test with exactly two systems to trigger comparison logic
        data = [
            {'system': 'sysA', 'latency': 100, 'success': True},
            {'system': 'sysB', 'latency': 200, 'success': True},
            {'system': 'sysA', 'latency': 110, 'success': True},
            {'system': 'sysB', 'latency': 210, 'success': False},
            "invalid_record",  # Dirty data, should be skipped
            {'system': 'sysA', 'latency': 105, 'success': True},
            {'system': 'sysB', 'latency': 190, 'success': True}
        ]
        report = analyze_abba_benchmark(data)

        self.assertEqual(report['total_records'], 7)
        self.assertIn('sysA', report['systems'])
        self.assertIn('sysB', report['systems'])

        self.assertEqual(report['systems']['sysA']['count'], 3)
        self.assertEqual(report['systems']['sysA']['success_rate'], 1.0)
        self.assertEqual(report['systems']['sysA']['latency_median'], 105.0)

        self.assertEqual(report['systems']['sysB']['count'], 3)
        # sysB successes: True, False, True -> 2 / 3
        self.assertAlmostEqual(report['systems']['sysB']['success_rate'], 2/3)
        self.assertEqual(report['systems']['sysB']['latency_median'], 200.0)

        # Comparison
        self.assertIn('comparison', report)
        self.assertTrue(report['comparison']['is_significant'])
        self.assertEqual(report['comparison']['winner'], 'sysA')

    def test_analyze_abba_benchmark_zero_iqr_significance(self):
        """Test significance when IQR is 0 but medians differ."""
        data = [
            {'system': 'A', 'latency': 10, 'success': True},
            {'system': 'A', 'latency': 10, 'success': True},
            {'system': 'B', 'latency': 20, 'success': True},
            {'system': 'B', 'latency': 20, 'success': True},
        ]
        report = analyze_abba_benchmark(data)
        self.assertTrue(report['comparison']['is_significant'])
        self.assertEqual(report['comparison']['winner'], 'A')

    def test_analyze_abba_benchmark_tie(self):
        """Test comparison when medians are exactly the same."""
        data = [
            {'system': 'A', 'latency': 10, 'success': True},
            {'system': 'B', 'latency': 10, 'success': True},
        ]
        report = analyze_abba_benchmark(data)
        self.assertFalse(report['comparison']['is_significant'])
        self.assertEqual(report['comparison']['winner'], 'tie')

    def test_analyze_abba_benchmark_one_system(self):
        """Test when only one system is present (no comparison)."""
        data = [
            {'system': 'A', 'latency': 10, 'success': True},
            {'system': 'A', 'latency': 15, 'success': True},
        ]
        report = analyze_abba_benchmark(data)
        self.assertNotIn('comparison', report)
        self.assertIn('A', report['systems'])

if __name__ == '__main__':
    unittest.main()

import unittest
import math
from ultra_modules.ab_interleaved_benchmark_core_engine import (
    _calculate_median,
    _calculate_iqr,
    _mann_whitney_u,
    analyze_interleaved_benchmark
)

class TestABInterleavedBenchmarkCoreEngine(unittest.TestCase):

    def test_calculate_median(self):
        self.assertEqual(_calculate_median([]), 0.0)
        self.assertEqual(_calculate_median([5]), 5.0)
        self.assertEqual(_calculate_median([1, 2, 3]), 2.0)
        self.assertEqual(_calculate_median([1, 2, 3, 4]), 2.5)

    def test_calculate_iqr(self):
        self.assertEqual(_calculate_iqr([]), (0.0, 0.0, 0.0))
        q1, q3, iqr = _calculate_iqr([1, 2, 3, 4, 5])
        self.assertEqual(q1, 2.0)
        self.assertEqual(q3, 4.0)
        self.assertEqual(iqr, 2.0)

        # Test percentile interpolation
        # values: 10, 20. p=0.25 -> k=(2-1)*0.25=0.25. f=0, c=1.
        # d0 = 10 * 0.75 = 7.5, d1 = 20 * 0.25 = 5.0 => q1 = 12.5
        q1, q3, iqr = _calculate_iqr([10, 20])
        self.assertEqual(q1, 12.5)
        self.assertEqual(q3, 17.5)
        self.assertEqual(iqr, 5.0)

    def test_mann_whitney_u(self):
        # Empty inputs
        u, p, z = _mann_whitney_u([], [])
        self.assertEqual((u, p, z), (0.0, 1.0, False))

        # Zero variance arrays / Sigma U = 0
        u, p, z = _mann_whitney_u([5, 5], [5, 5])
        self.assertEqual((u, p, z), (2.0, 1.0, False)) # Both rank 2.5. r1 = 5, u1=5-3=2. u2=4-2=2

        # Significant difference
        group_a = [1, 2, 3, 4, 5]
        group_b = [20, 21, 22, 23, 24]
        u, p_val, z = _mann_whitney_u(group_a, group_b)
        self.assertEqual(u, 0.0)
        self.assertTrue(p_val < 0.05)

        # No significant difference
        group_a = [10, 11, 12, 13, 14]
        group_b = [10, 11, 12, 13, 14]
        u, p_val, z = _mann_whitney_u(group_a, group_b)
        self.assertTrue(p_val > 0.05)

        # Test ties
        group_a = [1, 1, 1, 1]
        group_b = [1, 1, 2, 2]
        u, p_val, z = _mann_whitney_u(group_a, group_b)
        self.assertTrue(0 <= u <= 16)

    def test_analyze_interleaved_benchmark_normal_significant(self):
        # Normal clean data with significant difference
        data = [
            {'label': 'A', 'value': 1},
            {'label': 'A', 'value': 2},
            {'label': 'A', 'value': 3},
            {'label': 'B', 'value': 20},
            {'label': 'B', 'value': 21},
            {'label': 'B', 'value': 22}
        ]
        result = analyze_interleaved_benchmark(data, alpha=0.05)
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['significant_difference'])
        self.assertEqual(result['metrics']['A']['median'], 2.0)
        self.assertEqual(result['metrics']['B']['median'], 21.0)

    def test_analyze_interleaved_benchmark_normal_not_significant(self):
        # Normal clean data with no significant difference
        data = [
            {'label': 'X', 'value': 10},
            {'label': 'X', 'value': 11},
            {'label': 'Y', 'value': 10},
            {'label': 'Y', 'value': 11}
        ]
        result = analyze_interleaved_benchmark(data)
        self.assertEqual(result['status'], 'success')
        self.assertFalse(result['significant_difference'])

    def test_analyze_interleaved_benchmark_dirty_data(self):
        # Dirty data self-healing
        data = [
            {'label': 'A', 'value': 10},
            {'label': 'A', 'value': '20'}, # String in numeric
            {'label': 'A', 'value': None}, # None value
            {'label': 'A', 'value': 'abc'}, # Invalid string
            {'label': 'A', 'value': float('nan')}, # NaN
            {'label': 'A', 'value': float('inf')}, # Inf
            {'label': None, 'value': 30}, # None label
            {'label': '', 'value': 30}, # Empty label
            {'value': 40}, # Missing label key
            {'label': 'B'}, # Missing value key
            'not a dict', # Invalid item
            {'label': 'B', 'value': 50},
            {'label': 'B', 'value': 60}
        ]
        result = analyze_interleaved_benchmark(data)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['metrics']['A']['count'], 2) # 10 and 20
        self.assertEqual(result['metrics']['A']['median'], 15.0)
        self.assertEqual(result['metrics']['B']['count'], 2) # 50 and 60
        self.assertEqual(result['metrics']['B']['median'], 55.0)

    def test_analyze_interleaved_benchmark_missing_params(self):
        # Missing parameters / Default fallback

        # None data
        res1 = analyze_interleaved_benchmark(None)
        self.assertEqual(res1['status'], 'error')
        self.assertEqual(res1['message'], 'No valid data found.')
        self.assertFalse(res1['significant_difference'])

        # None alpha
        data = [{'label': 'A', 'value': 1}, {'label': 'B', 'value': 2}]
        res2 = analyze_interleaved_benchmark(data, alpha=None)
        self.assertEqual(res2['status'], 'success')
        self.assertEqual(res2['comparison']['alpha'], 0.05)

        # Invalid alpha string
        res3 = analyze_interleaved_benchmark(data, alpha='invalid')
        self.assertEqual(res3['comparison']['alpha'], 0.05)

    def test_analyze_interleaved_benchmark_extreme_boundaries(self):
        # Extreme boundaries

        # Empty dataset
        res1 = analyze_interleaved_benchmark([])
        self.assertEqual(res1['status'], 'error')

        # Single label dataset
        data = [
            {'label': 'A', 'value': 10},
            {'label': 'A', 'value': 20}
        ]
        res2 = analyze_interleaved_benchmark(data)
        self.assertEqual(res2['status'], 'success')
        self.assertEqual(res2['metrics']['A']['median'], 15.0)
        self.assertIsNone(res2['comparison'])
        self.assertFalse(res2['significant_difference'])

        # Large inputs
        data = [{'label': 'A', 'value': i} for i in range(1000)] + \
               [{'label': 'B', 'value': i + 500} for i in range(1000)]
        res3 = analyze_interleaved_benchmark(data)
        self.assertEqual(res3['status'], 'success')
        self.assertTrue(res3['significant_difference'])
        self.assertEqual(res3['metrics']['A']['count'], 1000)
        self.assertEqual(res3['metrics']['B']['count'], 1000)

if __name__ == '__main__':
    unittest.main()

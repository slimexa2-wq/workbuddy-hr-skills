import unittest
import time
import math
from ultra_modules.ab_interleaved_benchmark_self_healing_guard import ABInterleavedBenchmarkGuard

class TestABInterleavedBenchmarkGuard(unittest.TestCase):
    def test_normal_abba_ingestion(self):
        """Test normal ingestion of data for both groups and basic statistics."""
        guard = ABInterleavedBenchmarkGuard()

        # Interleaved ABBA data
        guard.add_data('A', 10.0)
        guard.add_data('B', 12.0)
        guard.add_data('B', 14.0)
        guard.add_data('A', 11.0)

        analysis = guard.analyze()
        self.assertEqual(analysis['group_a']['count'], 2)
        self.assertEqual(analysis['group_b']['count'], 2)
        self.assertEqual(analysis['group_a']['median'], 10.5)
        self.assertEqual(analysis['group_b']['median'], 13.0)

    def test_dirty_data_self_healing(self):
        """Test self-healing for invalid groups and NaN/Inf/String values."""
        guard = ABInterleavedBenchmarkGuard()

        guard.add_data('X', 5.0)  # Unknown group X -> falls back to 'A'
        guard.add_data('B', float('nan'))  # NaN -> 0.0
        guard.add_data('A', float('inf'))  # Inf -> 0.0
        guard.add_data('B', 'invalid')  # String -> 0.0
        guard.add_data(None, None)  # None -> A, 0.0

        analysis = guard.analyze()
        self.assertEqual(analysis['group_a']['count'], 3)
        self.assertEqual(analysis['group_b']['count'], 2)
        self.assertEqual(analysis['group_b']['median'], 0.0)

    def test_missing_args_defaults(self):
        """Test behavior with missing arguments using defaults."""
        guard = ABInterleavedBenchmarkGuard()
        guard.add_data()  # Default: 'A', 0.0
        guard.add_data(group='B')  # 'B', 0.0

        analysis = guard.analyze()
        self.assertEqual(analysis['group_a']['count'], 1)
        self.assertEqual(analysis['group_b']['count'], 1)
        self.assertEqual(analysis['group_a']['median'], 0.0)
        self.assertEqual(analysis['group_b']['median'], 0.0)

    def test_extreme_boundary_cases(self):
        """Test extreme boundary cases like empty initialization, all same elements."""
        guard = ABInterleavedBenchmarkGuard()

        # Empty
        analysis = guard.analyze()
        self.assertEqual(analysis['group_a']['count'], 0)
        self.assertEqual(analysis['group_b']['count'], 0)
        self.assertEqual(analysis['u_statistic'], 0.0)
        self.assertEqual(analysis['p_value'], 1.0)

        # All same elements
        for _ in range(5):
            guard.add_data('A', 1.0)
            guard.add_data('B', 1.0)

        analysis = guard.analyze()
        self.assertEqual(analysis['group_a']['iqr'], 0.0)
        self.assertEqual(analysis['group_b']['iqr'], 0.0)

    def test_snapshot_undo(self):
        """Test snapshot undo functionality with a time limit."""
        guard = ABInterleavedBenchmarkGuard(undo_window=0.5)

        guard.add_data('A', 10.0)
        self.assertEqual(guard.analyze()['group_a']['count'], 1)

        # Undo successfully
        success = guard.undo()
        self.assertTrue(success)
        self.assertEqual(guard.analyze()['group_a']['count'], 0)

        guard.add_data('B', 20.0)

        # Wait for undo window to expire
        time.sleep(0.6)
        success = guard.undo()
        self.assertFalse(success)
        self.assertEqual(guard.analyze()['group_b']['count'], 1)

if __name__ == '__main__':
    unittest.main()

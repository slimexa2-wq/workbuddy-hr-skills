import unittest
import time
from datetime import datetime, timedelta
from ultra_modules.monthly_254_baseline_auditor_self_healing_guard import BaselineAuditorGuard

class TestBaselineAuditorGuard(unittest.TestCase):

    def setUp(self):
        self.guard = BaselineAuditorGuard(baseline=10, undo_window_seconds=1)
        self.ref_date = datetime(2023, 10, 10)

    # Test 1: Normal processing and achievement rate calculation
    def test_normal_processing(self):
        records = [
            {'name': 'Alice', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'}, # 9 days
            {'name': 'Bob', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-05'},   # 5 days
            {'name': 'Charlie', 'active': False, 'self_recruited': True, 'hire_date': '2023-09-01'}, # inactive
            {'name': 'David', 'active': True, 'self_recruited': False, 'hire_date': '2023-10-01'}, # not self recruited
        ]
        result = self.guard.calculate(records, reference_date=self.ref_date)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_active_self_recruits'], 2)
        self.assertEqual(result['baseline'], 10)
        self.assertEqual(result['achievement_rate'], 0.2)
        self.assertEqual(result['full_7_days_count'], 1)

    # Test 2: Dirty data self-healing (bad types, missing fields, broken date strings)
    def test_dirty_data_healing(self):
        records = [
            {'name': 123, 'active': 'yes', 'self_recruited': 1, 'hire_date': '2023/10/01'}, # 9 days, valid
            {'active': '离职', 'hire_date': '2023.10.01'}, # inactive, no name -> Unknown
            {'name': 'Eve', 'self_recruited': 'false', 'hire_date': '20231001'}, # not self recruited
            {'name': 'Frank', 'active': '0', 'hire_date': 'bad-date'}, # inactive, bad date
            {'name': 'Grace'}, # missing active, self_recruited, hire_date. default active=True, sr=True, hire_date=None
            None,
            "not a dict"
        ]
        result = self.guard.calculate(records, reference_date=self.ref_date)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_active_self_recruits'], 2) # 123(Alice), Grace
        self.assertEqual(result['achievement_rate'], 0.2)
        self.assertEqual(result['full_7_days_count'], 1) # Only 123(Alice) has valid date >= 7 days

    # Test 3: Missing parameters fallback (no arguments passed, null values)
    def test_missing_parameters_fallback(self):
        result = self.guard.calculate()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_active_self_recruits'], 0)
        self.assertEqual(result['achievement_rate'], 0.0)
        self.assertEqual(result['full_7_days_count'], 0)

        result2 = self.guard.calculate(records=None, reference_date='invalid_date_format')
        self.assertEqual(result2['status'], 'success')
        self.assertEqual(result2['total_active_self_recruits'], 0)

    # Test 4: Snapshot Undo success (within 5 seconds) and failure (after 5 seconds)
    def test_snapshot_undo(self):
        self.guard.undo_window_seconds = 1
        # Action 1
        res1 = self.guard.calculate([
            {'name': 'A', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'}
        ], reference_date=self.ref_date)

        self.assertEqual(res1['total_active_self_recruits'], 1)

        # Action 2
        res2 = self.guard.calculate([
            {'name': 'B', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'},
            {'name': 'C', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'}
        ], reference_date=self.ref_date)

        self.assertEqual(res2['total_active_self_recruits'], 2)

        # Undo within window
        undone = self.guard.undo()
        self.assertEqual(undone['total_active_self_recruits'], 1)

        # Action 3
        res3 = self.guard.calculate([
            {'name': 'D', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'}
        ], reference_date=self.ref_date)
        self.assertEqual(res3['total_active_self_recruits'], 1)

        # Wait for undo window to expire
        time.sleep(1.1)
        undone_fail = self.guard.undo()
        self.assertEqual(undone_fail['total_active_self_recruits'], 1) # Still 1, undo failed

    # Test 5: Extreme edge cases (empty list, very large lists, future hire dates)
    def test_extreme_edge_cases(self):
        # Empty records
        res1 = self.guard.calculate([], reference_date=self.ref_date)
        self.assertEqual(res1['total_active_self_recruits'], 0)

        # Future hire dates
        res2 = self.guard.calculate([
            {'name': 'Future', 'active': True, 'self_recruited': True, 'hire_date': '2023-11-01'}
        ], reference_date=self.ref_date)
        self.assertEqual(res2['total_active_self_recruits'], 1)
        self.assertEqual(res2['full_7_days_count'], 0) # Days employed is negative

        # Zero baseline handling
        guard_zero = BaselineAuditorGuard(baseline=0)
        res_zero = guard_zero.calculate([
             {'name': 'A', 'active': True, 'self_recruited': True, 'hire_date': '2023-10-01'}
        ], reference_date=self.ref_date)
        self.assertEqual(res_zero['achievement_rate'], 0.0)

if __name__ == '__main__':
    unittest.main()

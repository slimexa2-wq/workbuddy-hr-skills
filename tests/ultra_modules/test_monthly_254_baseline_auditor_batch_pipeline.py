import unittest
import datetime
import time
from ultra_modules.monthly_254_baseline_auditor_batch_pipeline import MonthlyBaselineAuditorPipeline, run_audit_pipeline

class TestMonthlyBaselineAuditorPipeline(unittest.TestCase):

    def setUp(self):
        self.pipeline = MonthlyBaselineAuditorPipeline(baseline=254)
        self.audit_date = datetime.date(2023, 10, 15)

    def test_normal_processing(self):
        """Test case 1: Normal processing of valid and invalid records."""
        records = [
            {'id': '1', 'hire_date': '2023-10-01', 'status': 'active'}, # 14 days, valid
            {'id': '2', 'hire_date': '2023-10-10', 'status': 'active'}, # 5 days, invalid
            {'id': '3', 'hire_date': '2023-10-01', 'status': 'resigned'}, # 14 days, invalid (resigned)
        ]

        result = run_audit_pipeline(records, audit_date=self.audit_date, baseline=1)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['valid_count'], 1)
        self.assertTrue(result['baseline_met'])

        # Check individual results
        results_by_id = {r['id']: r for r in result['results']}
        self.assertTrue(results_by_id['1']['is_valid'])
        self.assertFalse(results_by_id['2']['is_valid'])
        self.assertFalse(results_by_id['3']['is_valid'])

    def test_dirty_data_self_healing(self):
        """Test case 2: Dirty data self-healing (invalid date format, invalid status)."""
        records = [
            {'id': '1', 'hire_date': '2023/10/01', 'status': '  AcTiVe  '}, # Alternative date format, messy status string
            {'id': '2', 'hire_date': 'not-a-date', 'status': 'unknown-status'}, # Unparseable date, unknown status
        ]

        # Test with a fixed audit date for predictability
        result = run_audit_pipeline(records, audit_date=self.audit_date)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total'], 2)

        results_by_id = {r['id']: r for r in result['results']}

        # Record 1: should heal to 'active' and correct date (14 days -> valid)
        self.assertEqual(results_by_id['1']['status'], 'active')
        self.assertTrue(results_by_id['1']['is_valid'])

        # Record 2: date heals to today, status heals to 'active'.
        # Since audit_date is fixed to 2023-10-15, and hire_date heals to today (e.g. 2024-xx-xx or whatever current date is),
        # days_employed will likely be negative, so it will be invalid.
        # But we verify self-healing happened.
        self.assertEqual(results_by_id['2']['status'], 'active')

    def test_default_parameters_fallback(self):
        """Test case 3: Missing parameters fallback (no ID, no hire_date, None records)."""
        records = [
            {'status': 'active'}, # Missing id and hire_date
            None # Completely None record
        ]

        result = run_audit_pipeline(records) # No audit_date provided

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total'], 2)

        # Both should have auto-generated IDs and be processed without crashing
        self.assertEqual(len(result['results']), 2)
        for r in result['results']:
            self.assertIsNotNone(r['id'])
            self.assertEqual(r['status'], 'active')

    def test_large_scale_boundary(self):
        """Test case 4: Large scale boundary test (1000 records)."""
        records = []
        for i in range(1000):
            records.append({
                'id': f'emp_{i}',
                'hire_date': '2023-10-01', # 14 days relative to audit_date
                'status': 'active'
            })

        result = run_audit_pipeline(records, audit_date=self.audit_date, baseline=254)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total'], 1000)
        self.assertEqual(result['processed'], 1000)
        self.assertEqual(result['valid_count'], 1000)
        self.assertTrue(result['baseline_met'])

    def test_progress_snapshot(self):
        """Test case 5: Progress snapshot functionality during batch processing."""
        # Create a large batch to ensure processing takes a tiny bit of time
        records = [{'id': f'emp_{i}', 'hire_date': '2023-10-01', 'status': 'active'} for i in range(500)]

        batch_id = self.pipeline.submit_batch(records, audit_date=self.audit_date)

        # Immediately check snapshot
        snapshot = self.pipeline.get_snapshot(batch_id)

        self.assertIn(snapshot['status'], ['processing', 'completed'])
        self.assertEqual(snapshot['total'], 500)
        self.assertTrue('processed' in snapshot)

        # Wait for completion
        while True:
            snapshot = self.pipeline.get_snapshot(batch_id)
            if snapshot['status'] == 'completed':
                break
            time.sleep(0.01)

        self.assertEqual(snapshot['status'], 'completed')
        self.assertEqual(snapshot['processed'], 500)
        self.assertEqual(snapshot['valid_count'], 500)

if __name__ == '__main__':
    unittest.main()

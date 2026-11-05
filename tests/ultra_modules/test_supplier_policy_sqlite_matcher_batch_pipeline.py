import unittest
import time
from ultra_modules.supplier_policy_sqlite_matcher_batch_pipeline import SupplierPolicyMatcher

class TestSupplierPolicyMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = SupplierPolicyMatcher()
        self.policies = [
            {
                'job_type': 'developer',
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'min_count': 0,
                'max_count': 10,
                'price': 100.0
            },
            {
                'job_type': 'developer',
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'min_count': 11,
                'max_count': 100,
                'price': 80.0
            },
            {
                'job_type': 'designer',
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'min_count': 0,
                'max_count': 50,
                'price': 150.0
            }
        ]
        self.matcher.insert_policies(self.policies)

    def tearDown(self):
        self.matcher.shutdown()

    def _wait_for_batch(self, batch_id, timeout=5.0):
        start = time.time()
        while time.time() - start < timeout:
            snapshot = self.matcher.get_snapshot(batch_id)
            if snapshot['status'] == 'completed':
                return snapshot
            time.sleep(0.01)
        raise TimeoutError("Batch processing timed out")

    def test_normal_processing(self):
        """Test normal processing with correct data."""
        records = [
            {'job_type': 'developer', 'date': '2023-05-15', 'count': 5},
            {'job_type': 'designer', 'date': '2023-06-20', 'count': 20}
        ]
        batch_id = self.matcher.submit_batch(records)
        snapshot = self._wait_for_batch(batch_id)

        self.assertEqual(snapshot['total'], 2)
        self.assertEqual(snapshot['processed'], 2)

        results = snapshot['results']
        prices = {r['job_type']: r['matched_price'] for r in results}
        self.assertEqual(prices['developer'], 100.0)
        self.assertEqual(prices['designer'], 150.0)

    def test_dirty_data_self_healing(self):
        """Test dirty data self-healing (missing fields, wrong types)."""
        records = [
            {'job_type': None, 'date': '2023/05/15', 'count': 'not_an_int'}, # count heals to 0, date replaces / with -
            {'job_type': '  developer  ', 'date': None, 'count': None} # heals to stripped, default date, count 0
        ]
        batch_id = self.matcher.submit_batch(records)
        snapshot = self._wait_for_batch(batch_id)

        results = snapshot['results']

        # first record heals to job_type='unknown', date='2023-05-15', count=0 -> no match so 0.0
        self.assertEqual(results[0]['job_type'], 'unknown')
        self.assertEqual(results[0]['date'], '2023-05-15')
        self.assertEqual(results[0]['count'], 0)
        self.assertEqual(results[0]['matched_price'], 0.0)

        # second record heals to job_type='developer', date='1970-01-01', count=0 -> no match (date outside range)
        self.assertEqual(results[1]['job_type'], 'developer')
        self.assertEqual(results[1]['date'], '1970-01-01')
        self.assertEqual(results[1]['count'], 0)
        self.assertEqual(results[1]['matched_price'], 0.0)

    def test_step_price_limit_matching(self):
        """Test step price matching when limits are hit."""
        records = [
            {'job_type': 'developer', 'date': '2023-05-15', 'count': 10}, # matches 1st step
            {'job_type': 'developer', 'date': '2023-05-15', 'count': 11}, # matches 2nd step
            {'job_type': 'developer', 'date': '2023-05-15', 'count': 101} # exceeds max_count, no match
        ]
        batch_id = self.matcher.submit_batch(records)
        snapshot = self._wait_for_batch(batch_id)

        results = snapshot['results']
        # Map original count to price to verify
        prices = {r['count']: r['matched_price'] for r in results}
        self.assertEqual(prices[10], 100.0)
        self.assertEqual(prices[11], 80.0)
        self.assertEqual(prices[101], 0.0)

    def test_extreme_boundary_1000_items(self):
        """Test extreme boundary (1000 items) for performance and correctness."""
        records = [{'job_type': 'developer', 'date': '2023-05-15', 'count': 5} for _ in range(1000)]

        start_time = time.time()
        batch_id = self.matcher.submit_batch(records)
        snapshot = self._wait_for_batch(batch_id, timeout=10.0)
        end_time = time.time()

        self.assertEqual(snapshot['total'], 1000)
        self.assertEqual(snapshot['processed'], 1000)

        # Verify correctness for the first and last
        self.assertEqual(snapshot['results'][0]['matched_price'], 100.0)
        self.assertEqual(snapshot['results'][-1]['matched_price'], 100.0)

        # Ensure it's fast (millisecond level processing, arbitrary 2s threshold for CI environments)
        self.assertLess(end_time - start_time, 2.0)

    def test_non_blocking_batch_snapshot(self):
        """Test non-blocking batch tracking (snapshots)."""
        records = [{'job_type': 'developer', 'date': '2023-05-15', 'count': 5} for _ in range(500)]
        batch_id = self.matcher.submit_batch(records)

        # Get a snapshot immediately, shouldn't block
        snapshot1 = self.matcher.get_snapshot(batch_id)
        self.assertIsNotNone(snapshot1)
        self.assertEqual(snapshot1['batch_id'], batch_id)
        self.assertEqual(snapshot1['total'], 500)
        self.assertIn(snapshot1['status'], ['running', 'completed']) # Could be fast enough to complete

        # Wait for completion
        snapshot_final = self._wait_for_batch(batch_id)
        self.assertEqual(snapshot_final['status'], 'completed')
        self.assertEqual(snapshot_final['processed'], 500)
        self.assertEqual(len(snapshot_final['results']), 500)

if __name__ == '__main__':
    unittest.main()

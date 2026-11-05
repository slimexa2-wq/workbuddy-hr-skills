import unittest
from unittest.mock import patch
import time

from ultra_modules.mihomo_proxy_health_prober_batch_pipeline import (
    ProxyProber,
    BatchPipeline,
    run_batch_pipeline,
    ProbeResult
)

class TestProxyProberPipeline(unittest.TestCase):

    @patch('ultra_modules.mihomo_proxy_health_prober_batch_pipeline.ProxyProber.probe_all')
    def test_normal_batch_processing(self, mock_probe_all):
        """Test normal batch stream processing of records"""
        mock_probe_all.return_value = [
            ProbeResult("direct", None, 50.0, True),
            ProbeResult("proxy_7890", 7890, 20.0, True),
            ProbeResult("proxy_26801", 26801, 100.0, True)
        ]
        records = [{"id": f"record_{i}", "data": "test"} for i in range(15)]
        results = run_batch_pipeline(records=records)

        self.assertEqual(len(results), 15)
        for res in results:
            self.assertEqual(res["best_connection"], 7890)
            self.assertEqual(res["best_latency_ms"], 20.0)
            self.assertEqual(len(res["probes"]), 3)
            self.assertTrue("id" in res)
            self.assertTrue("original_record" in res)

    @patch('ultra_modules.mihomo_proxy_health_prober_batch_pipeline.ProxyProber.probe_all')
    def test_dirty_data_self_healing(self, mock_probe_all):
        """Test dirty data self-healing, defaults applied without breaking"""
        mock_probe_all.return_value = [
            ProbeResult("direct", None, 50.0, True)
        ]

        # None, non-dict, dict without id
        records = [
            None,
            "just_a_string",
            12345,
            {"some_key": "val"}
        ]

        results = run_batch_pipeline(records=records)
        self.assertEqual(len(results), 3) # None is skipped

        ids = [res["id"] for res in results]
        self.assertIn("just_a_string", ids)
        self.assertIn("12345", ids)

        # Check that the dict without id got an auto-generated id
        auto_id_res = next((res for res in results if res["id"].startswith("auto_")), None)
        self.assertIsNotNone(auto_id_res)

    @patch('ultra_modules.mihomo_proxy_health_prober_batch_pipeline.ProxyProber.probe_all')
    def test_missing_parameter_default_fallback(self, mock_probe_all):
        """Test missing parameter default fallback - calling run_batch_pipeline with None"""
        mock_probe_all.return_value = [
            ProbeResult("direct", None, 50.0, True)
        ]

        results = run_batch_pipeline()
        self.assertEqual(len(results), 10)
        for i in range(10):
            self.assertEqual(results[i]["id"], f"default_{i}")

    @patch('ultra_modules.mihomo_proxy_health_prober_batch_pipeline.ProxyProber.probe_all')
    def test_extreme_boundary_conditions(self, mock_probe_all):
        """Test extreme boundary conditions with all failing/1000 records"""
        mock_probe_all.return_value = [
            ProbeResult("direct", None, 50.0, False, "timeout"),
            ProbeResult("proxy_7890", 7890, 20.0, False, "connection refused"),
            ProbeResult("proxy_26801", 26801, 100.0, False, "connection reset")
        ]

        records = [{"id": f"rec_{i}"} for i in range(1000)]
        results = run_batch_pipeline(records=records, max_workers=50) # Use more workers for speed in test

        self.assertEqual(len(results), 1000)
        for res in results:
            self.assertIsNone(res["best_connection"])
            self.assertEqual(res["best_latency_ms"], -1)
            for probe in res["probes"]:
                self.assertFalse(probe["success"])
                self.assertTrue(len(probe["error"]) > 0)

    @patch('ultra_modules.mihomo_proxy_health_prober_batch_pipeline.ProxyProber.probe_all')
    def test_progress_snapshot_and_non_blocking(self, mock_probe_all):
        """Test progress snapshot and zero-blocking result aggregation"""

        def slow_probe():
            time.sleep(0.1)
            return [ProbeResult("direct", None, 50.0, True)]

        mock_probe_all.side_effect = slow_probe

        pipeline = BatchPipeline(max_workers=2)
        records = [{"id": f"slow_{i}"} for i in range(10)]
        pipeline.submit_batch(records)

        # Take a snapshot immediately, should have 0 completed (non-blocking)
        snap1 = pipeline.get_progress_snapshot()
        self.assertEqual(snap1["total"], 10)
        # Could be 0 or slightly more if fast, but shouldn't be all 10
        self.assertTrue(snap1["completed"] < 10)

        # Wait completion
        results = pipeline.wait_completion()
        self.assertEqual(len(results), 10)

        snap2 = pipeline.get_progress_snapshot()
        self.assertEqual(snap2["total"], 10)
        self.assertEqual(snap2["completed"], 10)
        self.assertEqual(snap2["pending"], 0)
        self.assertEqual(len(snap2["results"]), 10)

if __name__ == '__main__':
    unittest.main()

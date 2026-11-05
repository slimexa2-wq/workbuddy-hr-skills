import unittest
from unittest.mock import patch, MagicMock
from ultra_modules.mihomo_proxy_health_prober_audit_trace import MihomoProxyHealthProber

class TestMihomoProxyHealthProber(unittest.TestCase):

    def setUp(self):
        # We patch urllib.request.build_opener to mock network requests
        self.patcher = patch('urllib.request.build_opener')
        self.mock_build_opener = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()


    def test_normal_behavior_and_audit_trace(self):
        # Test basic initialization with normal parameters
        prober = MihomoProxyHealthProber(ports=[7890], timeout=3.0, target_url="http://example.com")

        mock_opener = MagicMock()
        self.mock_build_opener.return_value = mock_opener

        mock_response = MagicMock()
        mock_response.status = 204

        # Make the context manager return our mock_response
        mock_opener.open.return_value.__enter__.return_value = mock_response

        res = prober.get_optimal_route()

        self.assertIn("route", res)
        self.assertIn("latency_ms", res)
        self.assertEqual(res["status"], "connected")

        # Check audit trace
        trace = prober.get_audit_trace()
        self.assertTrue(len(trace) > 0)

        actions = [t["action"] for t in trace]
        self.assertIn("init_complete", actions)
        self.assertIn("probe_start", actions)
        self.assertIn("probe_success", actions)
        self.assertIn("differential_compare", actions)

    def test_dirty_data_auto_healing(self):
        # Test passing completely broken ports list
        prober = MihomoProxyHealthProber(ports=["7890", "invalid", 999999, -1, 26801, 7890, None], timeout="not a float", target_url=12345)

        trace = prober.get_audit_trace()

        actions = [t["action"] for t in trace]
        self.assertIn("init_dirty_data", actions)
        self.assertIn("init_deduplicate", actions)
        self.assertIn("init_repair", actions) # from timeout/target_url repairs

        # Recovered ports: 7890 (str->int), 26801 (deduplicated the second 7890, ignored invalid/999999/-1/None)
        # Verify internal ports list (should be [7890, 26801])
        init_complete_log = next(t for t in trace if t["action"] == "init_complete")
        self.assertEqual(init_complete_log["details"]["ports"], [7890, 26801])
        self.assertEqual(init_complete_log["details"]["timeout"], 2.0)
        self.assertEqual(init_complete_log["details"]["target_url"], "http://www.google.com/generate_204")

    def test_missing_parameter_fallback(self):
        # Completely empty config
        prober = MihomoProxyHealthProber()

        trace = prober.get_audit_trace()
        init_complete_log = next(t for t in trace if t["action"] == "init_complete")

        self.assertEqual(init_complete_log["details"]["ports"], [7890, 26801])
        self.assertEqual(init_complete_log["details"]["timeout"], 2.0)
        self.assertEqual(init_complete_log["details"]["target_url"], "http://www.google.com/generate_204")

    def test_extreme_boundary_all_failed(self):
        prober = MihomoProxyHealthProber()

        # Mock opener to always raise an exception (simulate no network/all failed)
        mock_opener = MagicMock()
        self.mock_build_opener.return_value = mock_opener
        mock_opener.open.side_effect = Exception("Connection Refused")

        res = prober.get_optimal_route()

        # Verify extremely clean frontend output
        self.assertEqual(res["route"], "direct") # Should fallback to direct
        self.assertEqual(res["latency_ms"], -1)
        self.assertEqual(res["status"], "disconnected")

        # Verify decision fallback in trace
        trace = prober.get_audit_trace()
        actions = [t["action"] for t in trace]
        self.assertIn("probe_exception", actions)
        self.assertIn("decision_fallback", actions)

    def test_latency_comparison(self):
        # We mock _probe directly to simulate different latencies for different routes
        prober = MihomoProxyHealthProber(ports=[7890, 26801])

        def mock_probe(port):
            if port == "direct":
                return 150.0
            elif port == 7890:
                return float('inf') # timeout
            elif port == 26801:
                return 45.5 # fastest
            return float('inf')

        with patch.object(prober, '_probe', side_effect=mock_probe):
            res = prober.get_optimal_route()

        self.assertEqual(res["route"], "26801")
        self.assertEqual(res["latency_ms"], 45.5)
        self.assertEqual(res["status"], "connected")

        trace = prober.get_audit_trace()
        diff_compare = next(t for t in trace if t["action"] == "differential_compare")
        self.assertEqual(diff_compare["details"]["winner"], "26801")
        self.assertEqual(diff_compare["details"]["candidates"]["7890"], "timeout")

if __name__ == '__main__':
    unittest.main()

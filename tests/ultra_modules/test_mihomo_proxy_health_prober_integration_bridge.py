import unittest
import socket
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from ultra_modules.mihomo_proxy_health_prober_integration_bridge import (
    MihomoProxyHealthProber,
    SchemaConverter,
    run_probe_and_convert
)

class TestMihomoProxyHealthProberIntegrationBridge(unittest.TestCase):

    def test_normal_usage_schema_conversion(self):
        """
        Test 1: Normal usage where valid proxy data is converted.
        """
        old_data = {
            "delay": 42.5,
            "proxy_port": 26801,
            "is_alive": True,
            "proxy_type": "socks5"
        }

        converted = SchemaConverter.convert(old_data)

        self.assertAlmostEqual(converted["latency_ms"], 42.5)
        self.assertEqual(converted["port"], 26801)
        self.assertTrue(converted["status_ok"])
        self.assertEqual(converted["protocol"], "socks5")

    def test_dirty_data_self_healing(self):
        """
        Test 2: Dirty data self-healing where invalid data types are safely handled.
        """
        dirty_data = {
            "delay": "invalid_string_not_float",
            "proxy_port": "not_an_int",
            "is_alive": "yes",  # String instead of bool
            "extra_field": "should_be_kept"
        }

        converted = SchemaConverter.convert(dirty_data)

        # Invalid delay becomes -1.0
        self.assertEqual(converted["latency_ms"], -1.0)
        # Invalid port defaults to 7890
        self.assertEqual(converted["port"], 7890)
        # "yes" string parses as True
        self.assertTrue(converted["status_ok"])
        # Extra field is kept
        self.assertEqual(converted["extra_field"], "should_be_kept")

    def test_missing_parameter_fallbacks(self):
        """
        Test 3: Missing parameter fallbacks where an empty dict triggers sensible defaults.
        """
        empty_data = {}

        converted = SchemaConverter.convert(empty_data)

        # Missing port defaults to 7890
        self.assertEqual(converted["port"], 7890)
        # Missing status defaults to False
        self.assertFalse(converted["status_ok"])

    @patch('socket.create_connection')
    def test_boundary_case_network_timeout(self, mock_create_connection):
        """
        Test 4: Boundary case where probing encounters a network timeout.
        """
        # Make the connection throw a timeout
        mock_create_connection.side_effect = socket.timeout

        prober = MihomoProxyHealthProber(ports=[7890])
        latency = prober.measure_latency("example.com", 80)

        # Connection failed, latency should be -1.0
        self.assertEqual(latency, -1.0)

        health_status = prober.get_health_status()
        self.assertEqual(health_status["direct_latency_ms"], -1.0)
        self.assertEqual(health_status["best_latency"], -1.0)
        self.assertIsNone(health_status["best_proxy_port"])

    @patch('socket.create_connection')
    def test_run_probe_and_convert_integration(self, mock_create_connection):
        """
        Test 5: Integration test running the full probe and convert pipeline.
        Verify old schema fields map perfectly without errors and the probe logic handles it.
        """
        # Mock successful connection
        mock_create_connection.return_value.__enter__ = MagicMock()
        mock_create_connection.return_value.__exit__ = MagicMock()

        input_data = {
            "proxy_port": "26801",
            "is_alive": "1"
        }

        result = run_probe_and_convert(input_data)

        # Verify conversion applied
        self.assertEqual(result["input_config"]["port"], 26801)
        self.assertTrue(result["input_config"]["status_ok"])

        # Verify health probe has a best port due to mocked successful connection
        self.assertIsNotNone(result["health_probe"]["best_proxy_port"])
        self.assertEqual(result["health_probe"]["best_proxy_port"], 26801)

        # Recommend action should be use_proxy
        self.assertEqual(result["recommended_action"], "use_proxy")

if __name__ == '__main__':
    unittest.main()

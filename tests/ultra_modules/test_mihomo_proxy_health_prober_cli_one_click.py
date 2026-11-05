import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import tempfile
import json
import time

# Ensure import works by appending the root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ultra_modules import mihomo_proxy_health_prober_cli_one_click

class TestMihomoProxyHealthProberCliOneClick(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        # Clean up temp dir
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    @patch('socket.socket')
    def test_probe_endpoint_success(self, mock_socket):
        """Test normal successful probing."""
        # Mock time to control latency calculation
        with patch('time.time', side_effect=[100.0, 100.05]):
            latency = mihomo_proxy_health_prober_cli_one_click.probe_endpoint("127.0.0.1", 7890)
            self.assertEqual(latency, 50.0)
            mock_socket.return_value.__enter__.return_value.connect.assert_called_with(("127.0.0.1", 7890))

    @patch('socket.socket')
    def test_probe_endpoint_timeout_failure(self, mock_socket):
        """Test probing boundary case with timeout/failure."""
        import socket
        mock_socket.return_value.__enter__.return_value.connect.side_effect = socket.timeout("Timed out")

        latency = mihomo_proxy_health_prober_cli_one_click.probe_endpoint("127.0.0.1", 7890)
        self.assertEqual(latency, -1.0)

    @patch('socket.socket')
    def test_probe_endpoint_missing_params(self, mock_socket):
        """Test fallback when missing parameters."""
        with patch('time.time', side_effect=[100.0, 100.01]):
            latency = mihomo_proxy_health_prober_cli_one_click.probe_endpoint(None, None, None)
            self.assertEqual(latency, 10.0)
            mock_socket.return_value.__enter__.return_value.connect.assert_called_with(("127.0.0.1", 7890))

    @patch('ultra_modules.mihomo_proxy_health_prober_cli_one_click.probe_endpoint', return_value=20.0)
    def test_probe_all_dirty_data(self, mock_probe):
        """Test dirty data self-healing in targets."""
        dirty_targets = [
            ("Good", "127.0.0.1", 7890),
            None, # Invalid
            ("TooShort", "8.8.8.8"), # Invalid
            ("", "10.0.0.1", 8080) # Missing name
        ]

        results = mihomo_proxy_health_prober_cli_one_click.probe_all(dirty_targets)
        self.assertEqual(len(results), 2)

        self.assertEqual(results[0]["name"], "Good")
        self.assertEqual(results[1]["name"], "10.0.0.1:8080") # Auto-generated name

    def test_export_json_and_excel(self):
        """Test JSON and Excel export functionality without side-effects."""
        results = [
            {"name": "Proxy\x00", "host": "127.0.0.1\x00", "port": 7890, "latency_ms": 10.0, "status": "Healthy\x00", "timestamp": 1234567890.0}
        ]

        json_file = "test.json"
        excel_file = "test.xlsx"

        # Test JSON
        res_json = mihomo_proxy_health_prober_cli_one_click.export_json(results, json_file)
        self.assertEqual(res_json, json_file)
        self.assertTrue(os.path.exists(json_file))

        with open(json_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data[0]["name"], "Proxy\x00")

        # Test Excel
        res_excel = mihomo_proxy_health_prober_cli_one_click.export_excel(results, excel_file)
        if mihomo_proxy_health_prober_cli_one_click.openpyxl:
            self.assertEqual(res_excel, excel_file)
            self.assertTrue(os.path.exists(excel_file))

            import openpyxl
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            self.assertEqual(ws["A2"].value, "Proxy") # Null char stripped
            self.assertEqual(ws["B2"].value, "127.0.0.1")
            self.assertEqual(ws["C2"].value, 7890)
            self.assertEqual(ws["D2"].value, 10.0)
            self.assertEqual(ws["E2"].value, "Healthy")
            self.assertEqual(ws["F2"].value, 1234567890.0)

    @patch('ultra_modules.mihomo_proxy_health_prober_cli_one_click.probe_all')
    def test_run_cli(self, mock_probe_all):
        """Test zero-parameter CLI run."""
        mock_probe_all.return_value = [
            {"name": "Default", "host": "127.0.0.1", "port": 7890, "latency_ms": 15.0, "status": "Healthy", "timestamp": 1234.0}
        ]

        # Run with default args (empty sys.argv)
        with patch.object(sys, 'argv', ['prog']):
            results = mihomo_proxy_health_prober_cli_one_click.run_cli()
            self.assertEqual(len(results), 1)
            self.assertTrue(os.path.exists("probe_results.json"))
            if mihomo_proxy_health_prober_cli_one_click.openpyxl:
                self.assertTrue(os.path.exists("probe_results.xlsx"))

if __name__ == '__main__':
    unittest.main()

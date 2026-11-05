import unittest
import json
from unittest.mock import patch, MagicMock
from ultra_modules.mihomo_proxy_health_prober_plain_explainer import MihomoProxyHealthProberPlainExplainer

class TestMihomoProxyHealthProberPlainExplainer(unittest.TestCase):

    def test_missing_parameter_fallbacks(self):
        """Test zero-configuration: missing parameters default to sensible values."""
        prober = MihomoProxyHealthProberPlainExplainer()
        self.assertEqual(prober.target_url, "http://www.gstatic.com/generate_204")
        self.assertEqual(prober.proxy_ports, [7890, 26801])
        self.assertEqual(prober.timeout, 3.0)

    def test_dirty_data_self_healing(self):
        """Test dirty data healing: invalid types/values are silently healed."""
        prober = MihomoProxyHealthProberPlainExplainer(
            target_url=12345,
            proxy_ports="8080, invalid, 9090",
            timeout="-5.0"
        )
        self.assertEqual(prober.target_url, "http://www.gstatic.com/generate_204")
        self.assertEqual(prober.proxy_ports, [8080, 9090])
        self.assertEqual(prober.timeout, 3.0)

        prober_list = MihomoProxyHealthProberPlainExplainer(proxy_ports=[1080, "invalid", 1081])
        self.assertEqual(prober_list.proxy_ports, [1080, 1081])

        prober_int = MihomoProxyHealthProberPlainExplainer(proxy_ports=7890)
        self.assertEqual(prober_int.proxy_ports, [7890])

    @patch('urllib.request.build_opener')
    def test_direct_connection_best_scenario(self, mock_build_opener):
        """Test direct connection best scenario."""
        prober = MihomoProxyHealthProberPlainExplainer()

        def mock_measure_latency(port=None):
            if port is None:
                return 10.0 # Direct is very fast
            return 50.0 # Proxies are slower

        with patch.object(prober, '_measure_latency', side_effect=mock_measure_latency):
            reports = prober.probe()

        json_report = json.loads(reports['json'])
        self.assertEqual(json_report['best_mode'], 'direct')
        self.assertTrue("直连速度最快" in json_report['conclusion'])

        self.assertIn("直连速度最快", reports['markdown'])
        self.assertIn("直连速度最快", reports['html'])

    @patch('urllib.request.build_opener')
    def test_proxy_needed_scenario(self, mock_build_opener):
        """Test proxy needed scenario (proxy is faster than direct)."""
        prober = MihomoProxyHealthProberPlainExplainer(proxy_ports=[7890])

        def mock_measure_latency(port=None):
            if port is None:
                return -1.0 # Direct fails
            elif port == 7890:
                return 25.0 # Proxy is fast
            return -1.0

        with patch.object(prober, '_measure_latency', side_effect=mock_measure_latency):
            reports = prober.probe()

        json_report = json.loads(reports['json'])
        self.assertEqual(json_report['best_mode'], 'proxy_7890')
        self.assertTrue("推荐使用代理" in json_report['conclusion'])
        self.assertTrue("7890 端口代理的速度最快" in json_report['conclusion'])

    @patch('urllib.request.build_opener')
    def test_extreme_boundary_case_all_offline(self, mock_build_opener):
        """Test extreme boundary case: completely offline network."""
        prober = MihomoProxyHealthProberPlainExplainer()

        def mock_measure_latency(port=None):
            return -1.0 # All connections fail

        with patch.object(prober, '_measure_latency', side_effect=mock_measure_latency):
            reports = prober.probe()

        json_report = json.loads(reports['json'])
        self.assertEqual(json_report['best_mode'], 'none')
        self.assertTrue("网络好像彻底断了" in json_report['conclusion'])
        self.assertIn("超时/失败", reports['markdown'])
        self.assertIn("超时/失败", reports['html'])

if __name__ == '__main__':
    unittest.main()

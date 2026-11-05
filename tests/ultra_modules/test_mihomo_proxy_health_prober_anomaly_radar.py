import unittest
from unittest.mock import patch
from typing import Optional
from ultra_modules.mihomo_proxy_health_prober_anomaly_radar import (
    run_anomaly_radar,
    MihomoProxyHealthProberAnomalyRadar
)

class TestMihomoProxyHealthProberAnomalyRadar(unittest.TestCase):

    @patch('ultra_modules.mihomo_proxy_health_prober_anomaly_radar._measure_latency')
    def test_normal_execution(self, mock_measure):
        def mock_latency(url, proxy_url, timeout):
            if not proxy_url:
                return 200.0 # direct
            if "7890" in proxy_url:
                return 50.0
            if "26801" in proxy_url:
                return 60.0
            return 100.0

        mock_measure.side_effect = mock_latency

        result = run_anomaly_radar()

        self.assertEqual(result["overall_status"], "Yellow")
        self.assertEqual(len(result["anomalies"]), 1) # Top 1 highlighted anomaly (the 200ms direct)
        self.assertEqual(len(result["normal"]), 2)

        # Test auto-switch recommendation
        self.assertIn("建议自动切换至代理端口 7890", result["switch_suggestion"])
        self.assertEqual(result["best_connection"]["port"], 7890)

    @patch('ultra_modules.mihomo_proxy_health_prober_anomaly_radar._measure_latency')
    def test_dirty_data_self_healing(self, mock_measure):
        # 脏数据自愈测试
        mock_measure.return_value = 20.0

        # 传入各种脏数据
        result = run_anomaly_radar(
            target_url="  ", # 空字符串
            proxy_ports=["7890", None, 26801, "abc"], # 包含无法转换的内容
            timeout="invalid_timeout" # 无法转换为float
        )

        self.assertEqual(result["overall_status"], "Green")
        # Should fall back to 1 direct + 2 proxies (7890, 26801)
        self.assertEqual(len(result["normal"]) + len(result["anomalies"]), 3)
        ports = [r["port"] for r in result["normal"] + result["anomalies"] if r["type"] == "proxy"]
        self.assertIn(7890, ports)
        self.assertIn(26801, ports)

    @patch('ultra_modules.mihomo_proxy_health_prober_anomaly_radar._measure_latency')
    def test_missing_params_fallback(self, mock_measure):
        # 缺参自动兜底测试
        mock_measure.return_value = 15.0

        # 不传任何参数
        radar = MihomoProxyHealthProberAnomalyRadar()
        result = radar.check()

        self.assertEqual(result["overall_status"], "Green")
        ports = [r["port"] for r in result["normal"] + result["anomalies"] if r["type"] == "proxy"]
        self.assertEqual(sorted(ports), [7890, 26801])

    @patch('ultra_modules.mihomo_proxy_health_prober_anomaly_radar._measure_latency')
    def test_extreme_boundary_all_offline(self, mock_measure):
        # 极端边界：全部离线
        mock_measure.return_value = None

        result = run_anomaly_radar()

        self.assertEqual(result["overall_status"], "Red")
        self.assertIn("所有节点均离线", result["switch_suggestion"])

        # In all offline, only top 3% (which is 1) is anomaly, rest silenced
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(len(result["normal"]), 2)

        self.assertEqual(result["anomalies"][0]["status"], "Red")
        self.assertIn("静默放行", result["normal"][0]["reason"])

    @patch('ultra_modules.mihomo_proxy_health_prober_anomaly_radar._measure_latency')
    def test_top_anomaly_highlighting(self, mock_measure):
        # 测试异常高亮 (Top 3% 逻辑)，提供较多节点
        def mock_latency(url, proxy_url, timeout):
            if not proxy_url:
                return 40.0
            if "7890" in proxy_url:
                return 5000.0 # 异常1
            if "26801" in proxy_url:
                return 4500.0 # 异常2
            return 50.0

        mock_measure.side_effect = mock_latency

        # (1 direct + 6 proxies = 7 total). 3% of 7 is 0.21 -> max(1, 1) -> 1 anomaly highlighted.
        result = run_anomaly_radar(
            proxy_ports=[7890, 26801, 8080, 8081, 8082, 8083]
        )

        self.assertEqual(result["overall_status"], "Red")
        self.assertEqual(len(result["anomalies"]), 1)

        # 7890 is the worst
        self.assertEqual(result["anomalies"][0]["port"], 7890)

        # 26801 should be silenced
        silenced_26801 = [r for r in result["normal"] if r["port"] == 26801]
        self.assertEqual(len(silenced_26801), 1)
        self.assertIn("静默放行", silenced_26801[0]["reason"])

if __name__ == '__main__':
    unittest.main()

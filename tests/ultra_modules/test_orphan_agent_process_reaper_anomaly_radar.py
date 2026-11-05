import unittest
from unittest.mock import patch, MagicMock
from ultra_modules.orphan_agent_process_reaper_anomaly_radar import OrphanAgentProcessReaperAnomalyRadar, run_anomaly_radar

class TestOrphanAgentProcessReaperAnomalyRadar(unittest.TestCase):

    def setUp(self):
        self.radar = OrphanAgentProcessReaperAnomalyRadar()

    @patch("subprocess.run")
    def test_normal_no_orphans(self, mock_run):
        """测试正常情况：无孤儿进程，绿灯放行"""
        mock_result = MagicMock()
        mock_result.stdout = "PID PPID RSS COMMAND\n123 1 1024 /usr/bin/bash\n"
        mock_run.return_value = mock_result

        result = self.radar.scan_and_analyze()

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["anomalies"]), 0)
        self.assertEqual(result["normal_count"], 0)
        self.assertTrue("🟢 绿灯放行" in result["summary"])

    @patch("subprocess.run")
    def test_dirty_data_self_healing(self, mock_run):
        """测试脏数据自愈：静默过滤无效数据，不崩溃"""
        mock_result = MagicMock()
        # Contains missing columns, invalid int, empty lines
        mock_result.stdout = (
            "PID PPID RSS COMMAND\n"
            "123 1 1024 /usr/bin/agent\n"
            "124\n"
            "abc def 123 invalid\n"
            "\n"
            "125 1 2048 /usr/bin/playwright\n"
        )
        mock_run.return_value = mock_result

        result = self.radar.scan_and_analyze()
        # Should process PID 123 and 125, both are too small to be anomaly if N=2
        # Wait, if N=2, top 3% is 1 item. Let's see what logic does.
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["normal_count"] + len(result["anomalies"]), 2)

    @patch("subprocess.run")
    def test_anomaly_detection_zscore_iqr(self, mock_run):
        """测试异常检测：红黄灯标记Top 3%或Z-Score>3极高值"""
        # Create 100 processes: 99 normal (around 100MB), 1 extreme (2000MB)
        ps_output = "PID PPID RSS COMMAND\n"
        for i in range(99):
            ps_output += f"{1000+i} 1 102400 /usr/bin/agent\n" # 100MB
        ps_output += "2000 1 2048000 /usr/bin/agent\n" # 2000MB outlier

        mock_result = MagicMock()
        mock_result.stdout = ps_output
        mock_run.return_value = mock_result

        result = self.radar.scan_and_analyze()

        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["anomalies"]) > 0)

        # the outlier should be flagged
        outlier = next(a for a in result["anomalies"] if a["pid"] == 2000)
        self.assertTrue(outlier["z_score"] > 3.0)
        self.assertEqual(outlier["flag"], "🔴 红灯")
        self.assertTrue(result["normal_count"] >= 97) # rest are normal

    @patch("subprocess.run")
    def test_missing_parameter_fallback(self, mock_run):
        """测试缺参兜底：无参构造时使用合理的默认关键词并能成功识别"""
        radar_no_args = OrphanAgentProcessReaperAnomalyRadar()

        mock_result = MagicMock()
        mock_result.stdout = (
            "PID PPID RSS COMMAND\n"
            "10 1 50000 mcp-server\n"
            "11 1 50000 node playwright.js\n"
            "12 1 50000 some_agent_runner\n"
        )
        mock_run.return_value = mock_result

        result = radar_no_args.scan_and_analyze()

        # 3 processes, they should all be found since default includes agent, playwright, mcp
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["normal_count"] + len(result["anomalies"]), 3)

    @patch("subprocess.run")
    def test_extreme_boundary_empty_ps(self, mock_run):
        """测试极端边界：ps命令返回空或执行异常时不崩溃，妥善返回"""
        mock_run.side_effect = Exception("ps command failed")

        # Default run_anomaly_radar wrapper test
        result = run_anomaly_radar()

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["anomalies"]), 0)
        self.assertEqual(result["normal_count"], 0)
        self.assertTrue("🟢 绿灯放行" in result["summary"])

if __name__ == "__main__":
    unittest.main()

import unittest
import sys
import os

# Add the parent directory to the path so we can import ultra_modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ultra_modules.orphan_agent_process_reaper_plain_explainer import explain_reaped_processes

class TestOrphanAgentProcessReaperPlainExplainer(unittest.TestCase):
    def test_normal_case_json(self):
        """1. Normal case with valid process data targeting JSON output."""
        raw_data = [
            {"pid": 1001, "ppid": 1, "name": "Agent_Worker_1", "memory_mb": 150.5},
            {"pid": 1002, "ppid": 1, "name": "playwright-browser", "memory_mb": 300.0},
            {"pid": 1003, "ppid": 1, "name": "mcp-server", "memory_mb": 50.0},
            {"pid": 1004, "ppid": 2, "name": "Agent_Worker_2", "memory_mb": 100.0}, # ppid != 1
            {"pid": 1005, "ppid": 1, "name": "system-daemon", "memory_mb": 20.0}, # not agent/mcp/playwright
        ]
        result = explain_reaped_processes(raw_data, output_format="json")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["metrics"]["reaped_count"], 3)
        self.assertEqual(result["metrics"]["freed_memory_mb"], 500.5)
        self.assertEqual(len(result["details"]), 3)
        self.assertIn("系统已成功识别并清理了 3 个", result["summary"])

    def test_dirty_data_self_healing(self):
        """2. Dirty data self-healing: invalid types, missing keys, completely malformed dicts."""
        class MalformedDict(dict):
            def get(self, k, default=None):
                raise Exception("Malformed")

        raw_data = [
            {"pid": 2001, "ppid": "1", "name": "Agent_1", "memory_mb": "100.5"}, # string values
            {"ppid": 1, "name": "playwright", "memory_mb": None}, # missing pid, None memory
            "this is not a dictionary", # invalid item
            {"ppid": 1, "name": {"agent": "type"}, "memory_mb": 50}, # name is dict, contains agent
            {"pid": 2004, "ppid": 1, "name": "mcp-service", "memory_mb": -50}, # negative memory
            {"pid": 2005, "ppid": None, "name": "agent"}, # None ppid
            MalformedDict() # trigger Exception path
        ]
        result = explain_reaped_processes(raw_data, output_format="json")

        self.assertEqual(result["metrics"]["reaped_count"], 4)
        # 100.5 + 0.0 + 50.0 + 0.0 (negative becomes 0) = 150.5
        self.assertEqual(result["metrics"]["freed_memory_mb"], 150.5)

        # Checking details for the self-healed entries
        details = result["details"]
        self.assertEqual(details[0]["name"], "Agent_1")
        self.assertEqual(details[0]["memory_mb"], 100.5)
        self.assertEqual(details[1]["pid"], "Unknown")
        self.assertEqual(details[1]["memory_mb"], 0.0)
        self.assertEqual(details[2]["name"], "{'agent': 'type'}")
        self.assertEqual(details[3]["memory_mb"], 0.0)

    def test_missing_parameter_default_fallback(self):
        """3. Missing parameter default fallback: None or empty inputs, invalid raw_data types."""
        # Test None
        result_none = explain_reaped_processes(None)
        self.assertEqual(result_none["metrics"]["reaped_count"], 0)
        self.assertEqual(result_none["metrics"]["freed_memory_mb"], 0)
        self.assertEqual(result_none["summary"], "系统运行健康，未发现任何需要清理的残留孤儿进程。")

        # Test not a list
        result_dict = explain_reaped_processes({"some": "dict"})
        self.assertEqual(result_dict["metrics"]["reaped_count"], 0)

        # Test empty list
        result_empty = explain_reaped_processes([])
        self.assertEqual(result_empty["metrics"]["reaped_count"], 0)

    def test_extreme_edge_cases(self):
        """4. Extreme edge case: very large memory values, strange process names."""
        raw_data = [
            {"pid": 9999999, "ppid": 1, "name": "AGENT_OVERFLOW_" * 100, "memory_mb": 999999999.99},
            {"pid": 1, "ppid": 1, "name": "mcp_0", "memory_mb": 0.00001},
        ]
        result = explain_reaped_processes(raw_data, output_format="json")

        self.assertEqual(result["metrics"]["reaped_count"], 2)
        self.assertEqual(result["metrics"]["freed_memory_mb"], 999999999.99) # 999999999.99 + 0.00001 rounded to 2 decimals

    def test_different_output_formats(self):
        """5. Different output formats: HTML and Markdown."""
        raw_data = [
            {"pid": 1001, "ppid": 1, "name": "agent-worker", "memory_mb": 100.0}
        ]

        # Test HTML
        html_result = explain_reaped_processes(raw_data, output_format="html")
        self.assertIsInstance(html_result, str)
        self.assertIn("<div class='reaper-card'", html_result)
        self.assertIn("agent-worker", html_result)
        self.assertIn("100.0", html_result)

        # Test HTML with no processes
        html_empty = explain_reaped_processes([], output_format="html")
        self.assertIsInstance(html_empty, str)
        self.assertIn("系统运行健康", html_empty)
        self.assertNotIn("<li>", html_empty)

        # Test Markdown
        md_result = explain_reaped_processes(raw_data, output_format="markdown")
        self.assertIsInstance(md_result, str)
        self.assertIn("### 🧹 孤儿进程清理报告", md_result)
        self.assertIn("`agent-worker`", md_result)

        # Test Markdown with no processes
        md_empty = explain_reaped_processes([], output_format="markdown")
        self.assertIsInstance(md_empty, str)
        self.assertIn("系统运行健康", md_empty)
        self.assertNotIn("- 进程:", md_empty)

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
import psutil
from typing import Dict, Any, List

from ultra_modules.orphan_agent_process_reaper_integration_bridge import OrphanProcessReaperIntegrationBridge, reap_orphan_processes

class TestOrphanProcessReaperIntegrationBridge(unittest.TestCase):

    def setUp(self):
        self.bridge = OrphanProcessReaperIntegrationBridge()

    def test_normal_schema_mapping_and_termination(self):
        """Test 1: Valid mapping and normal process termination scenario (target keyword and ppid=1)."""
        input_processes = [
            # Uses alternative schema field names
            {"process_id": 9991, "name": "node", "ParentPID": 1, "args": ["playwright", "worker"]},
            # Not an orphan
            {"PID": 9992, "process_name": "bash", "PPID": 100, "command": "/bin/bash"},
            # Orphan but not target keyword
            {"id": 9993, "Name": "systemd", "ppid": 1, "CmdLine": "/sbin/init"}
        ]

        with patch('psutil.Process') as mock_process_cls:
            mock_process = MagicMock()
            mock_process_cls.return_value = mock_process

            reaped_count = self.bridge.process_and_reap(input_processes)

            self.assertEqual(reaped_count, 1)
            mock_process_cls.assert_called_once_with(9991)
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=3)

            # Check audit logs
            log_messages = "\n".join(self.bridge.audit_log)
            self.assertIn("Target orphan identified", log_messages)
            self.assertIn("Successfully reaped process 9991", log_messages)

    def test_dirty_data_self_healing(self):
        """Test 2: Dirty data self-healing, such as invalid values in fields."""
        input_processes = [
            # PID is string that cannot be cast, PPID is valid but has wrong field names
            {"pid": "invalid_pid", "process_id": "9994", "ppid": None, "ParentPID": "1", "name": "agent_worker", "cmdline": "agent start"},
            # Dict inside list
            {"pid": 9995, "ppid": 1, "name": "mcp_server", "cmdline": ["run", {"bad": "type"}]},
            # Completely missing critical fields
            {"unrelated": "field"}
        ]

        with patch('psutil.Process') as mock_process_cls:
            mock_process = MagicMock()
            mock_process_cls.return_value = mock_process

            reaped_count = self.bridge.process_and_reap(input_processes)

            self.assertEqual(reaped_count, 2)
            mock_process_cls.assert_any_call(9994)
            mock_process_cls.assert_any_call(9995)
            self.assertEqual(mock_process.terminate.call_count, 2)

    def test_missing_parameter_defaults(self):
        """Test 3: Missing parameter defaults, like providing None (empty config)."""
        # When process_list is None, it should fetch from psutil automatically
        mock_process_iter = MagicMock()

        # Creating mock processes
        p1 = MagicMock()
        p1.info = {'pid': 1234, 'name': 'headless_chrome', 'ppid': 1, 'cmdline': ['--headless']}
        p2 = MagicMock()
        p2.info = {'pid': 1235, 'name': 'bash', 'ppid': 100, 'cmdline': ['bash']}

        with patch('psutil.process_iter', return_value=[p1, p2]) as mock_iter, \
             patch('psutil.Process') as mock_process_cls:

            mock_process = MagicMock()
            mock_process_cls.return_value = mock_process

            # Simple frontend wrapper call
            reaped_count = reap_orphan_processes(None)

            self.assertEqual(reaped_count, 1)
            mock_process_cls.assert_called_once_with(1234)

        # Test invalid type fallback to empty list
        with patch('psutil.process_iter', return_value=[]) as mock_iter:
            # Should treat as empty list
            reaped_count = reap_orphan_processes("not_a_list")
            self.assertEqual(reaped_count, 0)

    def test_extreme_boundary_conditions(self):
        """Test 4: Extreme boundary condition where the process does not exist or permission is denied."""
        input_processes = [
            {"pid": 8001, "ppid": 1, "name": "agent1", "cmdline": ["start"]},
            {"pid": 8002, "ppid": 1, "name": "agent2", "cmdline": ["start"]},
            {"pid": 8003, "ppid": 1, "name": "agent3", "cmdline": ["start"]}
        ]

        def mock_process_side_effect(pid):
            if pid == 8001:
                raise psutil.NoSuchProcess(pid)
            elif pid == 8002:
                raise psutil.AccessDenied(pid)
            elif pid == 8003:
                mock_proc = MagicMock()
                mock_proc.wait.side_effect = psutil.TimeoutExpired(seconds=3)
                return mock_proc

        with patch('psutil.Process', side_effect=mock_process_side_effect):
            reaped_count = self.bridge.process_and_reap(input_processes)

            # Only 8003 is "successfully" reaped (via kill fallback)
            self.assertEqual(reaped_count, 1)

            log_messages = "\n".join(self.bridge.audit_log)
            self.assertIn("already dead/not found", log_messages)
            self.assertIn("Access denied", log_messages)
            self.assertIn("Force killed PID 8003", log_messages)

    def test_audit_log_verification(self):
        """Test 5: Verifying the audit logs to make sure the backend actions are traceable."""
        input_processes = [
            {"pid": 9001, "ppid": 1, "name": "agent", "cmdline": "run"}
        ]
        with patch('psutil.Process') as mock_process_cls:
            self.bridge.process_and_reap(input_processes)

            logs = self.bridge.audit_log

            self.assertTrue(any("Starting process_and_reap" in log for log in logs))
            self.assertTrue(any("Normalized schema" in log for log in logs))
            self.assertTrue(any("Target orphan identified" in log for log in logs))
            self.assertTrue(any("Successfully reaped process 9001" in log for log in logs))
            self.assertTrue(any("Completed process_and_reap" in log for log in logs))

if __name__ == '__main__':
    unittest.main()

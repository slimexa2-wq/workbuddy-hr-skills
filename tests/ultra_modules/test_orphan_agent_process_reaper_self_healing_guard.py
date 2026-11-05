import unittest
from unittest.mock import patch, MagicMock
import os
import signal
import time
from ultra_modules.orphan_agent_process_reaper_self_healing_guard import OrphanAgentProcessReaper

class TestOrphanAgentProcessReaper(unittest.TestCase):

    def setUp(self):
        # Sample output of `ps -e -o pid,ppid,args`
        self.mock_ps_output = """
  PID  PPID COMMAND
    1     0 init
   10     1 /usr/bin/python3 agent_script.py
   20     1 /opt/playwright/bin/browser
   30     1 ./mcp_server
   40     2 some_other_process
   50     1 not_an_orphan_to_kill
"""

    @patch('subprocess.check_output')
    @patch('os.kill')
    def test_normal_reap_and_undo(self, mock_kill, mock_check_output):
        """Test normal execution flow: finding, reaping, and undoing."""
        mock_check_output.return_value = self.mock_ps_output
        reaper = OrphanAgentProcessReaper()

        # Test reap
        reaped_count = reaper.reap()
        self.assertEqual(reaped_count, 3)
        mock_check_output.assert_called_once()

        # 3 calls to kill with SIGSTOP
        self.assertEqual(mock_kill.call_count, 3)
        mock_kill.assert_any_call(10, signal.SIGSTOP)
        mock_kill.assert_any_call(20, signal.SIGSTOP)
        mock_kill.assert_any_call(30, signal.SIGSTOP)

        # Reset mock
        mock_kill.reset_mock()

        # Test undo within window
        restored_count = reaper.undo()
        self.assertEqual(restored_count, 3)

        # 3 calls to kill with SIGCONT
        self.assertEqual(mock_kill.call_count, 3)
        mock_kill.assert_any_call(10, signal.SIGCONT)
        mock_kill.assert_any_call(20, signal.SIGCONT)
        mock_kill.assert_any_call(30, signal.SIGCONT)

    def test_dirty_data_self_healing(self):
        """Test self-healing from dirty data types for keywords."""
        # Missing/None
        reaper1 = OrphanAgentProcessReaper(keywords=None)
        self.assertEqual(reaper1.keywords, ["Agent", "Playwright", "MCP"])

        # String instead of list
        reaper2 = OrphanAgentProcessReaper(keywords="Agent")
        self.assertEqual(reaper2.keywords, ["Agent"])

        # Integers or invalid types inside list
        reaper3 = OrphanAgentProcessReaper(keywords=["Agent", 123, None, "  "])
        self.assertEqual(reaper3.keywords, ["Agent", "123"])

        # Completely invalid type (int)
        reaper4 = OrphanAgentProcessReaper(keywords=123)
        self.assertEqual(reaper4.keywords, ["Agent", "Playwright", "MCP"])

    @patch('subprocess.check_output')
    @patch('os.kill')
    def test_undo_window_expiry(self, mock_kill, mock_check_output):
        """Test that undo does nothing if window has expired."""
        mock_check_output.return_value = self.mock_ps_output
        reaper = OrphanAgentProcessReaper()

        # Mock time to simulate expiration
        with patch('time.time', side_effect=[0.0, 6.0]):
            reaper.reap()
            restored_count = reaper.undo()

        self.assertEqual(restored_count, 0)
        # Only called for STOP, not CONT
        self.assertEqual(mock_kill.call_count, 3)

    @patch('subprocess.check_output')
    def test_subprocess_failure_self_healing(self, mock_check_output):
        """Test that subprocess failure fails silently and gracefully."""
        mock_check_output.side_effect = Exception("Command failed")
        reaper = OrphanAgentProcessReaper()

        # Should not raise an exception
        reaped_count = reaper.reap()
        self.assertEqual(reaped_count, 0)

    @patch('subprocess.check_output')
    @patch('os.kill')
    def test_os_kill_permission_error(self, mock_kill, mock_check_output):
        """Test that os.kill permission errors are handled silently."""
        mock_check_output.return_value = self.mock_ps_output

        # First process fails, others succeed
        def kill_side_effect(pid, sig):
            if pid == 10:
                raise PermissionError("Access denied")
            return None

        mock_kill.side_effect = kill_side_effect
        reaper = OrphanAgentProcessReaper()

        reaped_count = reaper.reap()

        # Should only count the 2 successful ones
        self.assertEqual(reaped_count, 2)

        # Undo should only attempt to restore the 2 successful ones
        mock_kill.reset_mock()
        mock_kill.side_effect = None # Reset side effect for undo
        restored_count = reaper.undo()

        self.assertEqual(restored_count, 2)
        mock_kill.assert_any_call(20, signal.SIGCONT)
        mock_kill.assert_any_call(30, signal.SIGCONT)

if __name__ == '__main__':
    unittest.main()

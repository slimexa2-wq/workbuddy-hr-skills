import unittest
from unittest.mock import patch, MagicMock
import psutil
from ultra_modules.orphan_agent_process_reaper_audit_trace import OrphanProcessReaper, reap_orphan_processes

class TestOrphanProcessReaper(unittest.TestCase):
    def setUp(self):
        self.mock_proc = MagicMock(spec=psutil.Process)
        self.mock_proc.pid = 12345
        self.mock_proc.info = {
            'pid': 12345,
            'ppid': 1,
            'name': 'agent-process',
            'cmdline': ['/usr/bin/agent']
        }
        self.mock_proc.name.return_value = 'agent-process'
        self.mock_proc.cmdline.return_value = ['/usr/bin/agent']

    @patch('psutil.process_iter')
    def test_normal_execution(self, mock_process_iter):
        """Test Case 1: Normal execution with a valid simulated process."""
        mock_process_iter.return_value = [self.mock_proc]

        result = reap_orphan_processes(target_names=['agent'])

        self.assertEqual(result['summary']['status'], 'success')
        self.assertEqual(result['summary']['reaped_count'], 1)
        self.mock_proc.terminate.assert_called_once()
        self.mock_proc.wait.assert_called_once_with(timeout=3)

    @patch('psutil.process_iter')
    def test_dirty_data_auto_healing(self, mock_process_iter):
        """Test Case 2: Dirty data auto-healing (e.g., malformed process info)."""
        dirty_proc = MagicMock(spec=psutil.Process)
        # Delete pid attribute completely to simulate extreme dirty data
        del dirty_proc.pid

        dirty_proc.info = {
            'pid': None,
            'ppid': 1,
            'name': 'mcp-server',
            'cmdline': None
        }
        # Simulate errors when calling name() or cmdline()
        dirty_proc.name.side_effect = psutil.AccessDenied()
        dirty_proc.cmdline.side_effect = psutil.AccessDenied()

        mock_process_iter.return_value = [dirty_proc]

        # It should process it, but due to pid=-1 (fallback), it won't actually call terminate
        # (in our logic we skip pid=-1 for deduplication / reap logic)
        # We can test that the module handles it gracefully without crashing.
        result = reap_orphan_processes(target_names=['mcp'])

        self.assertEqual(result['summary']['status'], 'success')
        self.assertEqual(result['summary']['reaped_count'], 0) # Ignored due to pid=-1

    @patch('psutil.process_iter')
    def test_missing_parameter_fallback(self, mock_process_iter):
        """Test Case 3: Missing parameter fallbacks (e.g., using default targets)."""
        playwright_proc = MagicMock(spec=psutil.Process)
        playwright_proc.pid = 999
        playwright_proc.info = {
            'pid': 999, 'ppid': 1, 'name': 'playwright', 'cmdline': []
        }
        playwright_proc.name.return_value = 'playwright'

        mock_process_iter.return_value = [playwright_proc]

        # reap_orphan_processes without arguments, should use defaults ("agent", "playwright", "mcp")
        result = reap_orphan_processes()

        self.assertEqual(result['summary']['status'], 'success')
        self.assertEqual(result['summary']['reaped_count'], 1)
        playwright_proc.terminate.assert_called_once()

    @patch('psutil.process_iter')
    def test_extreme_edge_cases(self, mock_process_iter):
        """Test Case 4: Extreme edge case (no matching processes, non-existent PID, deduplication)."""
        # Empty iteration
        mock_process_iter.return_value = []
        result = reap_orphan_processes()
        self.assertEqual(result['summary']['status'], 'success')
        self.assertEqual(result['summary']['reaped_count'], 0)

        # Test deduplication
        dup_proc1 = MagicMock(spec=psutil.Process)
        dup_proc1.pid = 111
        dup_proc1.info = {'pid': 111, 'ppid': 1, 'name': 'agent', 'cmdline': []}

        dup_proc2 = MagicMock(spec=psutil.Process)
        dup_proc2.pid = 111
        dup_proc2.info = {'pid': 111, 'ppid': 1, 'name': 'agent', 'cmdline': []}

        mock_process_iter.return_value = [dup_proc1, dup_proc2]
        result = reap_orphan_processes()
        self.assertEqual(result['summary']['reaped_count'], 1)
        dup_proc1.terminate.assert_called_once()
        dup_proc2.terminate.assert_not_called()

        # Test termination exceptions (e.g. process already gone)
        gone_proc = MagicMock(spec=psutil.Process)
        gone_proc.pid = 222
        gone_proc.info = {'pid': 222, 'ppid': 1, 'name': 'agent', 'cmdline': []}
        gone_proc.terminate.side_effect = psutil.NoSuchProcess(222)
        mock_process_iter.return_value = [gone_proc]
        result = reap_orphan_processes()
        self.assertEqual(result['summary']['status'], 'success') # Skipped cleanly

    @patch('psutil.process_iter')
    def test_audit_trace_generation(self, mock_process_iter):
        """Test Case 5: Audit trace generation verification."""
        mock_process_iter.return_value = [self.mock_proc]

        result = reap_orphan_processes(target_names=['agent'])

        audit_trace = result['audit_trace']
        self.assertTrue(len(audit_trace) > 0)

        actions = [entry['action'] for entry in audit_trace]
        self.assertIn('DISCOVER_START', actions)
        self.assertIn('DISCOVER_END', actions)
        self.assertIn('REAP_START', actions)
        self.assertIn('REAP_SUCCESS', actions)
        self.assertIn('REAP_END', actions)

if __name__ == '__main__':
    unittest.main()

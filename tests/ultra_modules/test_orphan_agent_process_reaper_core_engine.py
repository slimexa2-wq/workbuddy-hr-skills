import unittest
from ultra_modules.orphan_agent_process_reaper_core_engine import identify_orphan_processes_to_reap

class TestOrphanAgentProcessReaperCoreEngine(unittest.TestCase):

    def test_normal_operation(self):
        """Test normal operation with valid data and expected orphans."""
        process_list = [
            {'pid': 100, 'ppid': 1, 'cmd': '/usr/bin/node agent.js'},
            {'pid': 101, 'ppid': 2, 'cmd': 'playwright-test'},
            {'pid': 102, 'ppid': 1, 'cmd': 'python mcp_server.py'},
            {'pid': 103, 'ppid': 1, 'cmd': 'bash some_script.sh'}
        ]
        result = identify_orphan_processes_to_reap(process_list)
        self.assertEqual(len(result), 2)
        pids = [proc['pid'] for proc in result]
        self.assertIn(100, pids)
        self.assertIn(102, pids)
        self.assertNotIn(101, pids) # PPID is not 1
        self.assertNotIn(103, pids) # Command doesn't match default keywords

    def test_dirty_data_self_healing(self):
        """Test that the function can silently handle dirty data like strings for pids or missing fields."""
        process_list = [
            {'pid': '200', 'ppid': '1', 'cmd': 'AGENT_process'}, # Strings instead of ints
            {'pid': None, 'ppid': 1, 'cmd': 'playwright'}, # Missing PID
            {'pid': 202, 'ppid': 'invalid', 'cmd': 'mcp'}, # Invalid PPID string
            {'pid': 203, 'ppid': 1, 'command': 'playwright-runner'}, # Uses 'command' instead of 'cmd'
            "Not a dictionary" # Invalid list element
        ]
        result = identify_orphan_processes_to_reap(process_list)
        self.assertEqual(len(result), 2)

        # Validates first case: case insensitivity and string conversion
        self.assertEqual(result[0]['pid'], 200)
        self.assertEqual(result[0]['ppid'], 1)
        self.assertEqual(result[0]['cmd'], 'AGENT_process')

        # Validates fourth case: alternative key 'command'
        self.assertEqual(result[1]['pid'], 203)
        self.assertEqual(result[1]['ppid'], 1)
        self.assertEqual(result[1]['cmd'], 'playwright-runner')

    def test_missing_parameter_fallback(self):
        """Test zero-config defaults when no parameters are provided."""
        # When process_list is missing, it should just return an empty list without error
        result_none = identify_orphan_processes_to_reap()
        self.assertEqual(result_none, [])

        # When target_keywords is missing, defaults should apply
        process_list = [
            {'pid': 300, 'ppid': 1, 'cmd': 'PlayWright'}
        ]
        result_default_keywords = identify_orphan_processes_to_reap(process_list)
        self.assertEqual(len(result_default_keywords), 1)
        self.assertEqual(result_default_keywords[0]['pid'], 300)

    def test_extreme_edge_cases(self):
        """Test extreme cases like negative pids, empty command strings, invalid types."""
        process_list = [
            {'pid': -5, 'ppid': 1, 'cmd': 'agent'}, # Negative PID should be ignored
            {'pid': 401, 'ppid': 1, 'cmd': ''}, # Empty command string
            {'pid': 402, 'ppid': 1}, # Missing command/cmd entirely
            {'pid': 403, 'ppid': 1, 'cmd': None} # None command
        ]
        # Should not throw any exception and should return an empty list
        # because none are valid match criteria with positive PID and matching string
        result = identify_orphan_processes_to_reap(process_list)
        self.assertEqual(result, [])

    def test_custom_target_keywords(self):
        """Test with custom keywords overriding the defaults."""
        process_list = [
            {'pid': 500, 'ppid': 1, 'cmd': 'custom-worker'},
            {'pid': 501, 'ppid': 1, 'cmd': 'agent'}
        ]
        custom_keywords = ['custom']
        result = identify_orphan_processes_to_reap(process_list, target_keywords=custom_keywords)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['pid'], 500)

    def test_non_list_input_healing(self):
        """Test when process_list is provided but is completely wrong type (not a list)."""
        result = identify_orphan_processes_to_reap({"this": "is a dict, not a list"})
        self.assertEqual(result, [])

if __name__ == '__main__':
    unittest.main()

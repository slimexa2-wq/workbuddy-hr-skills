import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from guards.agent_reaper import descendants, is_tool_process

class TestAgentReaper(unittest.TestCase):
    def test_descendants(self):
        children = {
            1: [2, 3],
            2: [4],
            3: [5, 6],
            4: [],
            5: [],
            6: []
        }
        res = descendants(children, 1)
        self.assertCountEqual(res, [2, 3, 4, 5, 6])

        res_empty = descendants(children, 4)
        self.assertEqual(res_empty, [])

    def test_is_tool_process(self):
        self.assertTrue(is_tool_process("node /path/to/script.js"))
        self.assertTrue(is_tool_process("/usr/bin/python3 script.py"))
        self.assertTrue(is_tool_process("/opt/homebrew/bin/bash script.sh"))
        self.assertTrue(is_tool_process("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless"))

        self.assertFalse(is_tool_process("/System/Library/CoreServices/Finder.app/Contents/MacOS/Finder"))
        self.assertFalse(is_tool_process("/usr/sbin/syslogd"))
        self.assertFalse(is_tool_process("/Applications/Safari.app/Contents/MacOS/Safari"))
        self.assertFalse(is_tool_process("vscode-server"))

if __name__ == "__main__":
    unittest.main()

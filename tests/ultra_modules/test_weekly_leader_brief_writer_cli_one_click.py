import unittest
import json
import os
import tempfile
from unittest.mock import patch
from io import StringIO

from ultra_modules.weekly_leader_brief_writer_cli_one_click import (
    generate_weekly_brief,
    clean_data,
    main,
    parse_excel
)

class TestWeeklyLeaderBriefWriter(unittest.TestCase):

    def setUp(self):
        # Create temporary files for testing file inputs
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_data_normal(self):
        # Normal data
        data = {
            "new_hires": 5,
            "departures": 2,
            "total_employees": 120,
            "interview_count": 15,
            "key_departures": "张三",
            "notes": "顺利"
        }
        cleaned = clean_data(data)
        self.assertEqual(cleaned["new_hires"], 5)
        self.assertEqual(cleaned["departures"], 2)
        self.assertEqual(cleaned["total_employees"], 120)
        self.assertEqual(cleaned["interview_count"], 15)
        self.assertEqual(cleaned["key_departures"], "张三")
        self.assertEqual(cleaned["notes"], "顺利")

    def test_clean_data_dirty_healing(self):
        # Dirty data self-healing scenarios (negatives, wrong types)
        data = {
            "new_hires": -5,  # Negative
            "departures": "abc",  # String where int is expected
            "total_employees": None,  # None
            "interview_count": 3.14,  # Float
            "key_departures": "张三\x00",  # Control character
            "notes": "   \n " # Whitespace
        }
        cleaned = clean_data(data)
        self.assertEqual(cleaned["new_hires"], 0) # Healing negative to 0
        self.assertEqual(cleaned["departures"], 0) # Fallback to 0 for invalid type
        self.assertEqual(cleaned["total_employees"], 100) # Fallback to default
        self.assertEqual(cleaned["interview_count"], 3) # Float cast to int
        self.assertEqual(cleaned["key_departures"], "张三") # Control char removed
        self.assertEqual(cleaned["notes"], "一切正常") # Empty/whitespace fallback

    def test_clean_data_missing_fallback_and_aliases(self):
        # Missing parameters default fallbacks and aliases
        data = {
            "新入职": 4, # alias
            "流失": 1, # alias
            # total_employees missing
            # interview_count missing
            # key_departures missing
            "说明": "测试说明" # alias
        }
        cleaned = clean_data(data)
        self.assertEqual(cleaned["new_hires"], 4)
        self.assertEqual(cleaned["departures"], 1)
        self.assertEqual(cleaned["total_employees"], 100) # Default
        self.assertEqual(cleaned["interview_count"], 0) # Default
        self.assertEqual(cleaned["key_departures"], "无") # Default
        self.assertEqual(cleaned["notes"], "测试说明")

    def test_generate_weekly_brief_extreme_boundaries(self):
        # Extreme boundary cases (very large numbers)
        data = {
            "new_hires": 99999999,
            "departures": 0,
            "total_employees": 0,
            "interview_count": 9999999999,
            "key_departures": "A"*1000,
            "notes": ""
        }
        brief = generate_weekly_brief(data)
        self.assertIn("新入职 99999999 人", brief)
        self.assertIn("当前在职总人数为 0 人", brief)
        self.assertIn("本周离职 0 人", brief)
        self.assertIn("面试完成 9999999999 人", brief)
        self.assertIn("A"*1000, brief)
        self.assertIn("一切正常", brief) # Empty string fallback

    def test_generate_weekly_brief_empty(self):
        brief = generate_weekly_brief()
        self.assertIn("当前在职总人数为 100 人", brief)
        self.assertIn("本周新入职 0 人", brief)
        self.assertIn("本周离职 0 人", brief)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_json_string(self, mock_stdout):
        # Test CLI with json string
        test_data = {"new_hires": 10, "departures": 2}
        json_str = json.dumps(test_data)

        with patch('sys.argv', ['prog', '--json-str', json_str]):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("本周新入职 10 人", output)
        self.assertIn("本周离职 2 人", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_json_file(self, mock_stdout):
        # Test CLI with json file
        test_data = {"new_hires": 7, "departures": 3}
        json_file_path = os.path.join(self.temp_dir.name, 'test.json')
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        with patch('sys.argv', ['prog', '--json-file', json_file_path]):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("本周新入职 7 人", output)
        self.assertIn("本周离职 3 人", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_excel_file(self, mock_stdout):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")

        # Create a test excel file
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["新入职", 8])
        ws.append(["流失", 1])
        ws.append(["在职人数", 150])
        ws.append(["面试人数", 20])
        ws.append(["关键流失", "李四"])
        ws.append(["备注", "顺利"])

        excel_file_path = os.path.join(self.temp_dir.name, 'test.xlsx')
        wb.save(excel_file_path)

        with patch('sys.argv', ['prog', '--excel-file', excel_file_path]):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("本周新入职 8 人", output)
        self.assertIn("本周离职 1 人", output)
        self.assertIn("当前在职总人数为 150 人", output)
        self.assertIn("关键流失：李四", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_no_args_default(self, mock_stdout):
        # Test CLI with no args -> zero-configuration fault tolerance
        with patch('sys.argv', ['prog']):
            main()

        output = mock_stdout.getvalue()
        self.assertIn("本周新入职 3 人", output)
        self.assertIn("本周离职 1 人", output)
        self.assertIn("当前在职总人数为 150 人", output)

if __name__ == '__main__':
    unittest.main()

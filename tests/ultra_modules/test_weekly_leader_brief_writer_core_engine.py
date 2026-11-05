import unittest
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ultra_modules.weekly_leader_brief_writer_core_engine import generate_weekly_hr_brief

class TestWeeklyLeaderBriefWriterCoreEngine(unittest.TestCase):

    def test_normal_data(self):
        """Test with normal input data."""
        data = {
            'week_start': '2023-10-01',
            'week_end': '2023-10-07',
            'department': '研发部',
            'onboarded': 5,
            'offboarded': 2
        }
        report = generate_weekly_hr_brief(data)
        self.assertIn('2023-10-01 至 2023-10-07', report)
        self.assertIn('研发部', report)
        self.assertIn('本周入职人数：5 人', report)
        self.assertIn('本周离职人数：2 人', report)
        self.assertIn('净增 3 人', report)

    def test_missing_data_fallback(self):
        """Test with missing data to ensure defaults are used."""
        report = generate_weekly_hr_brief({})
        self.assertIn('未知开始日期 至 未知结束日期', report)
        self.assertIn('全局', report)
        self.assertIn('本周入职人数：0 人', report)
        self.assertIn('本周离职人数：0 人', report)
        self.assertIn('净增减 0 人', report)

    def test_none_input(self):
        """Test with None input."""
        report = generate_weekly_hr_brief(None)
        self.assertIn('未知开始日期 至 未知结束日期', report)
        self.assertIn('全局', report)
        self.assertIn('本周入职人数：0 人', report)

    def test_dirty_data_self_healing(self):
        """Test with dirty data like invalid strings, negative counts."""
        data = {
            'week_start': '   2023-10-08   ',
            'week_end': '',
            'department': '   ',
            'onboarded': 'abc',
            'offboarded': -5
        }
        report = generate_weekly_hr_brief(data)
        self.assertIn('2023-10-08 至 未知结束日期', report)
        self.assertIn('全局', report)
        self.assertIn('本周入职人数：0 人', report)
        self.assertIn('本周离职人数：0 人', report)
        self.assertIn('净增减 0 人', report)

    def test_list_dict_counts(self):
        """Test counts provided as lists or dicts."""
        data = {
            'onboarded': ['Alice', 'Bob', 'Charlie'],
            'offboarded': {'David': 'resigned', 'Eve': 'fired'}
        }
        report = generate_weekly_hr_brief(data)
        self.assertIn('本周入职人数：3 人', report)
        self.assertIn('本周离职人数：2 人', report)
        self.assertIn('净增 1 人', report)

    def test_float_string_counts(self):
        """Test counts provided as floats or strings containing floats."""
        data = {
            'onboarded': 3.7,
            'offboarded': ' 4.2 '
        }
        report = generate_weekly_hr_brief(data)
        self.assertIn('本周入职人数：3 人', report)
        self.assertIn('本周离职人数：4 人', report)
        self.assertIn('净减 1 人', report)

    def test_extreme_boundary_cases(self):
        """Test with completely unexpected data type for input."""
        report = generate_weekly_hr_brief(["unexpected", "list"])
        self.assertIn('未知开始日期', report)
        self.assertIn('本周入职人数：0 人', report)

if __name__ == '__main__':
    unittest.main()

import unittest
import time
from unittest.mock import patch
from ultra_modules.weekly_leader_brief_writer_self_healing_guard import WeeklyLeaderBriefWriterSelfHealingGuard

class TestWeeklyLeaderBriefWriterSelfHealingGuard(unittest.TestCase):
    def setUp(self):
        self.guard = WeeklyLeaderBriefWriterSelfHealingGuard()

    def test_normal_input(self):
        data = {
            "department": "技术部",
            "new_hires": 5,
            "resignations": 2,
            "active_employees": 120
        }
        result = self.guard.generate_brief(data)
        self.assertEqual(result, "【技术部】本周入职5人，离职2人，当前在职120人。")

    def test_dirty_data_self_healing(self):
        data = {
            "department": "  市场   部  \n",
            "new_hires": " 12人 ",
            "resignations": 1.5,
            "active_employees": "approx 105 total"
        }
        result = self.guard.generate_brief(data)
        self.assertEqual(result, "【市场 部】本周入职12人，离职1人，当前在职105人。")

    def test_missing_parameter_default_fallback(self):
        result = self.guard.generate_brief(None)
        self.assertEqual(result, "【祥能人力】本周入职0人，离职0人，当前在职0人。")

        result_empty_dict = self.guard.generate_brief({})
        self.assertEqual(result_empty_dict, "【祥能人力】本周入职0人，离职0人，当前在职0人。")

        result_partial = self.guard.generate_brief({"department": "人事部"})
        self.assertEqual(result_partial, "【人事部】本周入职0人，离职0人，当前在职0人。")

        result_none_values = self.guard.generate_brief({
            "department": None,
            "new_hires": None,
            "resignations": None,
            "active_employees": None
        })
        self.assertEqual(result_none_values, "【祥能人力】本周入职0人，离职0人，当前在职0人。")

    def test_extreme_boundaries(self):
        data = {
            "department": "A" * 1000,
            "new_hires": -50,
            "resignations": 999999999999999999999999999999,
            "active_employees": "-1000"
        }
        result = self.guard.generate_brief(data)
        expected = f"【{'A' * 1000}】本周入职-50人，离职999999999999999999999999999999人，当前在职-1000人。"
        self.assertEqual(result, expected)

    def test_undo_snapshot_mechanism(self):
        # Initial generation
        result1 = self.guard.generate_brief({"department": "测试一", "new_hires": 1, "resignations": 0, "active_employees": 10})
        self.assertEqual(result1, "【测试一】本周入职1人，离职0人，当前在职10人。")

        # Second generation
        result2 = self.guard.generate_brief({"department": "测试二", "new_hires": 2, "resignations": 1, "active_employees": 11})
        self.assertEqual(result2, "【测试二】本周入职2人，离职1人，当前在职11人。")

        # Undo within 5 seconds
        undo_result = self.guard.undo()
        self.assertEqual(undo_result, "【测试一】本周入职1人，离职0人，当前在职10人。")

        # Undo again should do nothing (snapshot consumed)
        undo_result2 = self.guard.undo()
        self.assertEqual(undo_result2, "【测试一】本周入职1人，离职0人，当前在职10人。")

    @patch('time.time')
    def test_undo_expiration(self, mock_time):
        mock_time.return_value = 1000.0
        # Generate with mocked time
        self.guard.generate_brief({"department": "测试三"})

        mock_time.return_value = 1001.0
        result2 = self.guard.generate_brief({"department": "测试四"})

        # Advance time by more than 5 seconds
        mock_time.return_value = 1006.1

        # Undo should fail silently and return current text
        undo_result = self.guard.undo()
        self.assertEqual(undo_result, "【测试四】本周入职0人，离职0人，当前在职0人。")

if __name__ == "__main__":
    unittest.main()

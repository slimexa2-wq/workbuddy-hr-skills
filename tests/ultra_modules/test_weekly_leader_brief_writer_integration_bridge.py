import unittest
from ultra_modules.weekly_leader_brief_writer_integration_bridge import WeeklyLeaderBriefWriter

class TestWeeklyLeaderBriefWriterIntegrationBridge(unittest.TestCase):

    def test_normal_case_new_schema(self):
        """Test with correctly formatted standard (new schema) keys."""
        data = {
            'date': '2023年10月',
            'onboarded_count': 5,
            'offboarded_count': 2,
            'current_headcount': 150
        }
        result = WeeklyLeaderBriefWriter.generate_brief(data)
        self.assertIn("【2023年10月】人员流动情况汇报：", result)
        self.assertIn("- 新入职员工：5人", result)
        self.assertIn("- 离职员工：2人", result)
        self.assertIn("- 当前总人数：150人", result)

    def test_normal_case_old_schema_conversion(self):
        """Test with old schema keys, ensuring silent forward compatibility mapping."""
        data = {
            'report_date': 'W42',
            'new_hires': 8,
            'resignations': 1,
            'total_staff': 157
        }
        result = WeeklyLeaderBriefWriter.generate_brief(data)
        self.assertIn("【W42】人员流动情况汇报：", result)
        self.assertIn("- 新入职员工：8人", result)
        self.assertIn("- 离职员工：1人", result)
        self.assertIn("- 当前总人数：157人", result)

    def test_dirty_data_self_healing(self):
        """Test with string values containing numbers where integers are expected (dirty data)."""
        data = {
            'date': ' 本周 ',
            'onboarded_count': '大约 12 人',
            'offboarded_count': '3',
            'current_headcount': '总数: 166'
        }
        result = WeeklyLeaderBriefWriter.generate_brief(data)
        self.assertIn("【本周】人员流动情况汇报：", result)
        self.assertIn("- 新入职员工：12人", result)
        self.assertIn("- 离职员工：3人", result)
        self.assertIn("- 当前总人数：166人", result)

    def test_missing_parameters_default_fallback(self):
        """Test with missing parameters, None values, and empty input to ensure safe defaults."""
        result_none = WeeklyLeaderBriefWriter.generate_brief(None)
        expected_defaults = (
            "【本周】人员流动情况汇报：\n"
            "- 新入职员工：0人\n"
            "- 离职员工：0人\n"
            "- 当前总人数：0人\n"
            "注：数据已自动核对处理。"
        )
        self.assertEqual(result_none, expected_defaults)

        result_empty_dict = WeeklyLeaderBriefWriter.generate_brief({})
        self.assertEqual(result_empty_dict, expected_defaults)

        data_with_none = {
            'date': None,
            'onboarded_count': None,
            'offboarded_count': None,
            'current_headcount': None
        }
        result_partial = WeeklyLeaderBriefWriter.generate_brief(data_with_none)
        self.assertEqual(result_partial, expected_defaults)

    def test_extreme_edge_cases(self):
        """Test with completely unexpected data types and unparseable strings."""
        data = {
            'date': ['list', 'date'],
            'onboarded_count': 'no numbers here',
            'offboarded_count': {}, # dictionary where int expected
            'current_headcount': 123.45 # float where int expected
        }
        result = WeeklyLeaderBriefWriter.generate_brief(data)
        self.assertIn("【['list', 'date']】人员流动情况汇报：", result)
        self.assertIn("- 新入职员工：0人", result)
        self.assertIn("- 离职员工：0人", result)
        self.assertIn("- 当前总人数：123人", result)

if __name__ == '__main__':
    unittest.main()

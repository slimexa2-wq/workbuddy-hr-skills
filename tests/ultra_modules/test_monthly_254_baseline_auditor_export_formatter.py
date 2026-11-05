import unittest
import math
from ultra_modules.monthly_254_baseline_auditor_export_formatter import Monthly254BaselineAuditor

class TestMonthly254BaselineAuditor(unittest.TestCase):
    def setUp(self):
        self.auditor = Monthly254BaselineAuditor()

    def test_normal_usage(self):
        data = [
            {'name': 'Alice', 'days_employed': 8, 'is_active': True},
            {'name': 'Bob', 'days_employed': 5, 'is_active': True},
            {'name': 'Charlie', 'days_employed': 10, 'is_active': False}
        ]
        result = self.auditor.audit_and_format(data)

        self.assertEqual(result['valid_count'], 1)  # Only Alice meets criteria
        self.assertEqual(result['target'], 254)
        self.assertEqual(result['rate'], 1 / 254)
        self.assertIn("当前在职满7天计1人", result['report'])
        self.assertEqual(len(result['clean_data']), 3)

    def test_dirty_data_self_healing(self):
        data = [
            {'days_employed': float('nan'), 'is_active': True},
            {'days_employed': None, 'is_active': None},
            {'days_employed': 'invalid', 'is_active': 'invalid'}
        ]
        result = self.auditor.audit_and_format(data)

        clean_data = result['clean_data']
        self.assertEqual(clean_data[0]['days_employed'], 0)
        self.assertEqual(clean_data[0]['is_active'], True)
        self.assertEqual(clean_data[1]['days_employed'], 0)
        self.assertEqual(clean_data[1]['is_active'], False)  # None becomes False
        self.assertEqual(clean_data[2]['days_employed'], 0)  # Invalid string becomes 0
        self.assertEqual(clean_data[2]['is_active'], True)   # 'invalid' string evaluates to True bool
        self.assertEqual(result['valid_count'], 0)

    def test_missing_parameter_fallbacks(self):
        # Test missing data_list parameter (defaulting to empty list)
        result1 = self.auditor.audit_and_format()
        self.assertEqual(result1['valid_count'], 0)
        self.assertEqual(result1['clean_data'], [])

        # Test passing a single dict instead of list
        single_record = {'days_employed': 10, 'is_active': True}
        result2 = self.auditor.audit_and_format(single_record)
        self.assertEqual(result2['valid_count'], 1)
        self.assertEqual(len(result2['clean_data']), 1)

        # Test completely empty records
        result3 = self.auditor.audit_and_format([{}])
        self.assertEqual(result3['valid_count'], 0)
        self.assertEqual(result3['clean_data'][0]['days_employed'], 0)
        self.assertEqual(result3['clean_data'][0]['is_active'], False)

    def test_zero_comments_and_clean_fields(self):
        data = [
            {'comments': 'Some notes', 'days_employed': 7, 'is_active': True, 'score': float('nan'), 'other': None}
        ]
        result = self.auditor.audit_and_format(data)
        clean_data = result['clean_data'][0]

        self.assertEqual(clean_data['comments'], 0)
        self.assertEqual(clean_data['score'], 0)
        self.assertEqual(clean_data['other'], "")
        self.assertEqual(result['valid_count'], 1)

    def test_boundary_cases(self):
        # 0 target baseline
        auditor_zero = Monthly254BaselineAuditor(target_baseline=0)
        data = [{'days_employed': 7, 'is_active': True}]
        result = auditor_zero.audit_and_format(data)
        self.assertEqual(result['rate'], 0.0)
        self.assertEqual(result['valid_count'], 1)

        # Exact boundary 7 days
        result_7 = self.auditor.audit_and_format([{'days_employed': 7, 'is_active': True}])
        self.assertEqual(result_7['valid_count'], 1)

        # Boundary 6 days
        result_6 = self.auditor.audit_and_format([{'days_employed': 6, 'is_active': True}])
        self.assertEqual(result_6['valid_count'], 0)

if __name__ == '__main__':
    unittest.main()

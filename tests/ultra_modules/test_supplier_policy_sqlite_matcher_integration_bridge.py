import unittest
import datetime
from ultra_modules.supplier_policy_sqlite_matcher_integration_bridge import SupplierPolicySQLiteMatcher

class TestSupplierPolicySQLiteMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = SupplierPolicySQLiteMatcher()

    def test_normal_matching(self):
        # Insert a standard policy
        self.matcher.add_policy({
            'job_title': 'Software Engineer',
            'start_date': '2023-01-01',
            'end_date': '2023-12-31',
            'unit_price': 150.0
        })

        # Test exact match within date range
        result = self.matcher.match_policy('Software Engineer', '2023-06-15')
        self.assertIsNotNone(result)
        self.assertEqual(result['unit_price'], 150.0)
        self.assertEqual(result['job_title'], 'software engineer')

    def test_dirty_data_self_healing(self):
        # Insert policy with messy data
        self.matcher.add_policy({
            'job_title': '  Data Scientist  ',
            'start_date': '2023.01/01',
            'end_date': '2023_12-31',
            'unit_price': '2,500.50'
        })

        # Should self-heal dates and job titles
        result = self.matcher.match_policy('Data Scientist', '2023-05-05')
        self.assertIsNotNone(result)
        self.assertEqual(result['unit_price'], 2500.5)
        self.assertEqual(result['job_title'], 'data scientist')
        self.assertEqual(result['start_date'], '2023-01-01')
        self.assertEqual(result['end_date'], '2023-12-31')

    def test_missing_parameter_fallback(self):
        # Insert minimal policy
        self.matcher.add_policy({
            'unit_price': 100.0
        })

        # Should default to DEFAULT_JOB and very wide dates
        result = self.matcher.match_policy()
        self.assertIsNotNone(result)
        self.assertEqual(result['job_title'], 'default_job')
        self.assertEqual(result['unit_price'], 100.0)

        # Test fallback when querying unknown job without date
        result2 = self.matcher.match_policy('Unknown Job')
        self.assertIsNotNone(result2)
        self.assertEqual(result2['job_title'], 'default_job')

    def test_boundary_cases(self):
        # Policies with overlapping boundaries and reversed dates
        self.matcher.add_policy({
            'job_title': 'QA Tester',
            'start_date': '2023-12-31', # Reversed
            'end_date': '2023-01-01',   # Reversed
            'unit_price': 80.0
        })

        # The reversed dates should be swapped automatically
        result_start = self.matcher.match_policy('QA Tester', '2023-01-01')
        result_end = self.matcher.match_policy('QA Tester', '2023-12-31')

        self.assertIsNotNone(result_start)
        self.assertEqual(result_start['unit_price'], 80.0)

        self.assertIsNotNone(result_end)
        self.assertEqual(result_end['unit_price'], 80.0)

    def test_schema_auto_compatibility(self):
        # Test with old schema fields
        self.matcher.add_policy({
            'role': 'Project Manager',
            'begin_date': '2023-01-01',
            'valid_to': '2023-12-31',
            'rate': 200.0
        })

        result = self.matcher.match_policy('Project Manager', '2023-06-01')
        self.assertIsNotNone(result)
        self.assertEqual(result['job_title'], 'project manager')
        self.assertEqual(result['unit_price'], 200.0)
        self.assertEqual(result['start_date'], '2023-01-01')
        self.assertEqual(result['end_date'], '2023-12-31')

if __name__ == '__main__':
    unittest.main()

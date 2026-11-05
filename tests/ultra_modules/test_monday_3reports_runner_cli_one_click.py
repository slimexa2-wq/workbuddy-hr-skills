import unittest
import os
import json
import csv
from unittest.mock import patch, mock_open

# Adjust import path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ultra_modules.monday_3reports_runner_cli_one_click import (
    parse_project_requirements,
    parse_student_workers,
    parse_campus_recruitment,
    synthesize_reports,
    output_to_json,
    output_to_csv,
    run_reports_one_click
)

class TestMonday3ReportsRunnerCLIOneClick(unittest.TestCase):

    def test_standard_successful_execution(self):
        proj = {'status': 'Active', 'count': 5}
        sw = {'department': 'Engineering', 'headcount': 10}
        cr = {'role': 'Developer', 'performance': 'Excellent'}

        reports = synthesize_reports(proj, sw, cr)
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]['status'], 'Active')
        self.assertEqual(reports[0]['count'], 5)
        self.assertEqual(reports[1]['department'], 'Engineering')
        self.assertEqual(reports[1]['headcount'], 10)
        self.assertEqual(reports[2]['role'], 'Developer')
        self.assertEqual(reports[2]['performance'], 'Excellent')

    def test_dirty_data_correction(self):
        # Invalid types that should be coerced or defaulted
        proj = {'status': 123, 'count': '5'}
        sw = {'department': None, 'headcount': 'invalid'}
        cr = {'role': {'invalid': 'type'}, 'performance': 456}

        reports = synthesize_reports(proj, sw, cr)

        self.assertEqual(reports[0]['status'], '123')
        self.assertEqual(reports[0]['count'], 5)

        self.assertEqual(reports[1]['department'], 'None')
        self.assertEqual(reports[1]['headcount'], 0)

        # 'role' stringifies a dict, which is technically a string, but it won't be empty
        self.assertTrue(isinstance(reports[2]['role'], str))
        self.assertEqual(reports[2]['performance'], '456')

    def test_missing_parameter_default_fallbacks(self):
        # Empty dicts, None values, and missing keys
        proj = {}
        sw = None
        cr = [] # invalid type, should be treated as empty dict

        reports = synthesize_reports(proj, sw, cr)

        self.assertEqual(reports[0]['status'], 'Unknown')
        self.assertEqual(reports[0]['count'], 0)

        self.assertEqual(reports[1]['department'], 'General')
        self.assertEqual(reports[1]['headcount'], 0)

        self.assertEqual(reports[2]['role'], 'Any')
        self.assertEqual(reports[2]['performance'], 'N/A')

    def test_extreme_boundary_inputs(self):
        # Very large numbers, empty strings, whitespace strings
        proj = {'status': '   ', 'count': 9999999999999999999999999999999999}
        sw = {'department': '   ', 'headcount': -100}
        cr = {'role': '', 'performance': '   \n  '}

        reports = synthesize_reports(proj, sw, cr)

        self.assertEqual(reports[0]['status'], 'Unknown') # Stripped and empty -> Unknown
        self.assertEqual(reports[0]['count'], 9999999999999999999999999999999999)

        self.assertEqual(reports[1]['department'], 'General') # Stripped and empty -> General
        self.assertEqual(reports[1]['headcount'], -100)

        self.assertEqual(reports[2]['role'], 'Any')
        self.assertEqual(reports[2]['performance'], 'N/A')

    def test_file_output_adapter_verification(self):
        # Test output_to_json and output_to_csv with valid data
        data = [{'a': 1, 'b': 2}, {'a': 3, 'c': 4}]

        json_path = 'test_temp.json'
        csv_path = 'test_temp.csv'

        self.assertTrue(output_to_json(data, json_path))
        self.assertTrue(os.path.exists(json_path))

        self.assertTrue(output_to_csv(data, csv_path))
        self.assertTrue(os.path.exists(csv_path))

        # Test output_to_csv with empty data
        self.assertFalse(output_to_csv([], csv_path))

        # Test exceptions in output functions
        with patch('builtins.open', side_effect=PermissionError("Mock Permission Error")):
            self.assertFalse(output_to_json(data, json_path))
            self.assertFalse(output_to_csv(data, csv_path))

        # Clean up
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)

    def test_run_reports_one_click(self):
        # Test full pipeline function
        result = run_reports_one_click(output_dir='.')
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 3)
        self.assertTrue(os.path.exists(result['json_path']))
        self.assertTrue(os.path.exists(result['csv_path']))

        # Clean up
        if os.path.exists(result['json_path']):
            os.remove(result['json_path'])
        if os.path.exists(result['csv_path']):
            os.remove(result['csv_path'])

if __name__ == '__main__':
    unittest.main()

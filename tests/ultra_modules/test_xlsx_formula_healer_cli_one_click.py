import unittest
import json
import os
import tempfile
import sys
from io import StringIO
from unittest.mock import patch

from ultra_modules.xlsx_formula_healer_cli_one_click import XlsxFormulaHealerOneClick, process_file, main

class TestXlsxFormulaHealerCliOneClick(unittest.TestCase):
    def setUp(self):
        self.healer = XlsxFormulaHealerOneClick()

    def test_normal_behavior_clean_data(self):
        # 1. Normal behavior
        data = [{"id": 1, "name": "Alice", "score": 95}, {"id": 2, "name": "Bob", "score": 88}]
        result = self.healer.heal_data(data)
        self.assertEqual(result, data)

    def test_dirty_data_healing(self):
        # 2. Dirty data healing (#REF!, #DIV/0!, text numbers, circular ref)
        data = [
            {"id": 1, "value": "#REF!", "cost": " 42.5 "},
            {"id": 2, "value": "#DIV/0!", "cost": "-15"},
            {"id": 3, "value": "circular dependency detected", "cost": "invalid"}
        ]
        result = self.healer.heal_data(data)
        self.assertEqual(result[0]["value"], 0)
        self.assertEqual(result[0]["cost"], 42.5)
        self.assertEqual(result[1]["value"], 0)
        self.assertEqual(result[1]["cost"], -15)
        self.assertEqual(result[2]["value"], 0)
        self.assertEqual(result[2]["cost"], "invalid")

    def test_missing_parameter_fallback(self):
        # 3. Missing parameter/Empty data fallback
        self.assertEqual(self.healer.heal_data([]), [])
        self.assertEqual(self.healer.heal_data({}), {})
        self.assertEqual(self.healer.heal_data(None), None)

        # Test CLI fallback with no args
        with patch('sys.argv', ['xlsx_formula_healer_cli_one_click.py']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with patch('sys.stdin.isatty', return_value=True):
                    main()
                    output = mock_stdout.getvalue()
                    self.assertIn("No input provided", output)
                    self.assertIn("0", output) # The healed #REF! in fallback data
                    self.assertIn("42.5", output) # The parsed number in fallback data

    def test_extreme_boundary_nested_list(self):
        # 4. Extreme boundary: List of lists and flat list
        data_lol = [["#VALUE!", " 123 "], ["text", "#N/A"]]
        res_lol = self.healer.heal_data(data_lol)
        self.assertEqual(res_lol, [[0, 123], ["text", 0]])

        data_flat = ["#NULL!", " 99.9 ", "ok"]
        res_flat = self.healer.heal_data(data_flat)
        self.assertEqual(res_flat, [0, 99.9, "ok"])

    def test_cli_file_processing_json(self):
        # 5. CLI process_file with temporary json file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_in:
            json.dump([{"test": "#REF!", "num": " 10 "}], temp_in)
            temp_in_name = temp_in.name

        temp_out_name = temp_in_name.replace('.json', '_healed.json')

        try:
            success = process_file(temp_in_name, temp_out_name)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(temp_out_name))

            with open(temp_out_name, 'r') as f:
                res = json.load(f)

            self.assertEqual(res, [{"test": 0, "num": 10}])
        finally:
            if os.path.exists(temp_in_name):
                os.remove(temp_in_name)
            if os.path.exists(temp_out_name):
                os.remove(temp_out_name)

    def test_cli_file_processing_xlsx(self):
        # 6. CLI process_file with temporary xlsx file
        import openpyxl
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_in:
            temp_in_name = temp_in.name

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["#REF!", " 10 "])
        wb.save(temp_in_name)

        temp_out_name = temp_in_name.replace('.xlsx', '_healed.xlsx')

        try:
            success = process_file(temp_in_name, temp_out_name)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(temp_out_name))

            wb_out = openpyxl.load_workbook(temp_out_name)
            ws_out = wb_out.active

            self.assertEqual(ws_out.cell(row=1, column=1).value, 0)
            self.assertEqual(ws_out.cell(row=1, column=2).value, 10)
        finally:
            if os.path.exists(temp_in_name):
                os.remove(temp_in_name)
            if os.path.exists(temp_out_name):
                os.remove(temp_out_name)

    def test_cli_stdin_processing(self):
        # 6. Test stdin processing
        input_json = '[{"key": "#DIV/0!"}]'
        expected_json = '[\n  {\n    "key": 0\n  }\n]\n'

        with patch('sys.argv', ['xlsx_formula_healer_cli_one_click.py']):
            with patch('sys.stdin', new_callable=StringIO, initial_value=input_json) as mock_stdin:
                with patch('sys.stdin.isatty', return_value=False):
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        main()
                        output = mock_stdout.getvalue()
                        self.assertEqual(output, expected_json)

if __name__ == '__main__':
    unittest.main()

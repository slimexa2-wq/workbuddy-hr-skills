import unittest
import os
import tempfile
import json
import openpyxl
from openpyxl.comments import Comment

from ultra_modules.zero_comment_null_guard_cli_one_click import process_excel_guard, main

class TestZeroCommentNullGuardCliOneClick(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_excel_path = os.path.join(self.temp_dir.name, "test.xlsx")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normal_operation_no_dirty_data(self):
        # 1. Normal operation with valid Excel containing no comments and no nulls
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = "Name"
        ws['B1'] = "Value"
        ws['A2'] = "Item"
        ws['B2'] = 100
        wb.save(self.test_excel_path)
        wb.close()

        report = process_excel_guard(self.test_excel_path)

        self.assertEqual(report["comments_removed"], 0)
        self.assertEqual(report["nulls_filled_with_zero"], 0)

        # Verify output excel has no changes to actual data
        wb_out = openpyxl.load_workbook(report["output_file"])
        ws_out = wb_out.active
        self.assertEqual(ws_out['A1'].value, "Name")
        self.assertEqual(ws_out['B2'].value, 100)
        wb_out.close()

    def test_dirty_data_healing(self):
        # 2. Dirty data healing: fixing nulls (filling with 0) and removing comments
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = "Name"
        ws['B1'] = "Value"
        ws['C1'] = "Score"
        ws['A2'] = "Item A"
        ws['B2'] = 100
        # C2 is null
        ws['A3'] = "Item B"
        # B3 is null
        ws['C3'] = 200

        ws['B2'].comment = Comment("Check this", "Reviewer")
        ws['A3'].comment = Comment("Important", "Manager")

        wb.save(self.test_excel_path)
        wb.close()

        report = process_excel_guard(self.test_excel_path)

        self.assertEqual(report["comments_removed"], 2)
        self.assertEqual(report["nulls_filled_with_zero"], 2)

        wb_out = openpyxl.load_workbook(report["output_file"])
        ws_out = wb_out.active
        self.assertIsNone(ws_out['B2'].comment)
        self.assertIsNone(ws_out['A3'].comment)
        self.assertEqual(ws_out['C2'].value, 0)
        self.assertEqual(ws_out['B3'].value, 0)
        wb_out.close()

    def test_extreme_edge_case_empty_excel(self):
        # 4. Extreme edge case: empty excel file / sheet with no data
        wb = openpyxl.Workbook()
        ws = wb.active
        # No data added, but we save it
        wb.save(self.test_excel_path)
        wb.close()

        report = process_excel_guard(self.test_excel_path)

        self.assertEqual(report["comments_removed"], 0)
        # An empty workbook max_row and max_col are both 1, value is None.
        self.assertEqual(report["nulls_filled_with_zero"], 1)

        wb_out = openpyxl.load_workbook(report["output_file"])
        ws_out = wb_out.active
        self.assertEqual(ws_out['A1'].value, 0)
        wb_out.close()

    def test_output_mode_json(self):
        # 5. Output mode tests: Testing JSON output generation
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = "Name"
        ws['B1'] = "Value"
        ws['A2'] = "Item"
        # B2 is null
        ws['A2'].comment = Comment("Comment", "Author")
        wb.save(self.test_excel_path)
        wb.close()

        json_out_path = os.path.join(self.temp_dir.name, "report.json")
        report = process_excel_guard(self.test_excel_path, output_path=json_out_path, output_mode='json')

        self.assertEqual(report["comments_removed"], 1)
        self.assertEqual(report["nulls_filled_with_zero"], 1)

        self.assertTrue(os.path.exists(json_out_path))
        with open(json_out_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data["comments_removed"], 1)
            self.assertEqual(data["nulls_filled_with_zero"], 1)

    def test_default_parameters_fallback(self):
        # 3. Default parameters fallback: processing without specifying input (via main())
        # We will patch sys.argv and capture output to verify it works without throwing errors
        import sys
        from io import StringIO

        original_argv = sys.argv
        original_stdout = sys.stdout

        sys.argv = ['zero_comment_null_guard_cli_one_click.py']
        sys.stdout = StringIO()

        try:
            main()
            output = sys.stdout.getvalue()
            self.assertIn("[Auto-Fallback] No input provided", output)
            self.assertIn("Success! Report:", output)
        finally:
            sys.argv = original_argv
            sys.stdout = original_stdout

if __name__ == "__main__":
    unittest.main()

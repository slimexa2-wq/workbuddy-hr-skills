import unittest
import os
import tempfile
from openpyxl import Workbook
from openpyxl.comments import Comment
from ultra_modules.xlsx_formula_healer_export_formatter import heal_excel_report

class TestXlsxFormulaHealerExportFormatter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.input_file = os.path.join(self.test_dir.name, "test_input.xlsx")
        self.output_file = os.path.join(self.test_dir.name, "test_output.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "TestSheet"

        # 1. Normal operation with valid cells
        ws['A1'] = "Valid Text"
        ws['B1'] = 42
        ws['C1'] = 3.14

        # 2. Dirty data self-healing (error cells, #DIV/0!, NaN, string representations)
        ws['A2'] = "#REF!"
        ws['B2'] = "#DIV/0!"
        ws['C2'] = "NaN"
        ws['D2'] = "None"
        ws['E2'] = "null"

        # 3. Text number conversion
        ws['A3'] = "123"
        ws['B3'] = "456.78"
        ws['C3'] = "   999   "

        # Add comment
        comment = Comment("This is a test comment", "Author")
        ws['A1'].comment = comment

        # Add None values implicitly (empty cells) and explicitly
        ws['A4'] = None

        wb.save(self.input_file)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_normal_operation_and_repairs(self):
        # 1, 2, 3 cases merged into one comprehensive test
        stats = heal_excel_report(self.input_file, self.output_file)

        self.assertEqual(stats["status"], "success")
        self.assertEqual(stats["comments_removed"], 1)
        self.assertEqual(stats["errors_fixed"], 2)  # #REF!, #DIV/0!
        self.assertEqual(stats["nulls_replaced"], 3)  # NaN, None, null
        self.assertEqual(stats["text_numbers_converted"], 3)  # 123, 456.78, 999
        self.assertIn("【数据简报】报表已纯净导出", stats["brief_report"])

        # Verify output file
        from openpyxl import load_workbook
        wb = load_workbook(self.output_file)
        ws = wb.active

        self.assertIsNone(ws['A1'].comment)
        self.assertEqual(ws['A1'].value, "Valid Text")
        self.assertEqual(ws['B1'].value, 42)

        self.assertEqual(ws['A2'].value, 0)
        self.assertEqual(ws['B2'].value, 0)
        self.assertEqual(ws['C2'].value, 0)

        self.assertEqual(ws['A3'].value, 123)
        self.assertEqual(ws['B3'].value, 456.78)
        self.assertEqual(ws['C3'].value, 999)

    def test_default_fallback_missing_file(self):
        # 4. Default fallback on missing file
        stats = heal_excel_report("nonexistent_file.xlsx")
        self.assertEqual(stats["status"], "failed")
        self.assertEqual(stats["error_msg"], "Input file missing or path is empty.")
        self.assertIn("文件未找到", stats["brief_report"])

        stats2 = heal_excel_report("")
        self.assertEqual(stats2["status"], "failed")

    def test_default_output_path(self):
        # Test default output path logic
        stats = heal_excel_report(self.input_file)
        self.assertEqual(stats["status"], "success")
        base, ext = os.path.splitext(self.input_file)
        expected_output = f"{base}_healed{ext}"
        self.assertTrue(os.path.exists(expected_output))
        os.remove(expected_output)

    def test_exception_handling(self):
        # Test with an invalid file (not an Excel file) to trigger an exception
        bad_file = os.path.join(self.test_dir.name, "bad.xlsx")
        with open(bad_file, "w") as f:
            f.write("This is not an excel file")

        stats = heal_excel_report(bad_file)
        self.assertEqual(stats["status"], "failed")
        self.assertIn("处理失败", stats["brief_report"])

    def test_extreme_boundaries_empty_file(self):
        # 5. Extreme boundaries (empty excel file)
        empty_file = os.path.join(self.test_dir.name, "empty.xlsx")
        wb = Workbook()
        # Remove all sheets
        for sheet in wb.sheetnames:
            del wb[sheet]
        wb.create_sheet("Empty")
        wb.save(empty_file)

        stats = heal_excel_report(empty_file)
        self.assertEqual(stats["status"], "success")
        self.assertEqual(stats["cells_processed"], 0)

if __name__ == '__main__':
    unittest.main()

import unittest
import openpyxl
from openpyxl.comments import Comment
from ultra_modules.zero_comment_null_guard_core_engine import run_zero_comment_null_guard

class TestZeroCommentNullGuardCoreEngine(unittest.TestCase):

    def test_normal_usage_no_change(self):
        """Test with clean data that shouldn't be altered."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'].value = 100
        ws['B2'].value = "Valid String"

        processed_wb = run_zero_comment_null_guard(wb)
        ws_processed = processed_wb.active

        self.assertEqual(ws_processed['A1'].value, 100)
        self.assertEqual(ws_processed['B2'].value, "Valid String")
        self.assertIsNone(ws_processed['A1'].comment)

    def test_missing_params_fallback(self):
        """Test boundary: missing parameters (missing workbook or None)."""
        # passing nothing
        wb_empty = run_zero_comment_null_guard()
        self.assertIsInstance(wb_empty, openpyxl.Workbook)
        self.assertEqual(len(wb_empty.worksheets), 1)

        # passing dirty data types
        wb_dirty = run_zero_comment_null_guard("Not A Workbook")
        self.assertIsInstance(wb_dirty, openpyxl.Workbook)

    def test_dirty_data_self_healing_nulls(self):
        """Test auto-filling null and empty-like cells with default value (0)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'].value = None
        ws['A2'].value = ""
        ws['A3'].value = "   "
        ws['A4'].value = "Null"
        ws['A5'].value = " NaN "
        ws['A6'].value = "undefined"
        ws['A7'].value = "None"

        processed_wb = run_zero_comment_null_guard(wb, default_fill=0)
        ws_processed = processed_wb.active

        for i in range(1, 8):
            self.assertEqual(ws_processed[f'A{i}'].value, 0)

    def test_extreme_boundary_custom_default(self):
        """Test with extreme dirty string and a custom default fill value."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'].value = None
        ws['B1'].value = "  nUlL  "

        processed_wb = run_zero_comment_null_guard(wb, default_fill=-999)
        ws_processed = processed_wb.active

        self.assertEqual(ws_processed['A1'].value, -999)
        self.assertEqual(ws_processed['B1'].value, -999)

    def test_zero_comments_removal(self):
        """Test if comments are silently removed."""
        wb = openpyxl.Workbook()
        ws = wb.active

        ws['A1'].value = 42
        ws['A1'].comment = Comment("This is a comment", "Author")
        ws['B2'].value = "Test"
        ws['B2'].comment = Comment("Another comment", "Author2")

        self.assertIsNotNone(ws['A1'].comment)
        self.assertIsNotNone(ws['B2'].comment)

        processed_wb = run_zero_comment_null_guard(wb)
        ws_processed = processed_wb.active

        self.assertIsNone(ws_processed['A1'].comment)
        self.assertIsNone(ws_processed['B2'].comment)
        self.assertEqual(ws_processed['A1'].value, 42)
        self.assertEqual(ws_processed['B2'].value, "Test")

if __name__ == "__main__":
    unittest.main()

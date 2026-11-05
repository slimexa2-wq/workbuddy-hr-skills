import os
import unittest
import openpyxl
from openpyxl.comments import Comment

from ultra_modules.zero_comment_null_guard_self_healing_guard import ZeroCommentNullGuard

class TestZeroCommentNullGuard(unittest.TestCase):
    def setUp(self):
        self.guard = ZeroCommentNullGuard()
        self.test_file = "test_data.xlsx"

        # Create a valid excel file for normal operations
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = "Test"
        ws['A2'] = "" # Empty string
        ws['A3'] = None # None
        ws['B1'] = "With Comment"
        ws['B1'].comment = Comment("This is a comment", "Author")
        # Ensure dimensions expand enough to include A3
        ws['A4'] = "End"
        wb.save(self.test_file)

        self.corrupt_file = "corrupt_data.xlsx"
        with open(self.corrupt_file, 'w') as f:
            f.write("This is not an excel file")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.test_file + ".snapshot"):
            os.remove(self.test_file + ".snapshot")
        if os.path.exists(self.corrupt_file):
            os.remove(self.corrupt_file)
        if os.path.exists(self.corrupt_file + ".snapshot"):
            os.remove(self.corrupt_file + ".snapshot")

    def test_normal_operation(self):
        # 1. Normal operation: successful comment removal and zero-fill
        success = self.guard.process(self.test_file)
        self.assertTrue(success)

        wb = openpyxl.load_workbook(self.test_file)
        ws = wb.active

        self.assertEqual(ws['A1'].value, "Test")
        self.assertEqual(ws['A2'].value, 0)
        self.assertEqual(ws['A3'].value, 0)
        self.assertEqual(ws['B1'].value, "With Comment")
        self.assertIsNone(ws['B1'].comment)
        wb.close()

    def test_dirty_data_silent_failure(self):
        # 2. Dirty data / Corrupted file: robust silent failure
        success = self.guard.process(self.corrupt_file)
        self.assertFalse(success)

        # Self healing should revert to original state
        with open(self.corrupt_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "This is not an excel file")

    def test_missing_parameters(self):
        # 3. Missing parameters: process() and undo() handle None paths gracefully
        self.assertFalse(self.guard.process(None))
        self.assertFalse(self.guard.process())
        self.assertFalse(self.guard.undo(None))
        self.assertFalse(self.guard.undo())

    def test_extreme_boundaries(self):
        # 4. Extreme boundaries: invalid path types handle gracefully
        self.assertFalse(self.guard.process(123))
        self.assertFalse(self.guard.process([]))
        self.assertFalse(self.guard.process({}))

        self.assertFalse(self.guard.undo(123))
        self.assertFalse(self.guard.undo([]))

    def test_snapshot_undo(self):
        # 5. Snapshot & Undo verification
        # First process the file
        success = self.guard.process(self.test_file)
        self.assertTrue(success)

        # Verify changes happened
        wb = openpyxl.load_workbook(self.test_file)
        ws = wb.active
        self.assertIsNone(ws['B1'].comment)
        self.assertEqual(ws['A2'].value, 0)
        wb.close()

        # Undo
        undo_success = self.guard.undo(self.test_file)
        self.assertTrue(undo_success)

        # Verify changes were reverted
        wb = openpyxl.load_workbook(self.test_file)
        ws = wb.active
        self.assertIsNotNone(ws['B1'].comment)
        self.assertEqual(ws['A2'].value, None)
        wb.close()

if __name__ == '__main__':
    unittest.main()

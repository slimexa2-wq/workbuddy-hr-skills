import unittest
import os
import tempfile
import openpyxl
from openpyxl.comments import Comment
from ultra_modules.zero_comment_null_guard_batch_pipeline import ZeroCommentNullGuardBatchPipeline

class TestZeroCommentNullGuardBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = ZeroCommentNullGuardBatchPipeline(max_workers=2)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_files = []

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_excel(self, data, comments=None):
        wb = openpyxl.Workbook()
        ws = wb.active
        for r_idx, row in enumerate(data, 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if comments and (r_idx, c_idx) in comments:
                    cell.comment = Comment(comments[(r_idx, c_idx)], "Author")

        fd, path = tempfile.mkstemp(dir=self.temp_dir.name, suffix='.xlsx')
        os.close(fd)
        wb.save(path)
        self.temp_files.append(path)
        return path

    def test_normal_processing(self):
        """Test processing of normal valid Excel files"""
        data = [[1, 'a'], [2, 'b'], [3, 'c']]
        paths = [self._create_excel(data) for _ in range(3)]

        results = self.pipeline.process_batch(paths)

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["status"] == "success" for r in results))

        snapshot = self.pipeline.get_progress_snapshot()
        self.assertEqual(snapshot["total"], 3)
        self.assertEqual(snapshot["processed"], 3)
        self.assertEqual(snapshot["failed"], 0)

    def test_dirty_data_self_healing(self):
        """Test dirty data: removing comments and filling None with 0 in numeric columns"""
        data = [
            ["ID", "Name", "Score"],
            [1, "Alice", 95.5],
            [2, "Bob", None],  # Missing score
            [3, "Charlie", 80],
            [None, "David", 60] # Missing ID
        ]
        comments = {(2, 3): "Please check"} # Comment on Bob's missing score

        path = self._create_excel(data, comments)
        results = self.pipeline.process_batch([path])

        self.assertEqual(results[0]["status"], "success")

        wb = openpyxl.load_workbook(path)
        ws = wb.active

        # Check comments removed
        self.assertIsNone(ws.cell(row=2, column=3).comment)

        # Check nulls in numeric columns filled with 0
        # Col 1 (ID) is numeric, so row 5 col 1 should be 0
        self.assertEqual(ws.cell(row=5, column=1).value, 0)
        # Col 3 (Score) is numeric, so row 3 col 3 should be 0
        self.assertEqual(ws.cell(row=3, column=3).value, 0)

        # Check non-numeric column not affected
        # Col 2 (Name) is string, let's test a None value in a string column just in case
        data_with_str_none = [["Text"], [None], ["Val"]]
        path2 = self._create_excel(data_with_str_none)
        self.pipeline.process_batch([path2])
        wb2 = openpyxl.load_workbook(path2)
        self.assertIsNone(wb2.active.cell(row=2, column=1).value)

    def test_default_parameter_fallback(self):
        """Test missing parameters handled gracefully"""
        results = self.pipeline.process_batch()
        self.assertEqual(results, [])
        snapshot = self.pipeline.get_progress_snapshot()
        self.assertEqual(snapshot["total"], 0)

        results2 = self.pipeline.process_batch(None)
        self.assertEqual(results2, [])

    def test_empty_and_nonexistent_files(self):
        """Test edge cases with empty lists and non-existent files"""
        results = self.pipeline.process_batch(["non_existent_file.xlsx", ""])

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "failed" for r in results))

        snapshot = self.pipeline.get_progress_snapshot()
        self.assertEqual(snapshot["total"], 2)
        self.assertEqual(snapshot["processed"], 0)
        self.assertEqual(snapshot["failed"], 2)

    def test_non_numeric_columns_ignoring_empty_cells(self):
        """Test that empty cells in columns without any numeric values are NOT filled with 0"""
        data = [
            ["A", "B"],
            ["foo", "bar"],
            [None, "baz"],
            ["qux", None]
        ]
        path = self._create_excel(data)
        results = self.pipeline.process_batch([path])

        self.assertEqual(results[0]["status"], "success")

        wb = openpyxl.load_workbook(path)
        ws = wb.active

        # None values should remain None because there are no numeric values in these columns
        self.assertIsNone(ws.cell(row=3, column=1).value)
        self.assertIsNone(ws.cell(row=4, column=2).value)

if __name__ == '__main__':
    unittest.main()

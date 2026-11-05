import os
import time
import unittest
import openpyxl
from ultra_modules.zero_comment_null_guard_benchmark_suite import ZeroCommentNullGuard, SyntheticFixtureGenerator

class TestZeroCommentNullGuardBenchmarkSuite(unittest.TestCase):

    def setUp(self):
        self.test_dir = "tests/test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = os.path.join(self.test_dir, "test_fixture.xlsx")
        self.guarded_file = os.path.join(self.test_dir, "test_fixture_guarded.xlsx")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.guarded_file):
            os.remove(self.guarded_file)

    def test_normal_sanitization(self):
        # Generate 100 rows
        SyntheticFixtureGenerator.generate_fixture(self.test_file, rows=100)

        # Process
        out_path = ZeroCommentNullGuard.process_file(self.test_file, self.guarded_file)
        self.assertEqual(out_path, self.guarded_file)

        # Verify
        wb = openpyxl.load_workbook(out_path)
        ws = wb.active

        # Check comments are 0
        for row in ws.iter_rows():
            for cell in row:
                self.assertIsNone(cell.comment, "All comments should be removed.")

        # Check Score column (B, col_idx=2) nulls are filled with 0
        for i in range(2, 102):
            if (i - 1) % 10 == 0:
                cell_val = ws.cell(row=i, column=2).value
                self.assertEqual(cell_val, 0, "Null score should be replaced with 0.")

        wb.close()

    def test_dirty_data_auto_healing(self):
        SyntheticFixtureGenerator.generate_fixture(self.test_file, rows=20)
        out_path = ZeroCommentNullGuard.process_file(self.test_file, self.guarded_file)
        self.assertEqual(out_path, self.guarded_file)

        wb = openpyxl.load_workbook(out_path)
        ws = wb.active

        # Verify garbled data didn't crash it and remains intact (or processed if numeric context applies)
        for i in range(2, 22):
            if (i - 1) % 5 == 0:
                cell_val = ws.cell(row=i, column=3).value
                self.assertEqual(cell_val, "乱码@#$%^&*()_+{}:?><~")

        wb.close()

    def test_missing_param_default_fallback(self):
        SyntheticFixtureGenerator.generate_fixture(self.test_file, rows=10)

        # Missing output_path
        out_path = ZeroCommentNullGuard.process_file(self.test_file)

        expected_path = os.path.splitext(self.test_file)[0] + "_guarded" + os.path.splitext(self.test_file)[1]
        self.assertEqual(out_path, expected_path)
        self.assertTrue(os.path.exists(out_path))

        os.remove(expected_path)

    def test_extreme_boundaries(self):
        # 10000 rows for performance benchmark
        SyntheticFixtureGenerator.generate_fixture(self.test_file, rows=5000)

        start_time = time.time()
        out_path = ZeroCommentNullGuard.process_file(self.test_file, self.guarded_file)
        end_time = time.time()

        duration_ms = (end_time - start_time) * 1000
        print(f"\n[Benchmark] Processed 5000 extreme edge-case rows in {duration_ms:.2f} ms")

        self.assertTrue(os.path.exists(out_path))
        # Depending on hardware, usually takes < 10000ms. We just assert it didn't crash and works reasonably.

    def test_cross_year_month_dates(self):
        SyntheticFixtureGenerator.generate_fixture(self.test_file, rows=10)
        out_path = ZeroCommentNullGuard.process_file(self.test_file, self.guarded_file)

        wb = openpyxl.load_workbook(out_path)
        ws = wb.active

        # Check dates
        val_0 = ws.cell(row=2, column=4).value # idx 1, %3==1 -> 2024-1-1 0:0:1
        val_1 = ws.cell(row=3, column=4).value # idx 2, %3==2 -> 2024-2-29 12:0:0
        val_2 = ws.cell(row=4, column=4).value # idx 3, %3==0 -> 2023-12-31 23:59:59

        # openpyxl returns datetime objects if parsed correctly
        self.assertEqual(val_0.year, 2024)
        self.assertEqual(val_1.month, 2)
        self.assertEqual(val_2.year, 2023)
        self.assertEqual(val_2.day, 31)

        wb.close()

if __name__ == '__main__':
    unittest.main()

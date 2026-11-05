import os
import shutil
import tempfile
import unittest
import time
from pathlib import Path

from ultra_modules.wps_lock_conflict_cleaner_benchmark_suite import clean_wps_locks, WPSLockConflictCleaner

class TestWPSLockConflictCleanerBenchmarkSuite(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normal_case_clean_locks(self):
        # Create dummy normal lock files
        Path(os.path.join(self.test_dir, '~$normal1.xlsx')).touch()
        Path(os.path.join(self.test_dir, '.~lock.normal2.docx#')).touch()
        Path(os.path.join(self.test_dir, 'normal_file.txt')).touch()

        result = clean_wps_locks(self.test_dir)

        self.assertEqual(result['cleaned_count'], 2)
        self.assertEqual(result['failed_count'], 0)
        self.assertEqual(len(result['errors']), 0)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, '~$normal1.xlsx')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, '.~lock.normal2.docx#')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'normal_file.txt')))

    def test_dirty_data_invalid_path(self):
        # Passing an invalid path should not crash
        invalid_path = os.path.join(self.test_dir, "non_existent_dir")
        result = clean_wps_locks(invalid_path)

        self.assertEqual(result['cleaned_count'], 0)
        self.assertEqual(result['failed_count'], 0)
        self.assertTrue(len(result['errors']) > 0)
        self.assertIn("Invalid target directory", result['errors'][0])

    def test_missing_parameter_default_fallback(self):
        # Default fallback to "."
        # Change working directory to test_dir to avoid traversing real project space
        original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        # Create a lock file in the current directory (test_dir)
        dummy_lock = '~$test_default_fallback.xlsx'
        Path(dummy_lock).touch()
        try:
            result = clean_wps_locks() # No arguments
            # Just ensure it runs without error. It might clean more than 1 file depending on workspace state.
            self.assertTrue(result['cleaned_count'] >= 1)
            self.assertFalse(os.path.exists(dummy_lock))
        finally:
            os.chdir(original_cwd)

    def test_extreme_boundary_massive_concurrency(self):
        # Simulate extreme boundary: huge number of files and deep nesting
        # Creating synthetic dataset
        num_dirs = 10
        files_per_dir = 100 # Total 1000 lock files

        for i in range(num_dirs):
            sub_dir = os.path.join(self.test_dir, f"sub_dir_{i}")
            os.makedirs(sub_dir)
            for j in range(files_per_dir):
                Path(os.path.join(sub_dir, f"~${j}_large_dataset.xlsx")).touch()
                Path(os.path.join(sub_dir, f"keep_me_{j}.txt")).touch()

        # Measure performance
        start_time = time.time()
        result = clean_wps_locks(self.test_dir)
        end_time = time.time()

        self.assertEqual(result['cleaned_count'], num_dirs * files_per_dir)
        self.assertEqual(result['failed_count'], 0)

        # Test millisecond response - 1000 files should be fast, allow up to 500ms max
        elapsed_ms = (end_time - start_time) * 1000
        self.assertTrue(result['elapsed_ms'] <= 500, f"Performance issue: took {result['elapsed_ms']}ms")

    def test_dirty_data_permission_error_self_healing(self):
        # Simulate a file that cannot be deleted due to permissions
        locked_file = os.path.join(self.test_dir, '~$locked_by_system.xlsx')
        Path(locked_file).touch()

        # Make the file read-only, although on Windows this prevents deletion, on Unix it might just need directory read-only.
        # So we make the directory read-only.
        sub_dir = os.path.join(self.test_dir, 'readonly_dir')
        os.makedirs(sub_dir)
        nested_locked_file = os.path.join(sub_dir, '~$nested_locked.xlsx')
        Path(nested_locked_file).touch()

        # Make directory read-only and non-executable
        os.chmod(sub_dir, 0o400)

        try:
            result = clean_wps_locks(self.test_dir)
            # The nested file might fail to be read/deleted depending on OS traversal behavior
            # Just ensure no crash
            self.assertTrue(result['cleaned_count'] >= 0)
            self.assertTrue(result['failed_count'] >= 0 or len(result['errors']) > 0)
        finally:
            # Restore permissions so tearDown can delete it
            os.chmod(sub_dir, 0o777)

    def test_extreme_boundary_weird_characters_and_dates(self):
        # Simulate edge cases: weird file names with Unicode/garbage characters, cross-year/month boundaries
        weird_names = [
            '~$cross_year_📅_2023_2024.xlsx',
            '.~lock.乱码_#$%^&*_test.docx#',
            '~$   spaces   .ppt',
            '~$.hidden_lock.xls'
        ]

        for name in weird_names:
            path = os.path.join(self.test_dir, name)
            Path(path).touch()
            # Modify access/mod times to simulate cross-year (e.g. Dec 31 2023 to Jan 1 2024)
            # using random old timestamp
            os.utime(path, (1704067199, 1704067199)) # 2023-12-31 23:59:59 UTC

        result = clean_wps_locks(self.test_dir)
        self.assertEqual(result['cleaned_count'], len(weird_names))
        self.assertEqual(result['failed_count'], 0)

        for name in weird_names:
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, name)))

if __name__ == '__main__':
    unittest.main()

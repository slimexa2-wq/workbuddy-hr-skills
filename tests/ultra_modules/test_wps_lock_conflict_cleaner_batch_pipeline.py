import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ultra_modules.wps_lock_conflict_cleaner_batch_pipeline import WpsLockConflictCleanerBatchPipeline

class TestWpsLockConflictCleanerBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.pipeline = WpsLockConflictCleanerBatchPipeline()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_1_normal_directory_with_lock_files(self):
        """Case 1: Normal directory with lock files (cleaned)."""
        # Create normal files and lock files
        normal_file = os.path.join(self.test_dir, "normal.xlsx")
        lock_file1 = os.path.join(self.test_dir, ".~lock.normal.xlsx#")
        lock_file2 = os.path.join(self.test_dir, "~$normal.xlsx")

        with open(normal_file, 'w') as f: f.write("data")
        with open(lock_file1, 'w') as f: f.write("lock")
        with open(lock_file2, 'w') as f: f.write("lock")

        self.assertTrue(os.path.exists(lock_file1))
        self.assertTrue(os.path.exists(lock_file2))

        result = self.pipeline.run([self.test_dir])

        self.assertEqual(result['total_processed_paths'], 1)
        self.assertEqual(result['total_deleted'], 2)
        self.assertFalse(os.path.exists(lock_file1))
        self.assertFalse(os.path.exists(lock_file2))
        self.assertTrue(os.path.exists(normal_file)) # normal file untouched

    def test_2_directory_with_normal_files_ignored(self):
        """Case 2: Directory with normal files (untouched/ignored)."""
        normal_file1 = os.path.join(self.test_dir, "file1.txt")
        normal_file2 = os.path.join(self.test_dir, "document.docx")

        with open(normal_file1, 'w') as f: f.write("text")
        with open(normal_file2, 'w') as f: f.write("doc")

        result = self.pipeline.run([self.test_dir])

        self.assertEqual(result['total_deleted'], 0)
        self.assertEqual(len(result['deleted_files']), 0)
        self.assertTrue(os.path.exists(normal_file1))
        self.assertTrue(os.path.exists(normal_file2))

    def test_3_dirty_data_self_healing(self):
        """Case 3: Dirty data self-healing (handle None, mixed types, empty strings)."""
        # Should gracefully ignore dirty data
        dirty_paths = [
            None,
            123,
            "",
            "   ",
            {"not": "string"},
            self.test_dir
        ]

        lock_file = os.path.join(self.test_dir, "~$dirty.xlsx")
        with open(lock_file, 'w') as f: f.write("lock")

        result = self.pipeline.run(dirty_paths)

        self.assertEqual(result['total_processed_paths'], 1) # Only self.test_dir should be processed
        self.assertEqual(result['total_deleted'], 1)
        self.assertFalse(os.path.exists(lock_file))

    def test_4_default_fallback(self):
        """Case 4: Default fallback (missing parameter)."""
        # Call with no args or None should not raise exception
        result_none = self.pipeline.run(None)
        result_empty = self.pipeline.run()

        self.assertEqual(result_none['total_processed_paths'], 0)
        self.assertEqual(result_none['total_deleted'], 0)
        self.assertEqual(result_empty['total_processed_paths'], 0)
        self.assertEqual(result_empty['total_deleted'], 0)

        # Test passing string instead of list
        lock_file = os.path.join(self.test_dir, "~$single.xlsx")
        with open(lock_file, 'w') as f: f.write("lock")

        result_str = self.pipeline.run(self.test_dir)
        self.assertEqual(result_str['total_processed_paths'], 1)
        self.assertEqual(result_str['total_deleted'], 1)

    @patch('os.remove')
    def test_5_extreme_boundaries(self, mock_remove):
        """Case 5: Extreme boundaries (mock permission denied / stress test)."""
        # 1. Mock permission denied error
        mock_remove.side_effect = PermissionError("Permission Denied")
        lock_file = os.path.join(self.test_dir, "~$denied.xlsx")
        with open(lock_file, 'w') as f: f.write("lock")

        result_error = self.pipeline.run([self.test_dir])
        self.assertEqual(result_error['total_deleted'], 0)
        self.assertEqual(len(result_error['errors']), 1)
        self.assertIn("Permission Denied", result_error['errors'][0])

        # 2. Stress test - 1000 files (remove mock to test actual pipeline)
        mock_remove.side_effect = None
        stress_dir = os.path.join(self.test_dir, "stress")
        os.makedirs(stress_dir)

        for i in range(1000):
            with open(os.path.join(stress_dir, f"~$stress_{i}.xlsx"), 'w') as f:
                f.write("lock")

        result_stress = self.pipeline.run([stress_dir])
        self.assertEqual(result_stress['total_processed_paths'], 1)
        self.assertEqual(result_stress['total_deleted'], 1000)

if __name__ == '__main__':
    unittest.main()

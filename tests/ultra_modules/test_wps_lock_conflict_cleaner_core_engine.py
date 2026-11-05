import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from ultra_modules.wps_lock_conflict_cleaner_core_engine import clean_wps_lock_conflicts

class TestWPSLockCleaner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_normal_removal(self):
        # Create normal files and lock files
        os.makedirs(os.path.join(self.test_dir, "subdir"))
        lock1 = os.path.join(self.test_dir, ".~lock.file1.docx#")
        lock2 = os.path.join(self.test_dir, "subdir", "~$file2.xlsx")
        normal1 = os.path.join(self.test_dir, "normal.txt")

        for f in [lock1, lock2, normal1]:
            with open(f, "w") as fp:
                fp.write("test")

        result = clean_wps_lock_conflicts(self.test_dir)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed"]), 2)
        self.assertIn(lock1, result["removed"])
        self.assertIn(lock2, result["removed"])

        self.assertFalse(os.path.exists(lock1))
        self.assertFalse(os.path.exists(lock2))
        self.assertTrue(os.path.exists(normal1))

    def test_missing_argument_fallback(self):
        # When no argument is provided, should default to "."
        # We mock os.path.abspath to return test_dir to avoid deleting real files
        with patch('os.path.abspath', return_value=self.test_dir):
            lock1 = os.path.join(self.test_dir, ".~lock.test#")
            with open(lock1, "w") as fp:
                fp.write("test")

            result = clean_wps_lock_conflicts()

            self.assertEqual(len(result["removed"]), 1)
            self.assertFalse(os.path.exists(lock1))

    def test_dirty_data_handling(self):
        # Test with integers, None, objects
        with patch('os.path.abspath', return_value=self.test_dir):
            lock1 = os.path.join(self.test_dir, "~$test.xlsx")
            with open(lock1, "w") as fp:
                fp.write("test")

            # Dirty data: integer 12345
            result = clean_wps_lock_conflicts(12345)
            # It will fail parsing 12345 as valid directory, fallback to "." (mocked as test_dir)
            self.assertEqual(len(result["removed"]), 1)
            self.assertFalse(os.path.exists(lock1))

    def test_invalid_directory(self):
        # Non-existent directory should not crash
        invalid_dir = os.path.join(self.test_dir, "nonexistent")
        result = clean_wps_lock_conflicts(invalid_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed"]), 0)
        self.assertIn("Invalid or non-existent directory", result["errors"])

    def test_permission_denied_auto_fix(self):
        # File without write permission
        lock1 = os.path.join(self.test_dir, ".~lock.nopermission#")
        with open(lock1, "w") as fp:
            fp.write("test")

        # Make read-only
        os.chmod(lock1, 0o444)

        result = clean_wps_lock_conflicts(self.test_dir)

        self.assertEqual(len(result["removed"]), 1)
        self.assertIn(lock1, result["removed"])
        self.assertFalse(os.path.exists(lock1))

if __name__ == '__main__':
    unittest.main()

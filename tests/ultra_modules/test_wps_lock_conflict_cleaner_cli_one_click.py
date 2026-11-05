import os
import shutil
import tempfile
import unittest
import json
from unittest.mock import patch
from ultra_modules.wps_lock_conflict_cleaner_cli_one_click import detect_and_clean_locks, json_excel_adapter

class TestWPSLockConflictCleaner(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for safe testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def _create_file(self, filename, content=""):
        path = os.path.join(self.test_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_normal_operation_removes_locks(self):
        """Test that .~lock and ~$ files are correctly identified and removed."""
        lock_file1 = self._create_file(".~lock.data.xlsx#")
        lock_file2 = self._create_file("~$report.docx")
        normal_file = self._create_file("regular_file.txt")

        result = detect_and_clean_locks(self.test_dir)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["removed_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertFalse(os.path.exists(lock_file1))
        self.assertFalse(os.path.exists(lock_file2))
        self.assertTrue(os.path.exists(normal_file))

        # Ensure filenames are correctly reported
        self.assertIn(lock_file1, result["removed_files"])
        self.assertIn(lock_file2, result["removed_files"])

    def test_dirty_data_self_healing_and_fallback(self):
        """Test behavior with invalid directory parameter (dirty data/fallback)."""
        # Pass a non-existent directory; the function should fallback to "."
        with patch('os.path.exists', return_value=False):
            result = detect_and_clean_locks("invalid_dir/path")
            self.assertEqual(result["target_dir"], ".")

        # Pass a non-string type (int)
        result = detect_and_clean_locks(12345)
        self.assertEqual(result["target_dir"], ".")

    def test_default_parameter_fallback(self):
        """Test behavior with default missing parameters."""
        # Test default parameter target_dir
        with patch('os.walk', return_value=[]):
            result = detect_and_clean_locks()
            self.assertEqual(result["target_dir"], ".")
            self.assertEqual(result["removed_count"], 0)

        # Test adapter default formatting (json)
        res_data = {"status": "success", "target_dir": "test", "removed_count": 0, "failed_count": 0}
        out = json_excel_adapter(res_data) # no output_format specified
        self.assertTrue(out.startswith("{")) # JSON output

        out_invalid = json_excel_adapter(res_data, output_format=123) # invalid type
        self.assertTrue(out_invalid.startswith("{")) # falls back to json

    def test_extreme_boundary_permission_error(self):
        """Test extreme boundary where file cannot be removed due to permissions."""
        lock_file = self._create_file(".~lock.restricted.xlsx#")

        # Mock os.remove to raise PermissionError for this test
        with patch('os.remove', side_effect=PermissionError("Access Denied")):
            result = detect_and_clean_locks(self.test_dir)

            self.assertEqual(result["removed_count"], 0)
            self.assertEqual(result["failed_count"], 1)
            self.assertIn(lock_file, result["failed_files"])

    def test_adapter_excel_output(self):
        """Test that the adapter can output simulated excel/text summaries."""
        res_data = {
            "status": "success",
            "target_dir": "/tmp/test",
            "removed_count": 1,
            "failed_count": 1,
            "removed_files": ["/tmp/test/.~lock.a.xlsx#"],
            "failed_files": ["/tmp/test/~$b.xlsx"]
        }
        out = json_excel_adapter(res_data, output_format="excel")
        self.assertIn("--- Excel Summary ---", out)
        self.assertIn("Target Directory: /tmp/test", out)
        self.assertIn("Removed Count: 1", out)
        self.assertIn("Failed Count: 1", out)
        self.assertIn("- /tmp/test/.~lock.a.xlsx#", out)
        self.assertIn("- /tmp/test/~$b.xlsx", out)

if __name__ == '__main__':
    unittest.main()

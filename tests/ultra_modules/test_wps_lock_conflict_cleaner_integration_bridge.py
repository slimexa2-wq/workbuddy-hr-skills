import unittest
import os
import tempfile
import shutil
from ultra_modules.wps_lock_conflict_cleaner_integration_bridge import clean_lock_files, bridge_schema

class TestWPSLockCleanerBridge(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_clean_lock_files_normal(self):
        """Test normal operation: removing WPS and Excel lock files."""
        # Create dummy lock files
        wps_lock = os.path.join(self.test_dir, ".~lock.document.docx#")
        excel_lock = os.path.join(self.test_dir, "~$spreadsheet.xlsx")
        normal_file = os.path.join(self.test_dir, "document.docx")

        for f in [wps_lock, excel_lock, normal_file]:
            with open(f, 'w') as fh:
                fh.write("test")

        result = clean_lock_files(self.test_dir)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["cleaned"]), 2)
        self.assertIn(".~lock.document.docx#", result["cleaned"])
        self.assertIn("~$spreadsheet.xlsx", result["cleaned"])

        # Verify normal file still exists
        self.assertTrue(os.path.exists(normal_file))
        # Verify lock files are gone
        self.assertFalse(os.path.exists(wps_lock))
        self.assertFalse(os.path.exists(excel_lock))

    def test_clean_lock_files_dirty_data(self):
        """Test dirty data: missing parameter and invalid directory."""
        # Test with empty string / None equivalent behavior
        result = clean_lock_files("")
        # Empty string defaults to ".", so it should succeed but clean nothing (or something in current dir)
        self.assertEqual(result["status"], "success")

        # Test with non-existent directory
        result_non_existent = clean_lock_files(os.path.join(self.test_dir, "non_existent"))
        self.assertEqual(result_non_existent["status"], "error")
        self.assertEqual(result_non_existent["message"], "Directory does not exist.")

    def test_clean_lock_files_extreme_boundaries(self):
        """Test extreme boundaries: permission denied (simulated) or OS error."""
        # Create a file that can't be deleted (read-only directory)
        sub_dir = os.path.join(self.test_dir, "restricted")
        os.mkdir(sub_dir)
        lock_file = os.path.join(sub_dir, ".~lock.test#")
        excel_lock_file = os.path.join(sub_dir, "~$test.xlsx")

        with open(lock_file, 'w') as f:
            f.write("test")

        with open(excel_lock_file, 'w') as f:
            f.write("test")

        from unittest.mock import patch

        # Mock os.remove to raise exception to hit lines 32-33 and 39-40
        with patch("os.remove", side_effect=Exception("Mock Exception")):
            result = clean_lock_files(sub_dir)
            self.assertEqual(result["status"], "success")
            # Should have handled it silently and caught exception, returning what it could (nothing cleaned)
            self.assertEqual(result["cleaned"], [])

        # Let's also make the directory unreadable to hit os.listdir exception
        os.chmod(sub_dir, 0o000)
        try:
            result = clean_lock_files(sub_dir)
            self.assertEqual(result["status"], "error")
        finally:
            os.chmod(sub_dir, 0o755) # Restore permissions for tearDown

    def test_bridge_schema_normal(self):
        """Test normal schema bridging with exact and fuzzy matching."""
        source = {
            "userName": "Alice",
            "age": 30,
            "department_id": "HR",
            "RandomField": "Ignored"
        }
        target = ["user_name", "Age", "random", "salary"]

        result = bridge_schema(source, target)

        # userName -> user_name (fuzzy match)
        self.assertEqual(result["user_name"], "Alice")
        # age -> Age (exact match case insensitive)
        self.assertEqual(result["Age"], 30)
        # "randomfield" -> "random" (substring match)
        self.assertEqual(result["random"], "Ignored")
        # salary -> not found (default None)
        self.assertIsNone(result["salary"])

    def test_bridge_schema_dirty_data(self):
        """Test dirty data: invalid source, empty target, etc."""
        # Invalid source (not dict)
        self.assertEqual(bridge_schema(["invalid_list"], ["target"]), {})

        # Missing/Empty target schema (returns copy of source)
        source = {"a": 1}
        self.assertEqual(bridge_schema(source, None), source)
        self.assertEqual(bridge_schema(source, []), source)

        # Empty source
        self.assertEqual(bridge_schema({}, ["target"]), {"target": None})

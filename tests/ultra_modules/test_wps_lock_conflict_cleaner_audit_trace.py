import unittest
import os
import shutil
import tempfile
from typing import Dict, Any

from ultra_modules.wps_lock_conflict_cleaner_audit_trace import clean_wps_locks

class TestWPSLockConflictCleanerAuditTrace(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_normal_lock_removal(self):
        # Setup: Create some normal files and lock files
        os.makedirs("project")

        with open("project/normal.xlsx", "w") as f:
            f.write("data")
        with open("project/.~lock.normal.xlsx#", "w") as f:
            f.write("lock")
        with open("project/~$temp.xlsx", "w") as f:
            f.write("temp")

        result = clean_wps_locks("project")

        # Verify
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed_files"]), 2)

        # Check audit trace
        audit = result["audit"]
        self.assertTrue(len(audit["trace"]) > 0)

        # Check actual files on disk
        self.assertTrue(os.path.exists("project/normal.xlsx"))
        self.assertFalse(os.path.exists("project/.~lock.normal.xlsx#"))
        self.assertFalse(os.path.exists("project/~$temp.xlsx"))

    def test_missing_parameter_default_fallback(self):
        # Setup: Create lock file in current directory (which is temp_dir now)
        with open("~$current_dir.xlsx", "w") as f:
            f.write("temp")

        result = clean_wps_locks() # No parameter provided

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed_files"]), 1)
        self.assertTrue(result["removed_files"][0].endswith("~$current_dir.xlsx"))
        self.assertFalse(os.path.exists("~$current_dir.xlsx"))

    def test_dirty_data_self_healing_non_existent_dir(self):
        result = clean_wps_locks("non_existent_directory_12345")

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed_files"]), 0)

        audit_trace = result["audit"]["trace"]
        self.assertEqual(audit_trace[0]["action"], "self_heal_non_existent_dir")

    def test_dirty_data_self_healing_file_instead_of_dir(self):
        with open("just_a_file.txt", "w") as f:
            f.write("hello")

        result = clean_wps_locks("just_a_file.txt")

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed_files"]), 0)

        audit_trace = result["audit"]["trace"]
        self.assertEqual(audit_trace[0]["action"], "self_heal_not_a_dir")

    def test_extreme_boundary_deeply_nested_paths(self):
        nested_dir = os.path.join("a", "b", "c", "d", "e")
        os.makedirs(nested_dir)

        with open(os.path.join(nested_dir, ".~lock.deep.xlsx#"), "w") as f:
            f.write("lock")

        with open(os.path.join(nested_dir, "normal.txt"), "w") as f:
            f.write("txt")

        result = clean_wps_locks("a")

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["removed_files"]), 1)
        self.assertTrue(result["removed_files"][0].endswith(".~lock.deep.xlsx#"))

        self.assertFalse(os.path.exists(os.path.join(nested_dir, ".~lock.deep.xlsx#")))
        self.assertTrue(os.path.exists(os.path.join(nested_dir, "normal.txt")))

if __name__ == "__main__":
    unittest.main()

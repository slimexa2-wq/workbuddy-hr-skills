import unittest
import tempfile
import os
import time
from ultra_modules.wps_lock_conflict_cleaner_anomaly_radar import scan_and_clean_anomalies

class TestWPSLockConflictCleanerAnomalyRadar(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.target_dir = self.test_dir.name

    def tearDown(self):
        self.test_dir.cleanup()

    def create_mock_lock_file(self, filename, mtime=None):
        filepath = os.path.join(self.target_dir, filename)
        with open(filepath, 'w') as f:
            f.write("mock lock data")
        if mtime is not None:
            os.utime(filepath, (mtime, mtime))
        return filepath

    def test_normal_execution_and_auto_clean(self):
        """Test normal lock files are scanned and cleaned automatically (Green)."""
        now = time.time()
        # Normal recent files
        self.create_mock_lock_file(".~lock.file1.docx#", mtime=now - 10)
        self.create_mock_lock_file("~$file2.xlsx", mtime=now - 20)

        result = scan_and_clean_anomalies(target_dir=self.target_dir, auto_clean=True, test_mode=False)

        self.assertEqual(result["total_scanned"], 2)
        self.assertEqual(len(result["green_normals"]), 2)
        self.assertEqual(len(result["yellow_warnings"]), 0)
        self.assertEqual(len(result["red_anomalies"]), 0)
        self.assertEqual(result["cleaned_count"], 2)

        # Verify files were actually deleted
        files_left = os.listdir(self.target_dir)
        self.assertEqual(len(files_left), 0)

    def test_dirty_data_fallback_and_missing_params(self):
        """Test silent self-healing for dirty data (invalid target_dir, auto_clean types) and missing parameters."""
        # This will use the current directory '.' as fallback, so we test test_mode=True to not actually delete real '.' files
        result = scan_and_clean_anomalies(target_dir=12345, auto_clean="yes", test_mode=True)
        self.assertIn("total_scanned", result)
        self.assertIsInstance(result["cleaned_count"], int)

        # Another case with explicit None
        result2 = scan_and_clean_anomalies(target_dir=None)
        self.assertIn("total_scanned", result2)

    def test_anomaly_detection_top_3_percent_and_zscore(self):
        """Test detection of extreme anomalies using Z-score/IQR/Top 3% logic."""
        now = time.time()

        # Create many normal files
        for i in range(100):
            self.create_mock_lock_file(f".~lock.normal{i}.docx#", mtime=now - 60) # 1 min ago

        # Create 1 extreme anomaly (Red)
        self.create_mock_lock_file(".~lock.extreme.docx#", mtime=now - 86400 * 30) # 30 days ago

        # Create 1 minor anomaly (Yellow)
        self.create_mock_lock_file(".~lock.minor.docx#", mtime=now - 3600 * 2) # 2 hours ago

        result = scan_and_clean_anomalies(target_dir=self.target_dir, auto_clean=False, test_mode=True)

        self.assertEqual(result["total_scanned"], 102)

        # Top 3% of 102 is 4, but we only have 1 extreme and 1 minor. The extreme should be Red.
        self.assertTrue(len(result["red_anomalies"]) >= 1)
        self.assertEqual(result["red_anomalies"][0]["filename"], ".~lock.extreme.docx#")
        self.assertEqual(result["red_anomalies"][0]["color"], "Red")
        self.assertIn("人工看一眼确认", result["red_anomalies"][0]["reason"])

        # The minor anomaly should probably be Yellow
        self.assertTrue(any(f["filename"] == ".~lock.minor.docx#" for f in result["yellow_warnings"] + result["red_anomalies"]))

        # 97% are cleaned (Yellow and Green)
        # 102 total - len(red) should be cleaned_count in test_mode
        self.assertEqual(result["cleaned_count"], result["total_scanned"] - len(result["red_anomalies"]))

    def test_extreme_edge_cases_future_files(self):
        """Test extreme boundary cases like files from the 'future' (negative age) and empty directories."""
        now = time.time()
        # File from the future
        self.create_mock_lock_file(".~lock.future.docx#", mtime=now + 86400)

        result = scan_and_clean_anomalies(target_dir=self.target_dir, test_mode=True)

        self.assertEqual(result["total_scanned"], 1)
        self.assertEqual(result["green_normals"][0]["age"], 0) # Should fallback to 0 age

        # Empty directory
        empty_dir = tempfile.TemporaryDirectory()
        result_empty = scan_and_clean_anomalies(target_dir=empty_dir.name, test_mode=True)
        self.assertEqual(result_empty["total_scanned"], 0)
        self.assertEqual(result_empty["cleaned_count"], 0)
        self.assertEqual(result_empty["red_anomalies"], [])
        empty_dir.cleanup()

    def test_small_sample_size_no_false_positives(self):
        """Test small sample sizes (< 10) to ensure we don't flag normal files as Red incorrectly."""
        now = time.time()
        # Just 2 files with slight age difference, neither is extreme
        self.create_mock_lock_file(".~lock.file1.docx#", mtime=now - 10)
        self.create_mock_lock_file(".~lock.file2.docx#", mtime=now - 60)

        result = scan_and_clean_anomalies(target_dir=self.target_dir, test_mode=True)

        self.assertEqual(result["total_scanned"], 2)
        # Should not have any red anomalies
        self.assertEqual(len(result["red_anomalies"]), 0)
        self.assertEqual(result["cleaned_count"], 2)

if __name__ == '__main__':
    unittest.main()

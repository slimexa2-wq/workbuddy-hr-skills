import os
import glob
import unittest
from unittest.mock import patch
import math
from ultra_modules.wps_lock_conflict_cleaner_export_formatter import clean_and_format_export

class TestWpsLockConflictCleanerExportFormatter(unittest.TestCase):

    def setUp(self):
        # Create some dummy lock files for testing if needed
        self.test_dir = 'test_wps_cleaner_dir'
        os.makedirs(self.test_dir, exist_ok=True)
        open(os.path.join(self.test_dir, '.~lock.test.xlsx#'), 'w').close()
        open(os.path.join(self.test_dir, '~$test2.xlsx'), 'w').close()

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_dir):
            for f in glob.glob(os.path.join(self.test_dir, '*')):
                os.remove(f)
            for f in glob.glob(os.path.join(self.test_dir, '.~lock.*')):
                os.remove(f)
            os.rmdir(self.test_dir)

    def test_normal_operation(self):
        """Test normal operation with valid directory and data."""
        data = [
            {'id': 1, 'value': 100, 'comments': 'some comment'},
            {'id': 2, 'value': 200, 'comments': 5}
        ]
        result = clean_and_format_export(target_dir=self.test_dir, export_data=data)

        self.assertEqual(len(result['data']), 2)
        self.assertEqual(result['data'][0]['comments'], 0)
        self.assertEqual(result['data'][1]['comments'], 0)

        # Verify 3-line summary
        summary_lines = result['summary'].split('\n')
        self.assertEqual(len(summary_lines), 3)
        self.assertIn('成功清理 2 个隐藏锁文件', result['summary'])
        self.assertIn('净化 2 条无损记录', result['summary'])

        # Verify lock files deleted
        self.assertEqual(len(glob.glob(os.path.join(self.test_dir, '.~lock.*'))), 0)
        self.assertEqual(len(glob.glob(os.path.join(self.test_dir, '~$*'))), 0)

    def test_dirty_data_self_healing(self):
        """Test dirty data like NaN, None, invalid rows."""
        data = [
            {'id': 1, 'value': float('nan')},
            {'id': 2, 'value': None},
            "invalid_row_string",
            {'id': 3, 'comments': None, 'other': 'test'}
        ]
        result = clean_and_format_export(target_dir=self.test_dir, export_data=data)

        self.assertEqual(len(result['data']), 3) # "invalid_row_string" is skipped

        # NaN replaced with 0
        self.assertEqual(result['data'][0]['value'], 0)
        self.assertEqual(result['data'][0]['comments'], 0)

        # None replaced with 0
        self.assertEqual(result['data'][1]['value'], 0)
        self.assertEqual(result['data'][1]['comments'], 0)

        # comments replaced with 0
        self.assertEqual(result['data'][2]['comments'], 0)

    def test_missing_parameters_fallback(self):
        """Test missing parameters fallback (None inputs)."""
        result = clean_and_format_export(target_dir=None, export_data=None)
        self.assertEqual(len(result['data']), 0)
        self.assertIn('成功清理', result['summary'])

        # Also test non-list export_data
        result2 = clean_and_format_export(target_dir='.', export_data="not_a_list")
        self.assertEqual(len(result2['data']), 0)

    @patch('os.remove')
    def test_delete_exception_handling(self, mock_remove):
        """Test boundary condition: os.remove throws exception (permission denied)."""
        mock_remove.side_effect = PermissionError("Permission denied")

        # Call function, should not crash
        result = clean_and_format_export(target_dir=self.test_dir, export_data=[{}])

        self.assertEqual(len(result['data']), 1)
        self.assertEqual(result['data'][0]['comments'], 0)
        # 0 files deleted because it throws exception
        self.assertIn('成功清理 0 个隐藏锁文件', result['summary'])

        # Clean up manually since os.remove was mocked and failed to remove test files
        mock_remove.side_effect = None

    @patch('glob.glob')
    def test_glob_exception_handling(self, mock_glob):
        """Test boundary condition: glob throws exception or target_dir is invalid type."""
        # Force glob to throw an exception to simulate directory read errors
        mock_glob.side_effect = Exception("Read error")

        result = clean_and_format_export(target_dir=self.test_dir, export_data=[{'a': 1}])
        self.assertEqual(len(result['data']), 1)
        self.assertIn('成功清理 0 个隐藏锁文件', result['summary'])

if __name__ == '__main__':
    unittest.main()

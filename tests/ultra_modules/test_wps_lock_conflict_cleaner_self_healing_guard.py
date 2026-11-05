import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ultra_modules.wps_lock_conflict_cleaner_self_healing_guard import (
    WpsLockConflictCleanerSelfHealingGuard,
    clean_locks,
    undo_clean
)

class TestWpsLockConflictCleanerSelfHealingGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.snapshot_dir = Path(tempfile.mkdtemp())
        self.guard = WpsLockConflictCleanerSelfHealingGuard(self.snapshot_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.snapshot_dir, ignore_errors=True)
        # Try cleaning up default snapshots if created
        shutil.rmtree(Path.cwd() / ".wps_cleaner_snapshots", ignore_errors=True)

    def test_normal_operation(self):
        """Test finding and removing WPS/Excel lock files."""
        # Create normal files and lock files
        (self.test_dir / "normal.xlsx").touch()
        (self.test_dir / "~$lockfile.xlsx").touch()
        (self.test_dir / ".~lock.another.xlsx#").touch()

        # Add nested
        nested_dir = self.test_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "~$nested.xlsx").touch()

        snapshot_id = self.guard.clean(self.test_dir)

        self.assertTrue((self.test_dir / "normal.xlsx").exists())
        self.assertFalse((self.test_dir / "~$lockfile.xlsx").exists())
        self.assertFalse((self.test_dir / ".~lock.another.xlsx#").exists())
        self.assertFalse((nested_dir / "~$nested.xlsx").exists())

        # Verify snapshot exists
        self.assertTrue((self.snapshot_dir / snapshot_id / "manifest.json").exists())

    def test_undo_feature(self):
        """Test undoing a cleaning operation and restoring files."""
        (self.test_dir / "~$temp.xlsx").touch()
        snapshot_id = self.guard.clean(self.test_dir)
        self.assertFalse((self.test_dir / "~$temp.xlsx").exists())

        result = self.guard.undo(snapshot_id)
        self.assertTrue(result)
        self.assertTrue((self.test_dir / "~$temp.xlsx").exists())
        # Verify snapshot dir was cleaned up
        self.assertFalse((self.snapshot_dir / snapshot_id).exists())

    def test_dirty_data_missing_parameters(self):
        """Test passing invalid parameters and default fallbacks."""
        # Testing zero-config global functions with bad types
        snapshot_id = clean_locks(12345) # Should fallback to cwd silently
        self.assertIsInstance(snapshot_id, str)

        result = undo_clean(None)
        self.assertFalse(result)

        # Init with None and invalid path should fallback to a safe dir
        bad_guard = WpsLockConflictCleanerSelfHealingGuard(None)
        self.assertIsNotNone(bad_guard.snapshot_dir)

        bad_guard2 = WpsLockConflictCleanerSelfHealingGuard({"bad": "dict"})
        self.assertIsNotNone(bad_guard2.snapshot_dir)

    def test_empty_directory_handling(self):
        """Test running against an empty directory or directory with no locks."""
        # Empty dir
        snapshot_id = self.guard.clean(self.test_dir)
        self.assertIsInstance(snapshot_id, str)

        # Dir with only normal files
        (self.test_dir / "normal.txt").touch()
        snapshot_id = self.guard.clean(self.test_dir)
        self.assertIsInstance(snapshot_id, str)
        self.assertTrue((self.test_dir / "normal.txt").exists())
        # Should not create snapshot manifest if no files were backed up
        self.assertFalse((self.snapshot_dir / snapshot_id / "manifest.json").exists())

    def test_unwritable_snapshot_directory_fault_tolerance(self):
        """Test that failure to write to a snapshot directory is silently ignored."""
        unwritable_dir = self.test_dir / "unwritable"
        unwritable_dir.mkdir()
        try:
            unwritable_dir.chmod(0o444) # Read-only
        except Exception:
            pass # ignore on platforms where chmod doesn't work well

        guard = WpsLockConflictCleanerSelfHealingGuard(unwritable_dir)

        target_dir = self.test_dir / "target"
        target_dir.mkdir()
        (target_dir / "~$locked.xlsx").touch()

        # Should complete silently without raising exceptions
        snapshot_id = guard.clean(target_dir)
        self.assertIsInstance(snapshot_id, str)

if __name__ == '__main__':
    unittest.main()

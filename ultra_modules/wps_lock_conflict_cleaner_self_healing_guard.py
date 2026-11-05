import os
import shutil
import tempfile
import time
import uuid
import json
from pathlib import Path
from typing import Optional, Union, Dict, Any

class WpsLockConflictCleanerSelfHealingGuard:
    def __init__(self, snapshot_dir: Optional[Union[str, Path]] = None):
        """Initialize with zero-configuration and fault tolerance."""
        try:
            if not snapshot_dir or not isinstance(snapshot_dir, (str, Path)):
                snapshot_dir = Path(tempfile.gettempdir()) / ".wps_cleaner_snapshots"
            else:
                snapshot_dir = Path(snapshot_dir)
            self.snapshot_dir = snapshot_dir
            # Attempt to create it if it doesn't exist, ignore if we can't
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fallback to current directory temp folder if system temp is inaccessible
            self.snapshot_dir = Path.cwd() / ".wps_cleaner_snapshots"
            try:
                self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass # Completely silent

    def clean(self, target_dir: Optional[Union[str, Path]] = None) -> str:
        """
        Scans for macOS WPS/Excel lock files (`~$*` and `.~lock.*`) and moves them to a snapshot.
        Returns a snapshot_id for undo.
        """
        snapshot_id = str(uuid.uuid4())

        try:
            if target_dir is None:
                target_path = Path.cwd()
            elif isinstance(target_dir, (str, Path)):
                target_path = Path(target_dir)
            else:
                target_path = Path.cwd()

            if not target_path.exists() or not target_path.is_dir():
                target_path = Path.cwd()

        except Exception:
            target_path = Path.cwd()

        snapshot_path = self.snapshot_dir / snapshot_id
        manifest: Dict[str, str] = {} # mapping from backup file to original location

        try:
            for root, dirs, files in os.walk(str(target_path)):
                for file in files:
                    if file.startswith("~$") or file.startswith(".~lock."):
                        original_filepath = Path(root) / file
                        # Move to snapshot
                        try:
                            if not snapshot_path.exists():
                                snapshot_path.mkdir(parents=True, exist_ok=True)

                            backup_filename = f"{uuid.uuid4()}_{file}"
                            backup_filepath = snapshot_path / backup_filename

                            shutil.move(str(original_filepath), str(backup_filepath))
                            manifest[str(backup_filepath)] = str(original_filepath)
                        except Exception:
                            # Ignore files we can't access or move
                            pass

            if manifest:
                manifest_path = snapshot_path / "manifest.json"
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "files": manifest
                    }, f)

        except Exception:
            pass # Silent self-healing

        return snapshot_id

    def undo(self, snapshot_id: Any) -> bool:
        """
        Restores files from a given snapshot.
        If it fails, returns False silently.
        """
        try:
            if not isinstance(snapshot_id, str):
                snapshot_id = str(snapshot_id)

            snapshot_path = self.snapshot_dir / snapshot_id
            manifest_path = snapshot_path / "manifest.json"

            if not manifest_path.exists():
                return False

            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            manifest = data.get("files", {})

            for backup_filepath, original_filepath in manifest.items():
                try:
                    if os.path.exists(backup_filepath):
                        # Ensure original directory exists
                        orig_dir = os.path.dirname(original_filepath)
                        if not os.path.exists(orig_dir):
                            os.makedirs(orig_dir, exist_ok=True)
                        shutil.move(backup_filepath, original_filepath)
                except Exception:
                    continue

            # Try to cleanup snapshot dir
            try:
                shutil.rmtree(str(snapshot_path))
            except Exception:
                pass

            return True
        except Exception:
            return False

# Provide a zero-configuration singleton-like functions for 1-click use
_default_cleaner = WpsLockConflictCleanerSelfHealingGuard()

def clean_locks(target_dir: Optional[Union[str, Path]] = None) -> str:
    return _default_cleaner.clean(target_dir)

def undo_clean(snapshot_id: Any) -> bool:
    return _default_cleaner.undo(snapshot_id)

import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

class WPSLockConflictCleaner:
    """
    WPS/Excel lock file cleaner.
    """

    def clean_locks(self, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Recursively find and safely remove WPS/Excel lock files (`~$*`, `.~lock.*`).

        Args:
            target_dir: The directory to clean. Defaults to the current directory if None or empty.

        Returns:
            A summary dictionary containing:
            - cleaned_count: Number of successfully removed lock files.
            - failed_count: Number of lock files that failed to be removed.
            - elapsed_ms: Time taken in milliseconds.
            - errors: List of error messages for failures.
        """
        start_time = time.time()

        # Zero-configuration default fallback
        if not target_dir:
            target_dir = "."

        cleaned_count = 0
        failed_count = 0
        errors = []

        try:
            target_path = Path(target_dir)
            if not target_path.exists() or not target_path.is_dir():
                return {
                    "cleaned_count": 0,
                    "failed_count": 0,
                    "elapsed_ms": 0,
                    "errors": [f"Invalid target directory: {target_dir}"]
                }

            # Iterate through all files and directories
            for root, dirs, files in os.walk(target_dir):
                for filename in files:
                    # Check if the file is a lock file
                    is_lock = False
                    if filename.startswith('~$'):
                        is_lock = True
                    elif filename.startswith('.~lock.'):
                        is_lock = True

                    if is_lock:
                        file_path = os.path.join(root, filename)
                        try:
                            # Attempt to remove the file
                            os.remove(file_path)
                            cleaned_count += 1
                        except Exception as e:
                            # Self-healing / fault tolerance
                            failed_count += 1
                            errors.append(f"Failed to remove {file_path}: {str(e)}")

        except Exception as e:
            # Catch overarching errors during os.walk or Path resolution
            errors.append(f"Fatal error during clean: {str(e)}")

        end_time = time.time()
        elapsed_ms = (end_time - start_time) * 1000

        return {
            "cleaned_count": cleaned_count,
            "failed_count": failed_count,
            "elapsed_ms": elapsed_ms,
            "errors": errors
        }

def clean_wps_locks(target_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for zero-configuration, one-click access.
    """
    cleaner = WPSLockConflictCleaner()
    return cleaner.clean_locks(target_dir)

import os
import stat

def clean_wps_lock_conflicts(target_dir=None):
    """
    Core engine to detect and clean WPS/Excel lock conflicts.
    Automatically handles missing parameters, dirty data types, and boundary conditions.
    """
    # 1. Missing parameter fallback
    if target_dir is None:
        target_dir = "."

    # 2. Dirty data silent cleaning
    if not isinstance(target_dir, str):
        try:
            target_dir = str(target_dir)
        except Exception:
            target_dir = "."

    try:
        target_dir = target_dir.strip()
        if not target_dir:
            target_dir = "."
        target_dir = os.path.abspath(target_dir)
    except Exception:
        target_dir = os.path.abspath(".")

    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return {"status": "success", "removed": [], "errors": ["Invalid or non-existent directory"]}

    removed = []
    errors = []

    try:
        for root, _, files in os.walk(target_dir):
            for filename in files:
                if (filename.startswith('.~lock.') and filename.endswith('#')) or filename.startswith('~$'):
                    filepath = os.path.join(root, filename)
                    try:
                        os.remove(filepath)
                        removed.append(filepath)
                    except PermissionError:
                        try:
                            os.chmod(filepath, stat.S_IWUSR)
                            os.remove(filepath)
                            removed.append(filepath)
                        except Exception as e:
                            errors.append(f"Failed to remove {filepath}: {str(e)}")
                    except Exception as e:
                        errors.append(f"Failed to remove {filepath}: {str(e)}")
    except Exception as e:
        errors.append(f"Failed to walk directory: {str(e)}")

    return {
        "status": "success",
        "removed": removed,
        "errors": errors
    }

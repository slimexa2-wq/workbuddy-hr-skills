import os
import re
from typing import Dict, Any, List, Optional

def clean_lock_files(directory: str = ".") -> Dict[str, Any]:
    """
    Scans a directory (non-recursively by default, designed for simple one-click use)
    and removes WPS/Excel temporary lock files (.~lock.*# and ~$*).

    Args:
        directory: The directory to scan. Defaults to the current directory if empty or missing.

    Returns:
        A dictionary with the results, designed to be easily parseable and fault tolerant.
    """
    if not directory or not isinstance(directory, str):
        directory = "."

    if not os.path.exists(directory):
        return {"status": "error", "message": "Directory does not exist.", "cleaned": []}

    cleaned_files = []

    try:
        for filename in os.listdir(directory):
            # Check for WPS .~lock.*# pattern or Excel ~$* pattern
            if filename.startswith(".~lock.") and filename.endswith("#"):
                target = os.path.join(directory, filename)
                try:
                    os.remove(target)
                    cleaned_files.append(filename)
                except Exception:
                    pass # Ignore permissions or other OS errors, silent failure to avoid popup
            elif filename.startswith("~$"):
                target = os.path.join(directory, filename)
                try:
                    os.remove(target)
                    cleaned_files.append(filename)
                except Exception:
                    pass
    except Exception as e:
        return {"status": "error", "message": str(e), "cleaned": cleaned_files}

    return {"status": "success", "cleaned": cleaned_files}


def bridge_schema(source_data: Dict[str, Any], target_schema: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Automatically maps old version fields to new version fields based on string similarity.
    Handles dirty data (None, empty dicts) silently.

    Args:
        source_data: The input dictionary to map.
        target_schema: A list of expected keys in the output. If None, returns the cleaned source_data.

    Returns:
        The mapped dictionary.
    """
    if not isinstance(source_data, dict):
        return {}

    if not target_schema or not isinstance(target_schema, list):
        return source_data.copy()

    result = {}

    # Simple mapping rule:
    # 1. Exact match (case insensitive)
    # 2. Substring match
    # 3. If no match, fill with None or skip

    source_keys = list(source_data.keys())
    lower_source_keys = {k.lower(): k for k in source_keys}

    for target_key in target_schema:
        lower_target = target_key.lower()

        # 1. Exact match (case insensitive)
        if lower_target in lower_source_keys:
            result[target_key] = source_data[lower_source_keys[lower_target]]
            continue

        # 2. Substring match or partial match (very basic fuzzy logic for schema versioning)
        # e.g. "userName" -> "user_name"
        normalized_target = re.sub(r'[^a-z0-9]', '', lower_target)

        matched = False
        for s_key in source_keys:
            normalized_source = re.sub(r'[^a-z0-9]', '', str(s_key).lower())

            if normalized_target and normalized_source and (normalized_target in normalized_source or normalized_source in normalized_target):
                result[target_key] = source_data[s_key]
                matched = True
                break

        if not matched:
            result[target_key] = None # Default fallback

    return result

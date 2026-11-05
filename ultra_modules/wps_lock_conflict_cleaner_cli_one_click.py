import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def detect_and_clean_locks(target_dir: str = ".") -> Dict[str, Any]:
    """
    Detects and cleanly removes WPS/Excel temporary lock files (.~lock* and ~$*).

    Args:
        target_dir: The directory to scan. Defaults to current directory.

    Returns:
        Dict containing counts and lists of removed and failed files.
    """
    if not isinstance(target_dir, str) or not os.path.exists(target_dir):
        logging.warning(f"Invalid target_dir '{target_dir}'. Falling back to current directory.")
        target_dir = "."

    removed_files = []
    failed_files = []

    try:
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.startswith(".~lock.") or file.startswith("~$"):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        removed_files.append(file_path)
                        logging.info(f"Removed lock file: {file_path}")
                    except Exception as e:
                        failed_files.append(file_path)
                        logging.error(f"Failed to remove {file_path}: {e}")
    except Exception as e:
        logging.error(f"Error walking directory {target_dir}: {e}")

    return {
        "status": "success",
        "target_dir": target_dir,
        "removed_count": len(removed_files),
        "failed_count": len(failed_files),
        "removed_files": removed_files,
        "failed_files": failed_files
    }

def json_excel_adapter(result: Dict[str, Any], output_format: str = "json") -> str:
    """
    Adapts the result into the requested format (json or simulated excel output text for simplicity).

    Args:
        result: The result dictionary from detect_and_clean_locks.
        output_format: The format to output ('json' or 'excel').
    """
    if not isinstance(output_format, str) or output_format.lower() not in ["json", "excel"]:
        logging.warning(f"Invalid output_format '{output_format}'. Falling back to json.")
        output_format = "json"

    output_format = output_format.lower()

    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    elif output_format == "excel":
        # Simulating Excel export message as text for zero-config CLI
        lines = ["--- Excel Summary ---"]
        lines.append(f"Target Directory: {result.get('target_dir')}")
        lines.append(f"Removed Count: {result.get('removed_count')}")
        lines.append(f"Failed Count: {result.get('failed_count')}")
        if result.get('removed_files'):
            lines.append("Removed Files:")
            for f in result.get('removed_files'):
                lines.append(f"  - {f}")
        if result.get('failed_files'):
            lines.append("Failed Files:")
            for f in result.get('failed_files'):
                lines.append(f"  - {f}")
        return "\n".join(lines)

def main():
    """
    Zero-parameter CLI entry point.
    """
    # Accept zero config, run on current directory
    print("Starting WPS/Excel Lock File Cleaner...")
    result = detect_and_clean_locks()

    # Default to json output for programmatic ease, though excel is supported
    output = json_excel_adapter(result, output_format="json")
    print(output)

    # Exit with 0 if no failures, else 1
    if result["failed_count"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()

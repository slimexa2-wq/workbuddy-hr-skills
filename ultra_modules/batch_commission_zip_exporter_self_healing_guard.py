import zipfile
import csv
import io
import time
import os
import shutil
import tempfile
import logging

# Set up logging for self-healing operations
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class ExportState:
    def __init__(self):
        self.last_export_time = 0
        self.last_export_path = None
        self.backup_path = None

_export_state = ExportState()

def _safe_str(val):
    if val is None:
        return ""
    try:
        if isinstance(val, (int, float)):
            # Convert NaN or Infinity safely if they somehow pass as float
            if isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf')):
                return str(val)
        return str(val).strip()
    except Exception:
        return ""

def export_commissions(data, output_zip_path=None):
    """
    Exports commission data to a ZIP file grouped by vendor.
    Appends an "《（审核版）》" (Audited Version) column to each row.
    Maintains a 5-second undo snapshot.

    Self-healing features:
    - If `data` is None or invalid, falls back to an empty list.
    - If `output_zip_path` is None, creates a temp file.
    - Filters out rows that are not dicts or fixes them.
    - Fixes missing keys by defaulting to empty strings.
    """
    global _export_state

    # 1. Self-healing on parameters
    if not isinstance(data, list):
        logger.warning("Input data is not a list. Self-healing: Defaulting to empty list.")
        data = []

    if not output_zip_path or not isinstance(output_zip_path, str):
        output_zip_path = os.path.join(tempfile.gettempdir(), "commissions_export.zip")
        logger.warning(f"Invalid output_zip_path. Self-healing: Defaulting to {output_zip_path}")

    # Group by vendor
    vendor_data = {}
    for row in data:
        # Self-healing on row
        if not isinstance(row, dict):
            logger.warning(f"Row is not a dict: {row}. Skipping.")
            continue

        vendor = _safe_str(row.get('vendor', 'Unknown Vendor'))
        if not vendor:
            vendor = 'Unknown Vendor'

        if vendor not in vendor_data:
            vendor_data[vendor] = []

        vendor_data[vendor].append(row)

    # Create the zip file
    try:
        # Save previous file for undo snapshot if it exists
        backup_path = None
        if os.path.exists(output_zip_path):
            backup_fd, backup_path = tempfile.mkstemp(suffix=".zip")
            os.close(backup_fd)
            shutil.copy2(output_zip_path, backup_path)

        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for vendor, rows in vendor_data.items():
                if not rows:
                    continue

                # Collect all headers across rows for this vendor to self-heal missing columns
                all_headers = set()
                for row in rows:
                    all_headers.update(row.keys())

                headers = list(all_headers)
                # Ensure vendor is the first column if it exists in data
                if 'vendor' in headers:
                    headers.remove('vendor')
                    headers.insert(0, 'vendor')

                # Append the review column
                review_col = "《（审核版）》"
                if review_col not in headers:
                    headers.append(review_col)

                # Write to CSV in memory
                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=headers)
                writer.writeheader()

                for row in rows:
                    processed_row = {}
                    for header in headers:
                        if header == review_col:
                            processed_row[header] = "Pending" # Default review status
                        else:
                            processed_row[header] = _safe_str(row.get(header, ""))
                    writer.writerow(processed_row)

                # Add to ZIP
                safe_vendor_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in vendor)
                zf.writestr(f"{safe_vendor_name}_commissions.csv", csv_buffer.getvalue())

        # Update export state for undo
        _export_state.last_export_time = time.time()
        _export_state.last_export_path = output_zip_path
        _export_state.backup_path = backup_path

        return output_zip_path

    except Exception as e:
        logger.error(f"Failed to create ZIP: {e}")
        # Self-healing: if failed, return None rather than crashing
        return None

def undo_export():
    """
    Undoes the last export operation if called within 5 seconds.
    Restores the previous file state.
    """
    global _export_state

    if not _export_state.last_export_path:
        logger.warning("No export operation to undo.")
        return False

    current_time = time.time()
    if current_time - _export_state.last_export_time > 5:
        logger.warning("Undo period (5 seconds) has expired.")
        return False

    try:
        if _export_state.backup_path and os.path.exists(_export_state.backup_path):
            shutil.copy2(_export_state.backup_path, _export_state.last_export_path)
            os.remove(_export_state.backup_path)
        else:
            if os.path.exists(_export_state.last_export_path):
                os.remove(_export_state.last_export_path)

        # Reset state
        _export_state.last_export_time = 0
        _export_state.last_export_path = None
        _export_state.backup_path = None

        return True
    except Exception as e:
        logger.error(f"Failed to undo export: {e}")
        return False

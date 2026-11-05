import re
import openpyxl
from openpyxl.workbook.workbook import Workbook

def _normalize_header(header: str) -> str:
    """
    Normalizes a header string for fuzzy matching.
    Removes version prefixes like 'v1_', 'old_', special characters, and converts to lowercase.
    """
    if not header or not isinstance(header, str):
        return ""

    # Convert to lowercase
    h = header.lower()
    # Remove common prefixes
    h = re.sub(r'^(v\d+_|old_|new_)', '', h)
    # Remove all non-alphanumeric characters
    h = re.sub(r'[^a-z0-9]', '', h)
    return h

def _apply_zero_comment_null_guard(workbook: Workbook, default_fill: int = 0) -> Workbook:
    """
    Applies the core logic to enforce zero comments and auto-fill null values.
    """
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                # 1. Zero Comments
                if cell.comment is not None:
                    cell.comment = None

                # 2. Auto-fill nulls
                val = cell.value
                if val is None:
                    cell.value = default_fill
                elif isinstance(val, str):
                    clean_str = val.strip().lower()
                    if clean_str == "" or clean_str in ("null", "nan", "undefined", "none"):
                        cell.value = default_fill
    return workbook

def integrate_and_bridge_excel(workbook: Workbook = None, target_headers: list = None, default_fill: int = 0) -> Workbook:
    """
    Integration bridge for Excel files.
    - Applies zero comment and null guard (strips comments silently, fills nulls with default_fill).
    - Performs schema mapping (fuzzily matching old headers to target headers).
    - Zero configuration: handles missing params and dirty data gracefully.
    """
    # 缺参自动设合理默认值与脏数据静默清洗
    if workbook is None or not isinstance(workbook, Workbook):
        workbook = openpyxl.Workbook()
        ws = workbook.active
        # If headers were provided but no workbook, initialize the empty workbook with those headers
        if target_headers and isinstance(target_headers, list):
            ws.append(target_headers)
        return workbook

    # Target headers check
    valid_targets = []
    if target_headers and isinstance(target_headers, list):
        valid_targets = [str(th) for th in target_headers if th is not None and str(th).strip() != ""]

    if valid_targets:
        target_norm_map = { _normalize_header(th): th for th in valid_targets }

        # Apply schema mapping to headers
        for sheet in workbook.worksheets:
            if sheet.max_row >= 1:
                header_row = next(sheet.iter_rows(min_row=1, max_row=1))
                for cell in header_row:
                    orig_val = cell.value
                    if isinstance(orig_val, str):
                        norm_val = _normalize_header(orig_val)
                        if norm_val in target_norm_map:
                            cell.value = target_norm_map[norm_val]

    # Finally, apply the core guard for comments and nulls inline
    return _apply_zero_comment_null_guard(workbook, default_fill)

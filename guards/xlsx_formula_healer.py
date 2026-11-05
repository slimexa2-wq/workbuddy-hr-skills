import os
import shutil
import re
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string

def heal_xlsx(filepath: str):
    """
    Auto-scan and heal excel file according to rules:
    1. Backup original file.
    2. Zero comments.
    3. Zero blanks in data area.
    4. Numeric strings converted to number.
    5. Fix SUM formula (missing end rows, misaligned columns).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    snapshot_path = filepath + ".snapshot"
    shutil.copy2(filepath, snapshot_path)

    wb = load_workbook(filepath, data_only=False)

    for sheet in wb.worksheets:
        max_row = sheet.max_row
        max_col = sheet.max_column

        for row_idx in range(1, max_row + 1):
            for col_idx in range(1, max_col + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)

                # Rule 1: Zero comments
                if cell.comment:
                    cell.comment = None

                # Rule 2: Zero blanks (empty value or whitespace only string)
                if cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
                    # Only fill 0 if it's within a reasonable data boundary (e.g. not just trailing empty rows)
                    # For simplicity, filling 0 for any blank inside max_row x max_col.
                    # A better heuristic might be needed but keeping it simple based on requirements.
                    cell.value = 0

                # Rule 3: Numeric strings with spaces/newlines
                if isinstance(cell.value, str):
                    val_stripped = cell.value.strip()
                    if val_stripped:
                        try:
                            # Try converting to float/int
                            if '.' in val_stripped:
                                cell.value = float(val_stripped)
                            else:
                                cell.value = int(val_stripped)
                        except ValueError:
                            pass

                # Rule 4: Formula fixes (SUM)
                if isinstance(cell.value, str) and str(cell.value).startswith('='):
                    formula = str(cell.value)
                    if re.search(r'SUM\(', formula, re.IGNORECASE):
                        # Find all SUM(Xn:Ym)
                        def replacer(match):
                            prefix, start_col, start_row, colon, end_col, end_row, suffix = match.groups()

                            start_row = int(start_row)
                            end_row = int(end_row)

                            start_col_upper = start_col.upper()
                            end_col_upper = end_col.upper()

                            # Misaligned columns fix: if start_col == end_col, it's a vertical SUM.
                            # If they don't match the cell's column, fix it.
                            my_col_letter = get_column_letter(cell.column)
                            if start_col_upper == end_col_upper and start_col_upper != my_col_letter:
                                start_col = my_col_letter
                                end_col = my_col_letter
                                # Try matching original case
                                if start_col_upper.islower():
                                    start_col = start_col.lower()
                                    end_col = end_col.lower()


                            # Missing rows fix: if vertical SUM, and end_row < cell.row - 1
                            if start_col.upper() == end_col.upper() and end_row < cell.row - 1:
                                end_row = cell.row - 1

                            return f"{prefix}{start_col}{start_row}{colon}{end_col}{end_row}{suffix}"

                        # Match SUM(A1:A10) preserving case
                        pattern = re.compile(r'(SUM\(\s*)([a-zA-Z]+)(\d+)(\s*:\s*)([a-zA-Z]+)(\d+)(\s*\))', re.IGNORECASE)
                        new_formula = pattern.sub(replacer, formula)
                        cell.value = new_formula

    wb.save(filepath)
    wb.close()

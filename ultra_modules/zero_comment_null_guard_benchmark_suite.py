import os
import time
import datetime
import openpyxl
from openpyxl.comments import Comment

class ZeroCommentNullGuard:
    """
    Hardcore pre-checker for Excel files:
    1. Removes all comments (comments=0).
    2. Automatically fills empty values with 0 in numeric contexts.
    Extremely simple usage with auto-fallback.
    """

    @classmethod
    def process_file(cls, input_path: str, output_path: str = None) -> str:
        """
        Process the Excel file to remove comments and fill nulls in numeric columns with 0.
        If output_path is missing, auto-generates a sensible default.
        """
        if not output_path:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_guarded{ext}"

        start_time = time.time()

        try:
            wb = openpyxl.load_workbook(input_path, data_only=False)
        except Exception:
            # Zero crash policy: if it's not a valid excel or unreadable, return original path safely
            return input_path

        for sheet in wb.worksheets:
            # Heuristic: Identify columns that likely contain numeric data
            numeric_cols = set()
            max_col = sheet.max_column
            max_row = sheet.max_row

            for col_idx in range(1, max_col + 1):
                has_num = False
                # Check a sample of rows to determine if the column is numeric
                for row_idx in range(2, min(max_row, 100) + 1):
                    val = sheet.cell(row=row_idx, column=col_idx).value
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        has_num = True
                        break

                if has_num:
                    numeric_cols.add(col_idx)

            # Process cells
            for row in sheet.iter_rows():
                for cell in row:
                    # 1. Zero Comments Enforcer
                    if cell.comment:
                        cell.comment = None

                    # 2. Null Guard (fill 0 for numeric columns)
                    is_null = cell.value is None or (isinstance(cell.value, str) and not cell.value.strip())
                    if is_null and cell.column in numeric_cols:
                        cell.value = 0

        try:
            wb.save(output_path)
        except Exception:
            # Fallback if save fails (e.g., permission denied)
            return input_path
        finally:
            wb.close()

        return output_path


class SyntheticFixtureGenerator:
    """
    Generates extreme edge-case synthetic datasets for benchmarking and verification.
    Includes empty values, garbled text, high volume, cross-year/month dates.
    """

    @staticmethod
    def generate_fixture(filepath: str, rows: int = 1000):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Synthetic Data"

        # Headers
        ws.append(["ID", "Score", "Name", "Date", "Notes"])

        # Add comment to header
        ws["B1"].comment = Comment("This is a score column", "System")

        for i in range(1, rows + 1):
            # 1. ID: normal numeric
            # 2. Score: numeric, with nulls every 10 rows
            score = i * 1.5 if i % 10 != 0 else None

            # 3. Name: string, garbled data every 5 rows.
            # Openpyxl doesn't allow some control characters like \x00. Let's use valid garbled text.
            name = f"User_{i}" if i % 5 != 0 else "乱码@#$%^&*()_+{}:?><~"

            # 4. Date: cross year/month boundaries
            if i % 3 == 0:
                date_val = datetime.datetime(2023, 12, 31, 23, 59, 59)
            elif i % 3 == 1:
                date_val = datetime.datetime(2024, 1, 1, 0, 0, 1)
            else:
                date_val = datetime.datetime(2024, 2, 29, 12, 0, 0) # Leap year

            # 5. Notes: strings with empty spaces
            notes = "Note" if i % 2 == 0 else "   "

            ws.append([i, score, name, date_val, notes])

            # Add comments to some cells
            if i % 100 == 0:
                ws.cell(row=i+1, column=2).comment = Comment(f"Anomaly {i}", "Audit")

        wb.save(filepath)
        wb.close()
        return filepath

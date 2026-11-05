import os
import shutil
import logging
from typing import Optional

try:
    import openpyxl
except ImportError:
    openpyxl = None

class ZeroCommentNullGuard:
    def __init__(self):
        self.snapshots = {}

    def process(self, filepath: Optional[str] = None) -> bool:
        if not filepath or not isinstance(filepath, str):
            return False

        if not os.path.exists(filepath):
            return False

        if not openpyxl:
            return False

        snapshot_path = f"{filepath}.snapshot"
        try:
            # Create snapshot for 5s undo mechanism
            shutil.copy2(filepath, snapshot_path)
            self.snapshots[filepath] = snapshot_path

            # Process Excel file
            wb = openpyxl.load_workbook(filepath)
            for sheet in wb.worksheets:
                # We need to iterate over all dimensions that are populated.
                # It's possible that iter_rows doesn't include cells that are completely empty but inside the dimensions.
                # Actually, max_row and max_column denote the boundaries.
                for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
                    for cell in row:
                        if cell.comment:
                            cell.comment = None

                        # fill 0 for empty cells
                        if cell.value is None or (isinstance(cell.value, str) and not str(cell.value).strip()):
                            cell.value = 0

            wb.save(filepath)
            wb.close()
            return True
        except Exception as e:
            # Silent self-healing / fallback
            logging.error(f"Error processing {filepath}: {e}")
            if filepath in self.snapshots and os.path.exists(self.snapshots[filepath]):
                try:
                    shutil.copy2(self.snapshots[filepath], filepath)
                except Exception:
                    pass
            return False

    def undo(self, filepath: Optional[str] = None) -> bool:
        if not filepath or not isinstance(filepath, str):
            return False

        if filepath in self.snapshots and os.path.exists(self.snapshots[filepath]):
            try:
                shutil.copy2(self.snapshots[filepath], filepath)
                os.remove(self.snapshots[filepath])
                del self.snapshots[filepath]
                return True
            except Exception:
                return False
        return False

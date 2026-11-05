import os
import concurrent.futures
import openpyxl
from typing import List, Dict, Any, Optional

class ZeroCommentNullGuardBatchPipeline:
    """
    A high-throughput batch pipeline for Excel processing.
    Ensures zero comments and auto-fills empty numeric cells with 0.
    """
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.progress = {"total": 0, "processed": 0, "failed": 0}

    def _process_single_file(self, file_path: str) -> Dict[str, Any]:
        """
        Processes a single Excel file.
        Returns a dict with 'file_path', 'status', and optionally 'error'.
        """
        if not file_path:
            return {"file_path": file_path, "status": "failed", "error": "Missing file_path"}

        if not os.path.exists(file_path):
            return {"file_path": file_path, "status": "failed", "error": f"File not found: {file_path}"}

        try:
            wb = openpyxl.load_workbook(file_path)
            for sheet in wb.worksheets:
                numeric_cols = set()

                # First pass: remove comments and find numeric columns
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.comment:
                            cell.comment = None

                        # Identify if column is numeric (contains int or float, but not boolean)
                        if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                            numeric_cols.add(cell.column)

                # Second pass: fill None with 0 in numeric columns
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.column in numeric_cols and cell.value is None:
                            cell.value = 0

            wb.save(file_path)
            return {"file_path": file_path, "status": "success"}
        except Exception as e:
            return {"file_path": file_path, "status": "failed", "error": str(e)}

    def process_batch(self, file_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Processes a batch of Excel files concurrently.
        Supports 10~1000 files stream processing.
        """
        if file_paths is None:
            file_paths = []

        self.progress = {"total": len(file_paths), "processed": 0, "failed": 0}
        results = []

        if not file_paths:
            return results

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {executor.submit(self._process_single_file, path): path for path in file_paths}

            for future in concurrent.futures.as_completed(future_to_path):
                result = future.result()
                results.append(result)
                if result["status"] == "success":
                    self.progress["processed"] += 1
                else:
                    self.progress["failed"] += 1

        return results

    def get_progress_snapshot(self) -> Dict[str, int]:
        """
        Returns the current progress snapshot.
        """
        return self.progress.copy()

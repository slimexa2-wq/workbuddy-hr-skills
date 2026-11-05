import uuid
import time
import copy
import re
from typing import List, Dict, Any, Optional

class AuditLog:
    def __init__(self):
        self.trace_id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.logs = []

    def record(self, action: str, details: Dict[str, Any]):
        self.logs.append({
            "action": action,
            "details": details,
            "time": time.time()
        })

class ExcelDeliveryPrechecker:
    """
    Hardcore pre-checker for Excel delivery data.
    Ensures zero comments, null autofill for numeric columns, and data deduplication.
    Provides backend traceable audit logs and difference highlights.
    """
    def __init__(self, numeric_columns: Optional[List[str]] = None, deduplicate_keys: Optional[List[str]] = None):
        # Zero configuration auto-fallback: if not provided, defaults to empty or infers during process
        self.numeric_columns = numeric_columns if numeric_columns is not None else []
        self.deduplicate_keys = deduplicate_keys if deduplicate_keys is not None else []
        self.audit_logger = AuditLog()

    def process(self, rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Process Excel data rows.
        """
        if rows is None:
            rows = []

        if not rows:
            self.audit_logger.record("init", {"message": "Empty data received, auto-falling back to empty list"})
            return {
                "clean_data": [],
                "highlights": [],
                "audit_trace_id": self.audit_logger.trace_id,
                "audit_logs": self.audit_logger.logs
            }

        clean_rows = []
        highlights = []

        # Determine numeric columns if not explicitly provided
        numeric_cols = set(self.numeric_columns)
        if not numeric_cols:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for k, v in row.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        numeric_cols.add(k)

        seen_keys = set()

        # Regex to detect comment-like keys case-insensitively
        comment_pattern = re.compile(r'comment', re.IGNORECASE)

        for idx, original_row in enumerate(rows):
            if not isinstance(original_row, dict):
                # Dirty data self-healing: skip entirely invalid rows
                self.audit_logger.record("dirty_heal", {"row_idx": idx, "action": "dropped non-dict row"})
                continue

            repaired_row = copy.deepcopy(original_row)
            row_modifications = []

            # 1. Zero comments (comments=0) policy
            keys_to_remove = [k for k in repaired_row.keys() if comment_pattern.search(str(k))]
            for k in keys_to_remove:
                removed_val = repaired_row.pop(k)
                row_modifications.append({"field": k, "old": removed_val, "new": None, "reason": "Zero comment policy"})
                self.audit_logger.record("zero_comment", {"row_idx": idx, "field": k, "removed": removed_val})

            # 2. Null Guard & Auto-fill for numeric columns
            for k in list(repaired_row.keys()):
                v = repaired_row[k]

                # Treat empty string or None as null
                is_null = v is None or (isinstance(v, str) and v.strip() == "")

                if k in numeric_cols:
                    if is_null:
                        repaired_row[k] = 0
                        row_modifications.append({"field": k, "old": v, "new": 0, "reason": "Null guard autofill"})
                        self.audit_logger.record("null_guard", {"row_idx": idx, "field": k, "old_value": v, "new_value": 0})
                    elif isinstance(v, str):
                        try:
                            # Try to normalize string representations of numbers
                            float_val = float(v)
                            new_val = int(float_val) if float_val.is_integer() else float_val
                            if new_val != v:
                                repaired_row[k] = new_val
                                row_modifications.append({"field": k, "old": v, "new": new_val, "reason": "Type normalization"})
                                self.audit_logger.record("type_norm", {"row_idx": idx, "field": k, "old_value": v, "new_value": new_val})
                        except ValueError:
                            # Dirty data in numeric column -> self-heal to 0
                            repaired_row[k] = 0
                            row_modifications.append({"field": k, "old": v, "new": 0, "reason": "Dirty numeric self-healing"})
                            self.audit_logger.record("dirty_heal", {"row_idx": idx, "field": k, "old_value": v, "new_value": 0})

            # 3. Deduplication
            if self.deduplicate_keys:
                # Use a default tuple of None for missing keys
                dedup_key = tuple(repaired_row.get(k) for k in self.deduplicate_keys)
                if dedup_key in seen_keys:
                    self.audit_logger.record("deduplicate", {"row_idx": idx, "key": dedup_key, "action": "dropped"})
                    # Skip adding this row
                    continue
                seen_keys.add(dedup_key)

            clean_rows.append(repaired_row)
            if row_modifications:
                highlights.append({
                    "row_idx": idx,
                    "changes": row_modifications
                })

        self.audit_logger.record("completion", {"total_original": len(rows), "total_clean": len(clean_rows), "highlights_count": len(highlights)})

        return {
            "clean_data": clean_rows,
            "highlights": highlights,
            "audit_trace_id": self.audit_logger.trace_id,
            "audit_logs": self.audit_logger.logs
        }


def one_click_precheck(data: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Dict[str, Any]:
    """
    Extreme simplified frontend API.
    One-click check, zero configurations needed.
    """
    checker = ExcelDeliveryPrechecker(
        numeric_columns=kwargs.get("numeric_columns"),
        deduplicate_keys=kwargs.get("deduplicate_keys")
    )
    return checker.process(data)

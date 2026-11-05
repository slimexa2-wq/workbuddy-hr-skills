import openpyxl
from openpyxl.workbook.workbook import Workbook

def run_zero_comment_null_guard(workbook: Workbook = None, default_fill: int = 0) -> Workbook:
    """
    Excel Preflight Guard:
    - Enforces zero comments (strips them silently)
    - Auto-fills empty or invalid null-like cells with default_fill (default 0)
    - Zero configuration, handles missing params and dirty data without throwing blocking errors.
    """
    # 缺参自动设合理默认值与脏数据静默清洗
    if workbook is None or not isinstance(workbook, Workbook):
        # 兜底：如果传入非 Workbook 对象或为空，返回全新的无污染 Workbook
        workbook = openpyxl.Workbook()

    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                # 1. 零批注 (Zero Comments)
                if cell.comment is not None:
                    cell.comment = None

                # 2. 数值格空值自动填0
                val = cell.value
                if val is None:
                    cell.value = default_fill
                elif isinstance(val, str):
                    clean_str = val.strip().lower()
                    if clean_str == "" or clean_str in ("null", "nan", "undefined", "none"):
                        cell.value = default_fill

    return workbook

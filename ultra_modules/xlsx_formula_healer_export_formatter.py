import os
import logging
from openpyxl import load_workbook
import datetime
import traceback

logger = logging.getLogger(__name__)

def heal_excel_report(input_path: str, output_path: str = None) -> dict:
    """
    Scans and silently repairs an Excel report by fixing common errors (#REF!, #DIV/0!, #VALUE!),
    converting textual numbers, replacing NaN/None, and stripping all comments to export a pure file.
    Also generates a concise WeChat/Feishu report summary.

    Args:
        input_path: Path to the input Excel file.
        output_path: Optional path to save the repaired file. If not provided, it generates one.

    Returns:
        dict: Summary of the operation, including the short report text.
    """
    stats = {
        "errors_fixed": 0,
        "comments_removed": 0,
        "cells_processed": 0,
        "text_numbers_converted": 0,
        "nulls_replaced": 0,
        "status": "success",
        "error_msg": None,
        "brief_report": ""
    }

    if not input_path or not os.path.exists(input_path):
        stats["status"] = "failed"
        stats["error_msg"] = "Input file missing or path is empty."
        stats["brief_report"] = "【数据汇报】\n文件未找到，无需处理。\n(自动降级处理)"
        return stats

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_healed{ext}"

    try:
        wb = load_workbook(input_path)

        error_types = {'#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NUM!', '#NULL!'}
        null_types = {'nan', 'none', 'null'}

        for sheet in wb.sheetnames:
            ws = wb[sheet]
            for row in ws.iter_rows():
                for cell in row:
                    stats["cells_processed"] += 1

                    if cell.comment:
                        cell.comment = None
                        stats["comments_removed"] += 1

                    val = cell.value
                    if val is None:
                        continue

                    if isinstance(val, str):
                        val_str = val.strip()
                        val_lower = val_str.lower()

                        if val_str in error_types:
                            cell.value = 0
                            stats["errors_fixed"] += 1
                        elif val_lower in null_types:
                            cell.value = 0
                            stats["nulls_replaced"] += 1
                        else:
                            try:
                                if '.' in val_str:
                                    cell.value = float(val_str)
                                else:
                                    cell.value = int(val_str)
                                stats["text_numbers_converted"] += 1
                            except ValueError:
                                pass

        wb.save(output_path)

        report_lines = [
            "【数据简报】报表已纯净导出",
            f"⚡ 处理指标: 清理批注{stats['comments_removed']}个，修复异常值{stats['errors_fixed']}处，转换文本数字{stats['text_numbers_converted']}个，兜底空值{stats['nulls_replaced']}个。",
            f"📁 导出路径: {output_path}"
        ]
        stats["brief_report"] = "\n".join(report_lines)

    except Exception as e:
        logger.error(f"Error repairing excel: {traceback.format_exc()}")
        stats["status"] = "failed"
        stats["error_msg"] = str(e)
        stats["brief_report"] = f"【数据汇报】\n处理失败，遇到未知异常: {str(e)}\n(自动降级处理)"

    return stats

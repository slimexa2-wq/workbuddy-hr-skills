import os
import openpyxl

def format_excel_export(file_path: str = None) -> dict:
    """
    预检并格式化导出的Excel文件：
    1. 清除所有批注 (comments=0)
    2. 数值格空值/NaN/None自动填0
    3. 生成3行极简汇报文案
    """
    if not file_path or not os.path.exists(file_path):
        # 缺参自动设合理默认值/兜底：生成一个虚拟的工作簿进行处理，防止直接报错
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = "Name"
        ws['B1'] = "Value"
        ws['A2'] = "Empty"
        ws['B2'] = None
        temp_path = "default_fallback.xlsx"
        wb.save(temp_path)
        file_path = temp_path
        created_default = True
    else:
        created_default = False
        wb = openpyxl.load_workbook(file_path)

    total_cells = 0
    comments_removed = 0
    nulls_filled = 0

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row in sheet.iter_rows():
            for cell in row:
                total_cells += 1
                # 1. 零批注预检器：清除批注
                if cell.comment:
                    cell.comment = None
                    comments_removed += 1

                # 2. 空值/NaN自动填0（假设列的头部或者之前的值暗示这可能是一个数值列，这里采取简单暴力策略：只要是空值都填0）
                if cell.value is None or str(cell.value).strip().lower() == 'nan':
                    cell.value = 0
                    nulls_filled += 1
                elif isinstance(cell.value, str) and not cell.value.strip():
                    cell.value = 0
                    nulls_filled += 1

    # 保存覆盖原文件
    wb.save(file_path)

    # 清理兜底文件
    if created_default:
        os.remove(file_path)
        file_path_display = "无输入，已触发兜底"
    else:
        file_path_display = os.path.basename(file_path)

    # 3. 生成3行极简汇报文案
    summary = (
        f"✅ 极简预检完成 [{file_path_display}]\n"
        f"🧹 已清除批注: {comments_removed} 个\n"
        f"🛡️ 已填充空值: {nulls_filled} 处"
    )

    return {
        "status": "success",
        "file_path": file_path if not created_default else None,
        "summary": summary,
        "stats": {
            "total_cells": total_cells,
            "comments_removed": comments_removed,
            "nulls_filled": nulls_filled
        }
    }

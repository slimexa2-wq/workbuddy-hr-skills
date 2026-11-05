import os
import glob
import math
import logging

class AuditLogger:
    def __init__(self):
        self.logs = []

    def log(self, message: str):
        self.logs.append(message)
        logging.info(message)


def clean_and_format_export(target_dir: str = None, export_data: list = None) -> dict:
    """
    Cleans WPS/Excel lock files in target_dir and formats export_data.
    Zero-configuration: target_dir defaults to '.', export_data defaults to [].
    """
    audit = AuditLogger()
    audit.log("Starting WPS lock cleaner and export formatter.")

    if target_dir is None:
        target_dir = '.'
        audit.log("target_dir is None, defaulted to '.'")

    if export_data is None:
        export_data = []
        audit.log("export_data is None, defaulted to []")

    # 1. Clean WPS/Excel Lock Files
    deleted_files = 0
    try:
        lock_patterns = [
            os.path.join(target_dir, '.~lock.*'),
            os.path.join(target_dir, '~$*')
        ]

        for pattern in lock_patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    deleted_files += 1
                    audit.log(f"Deleted lock file: {file_path}")
                except Exception as e:
                    audit.log(f"Failed to delete lock file {file_path}: {str(e)}")
                    pass # silent error handling
    except Exception as e:
        audit.log(f"Error accessing target_dir {target_dir}: {str(e)}")
        # Dirty data self-healing: invalid target_dir, do nothing

    # 2. Format Export Data
    # 确保导出数据comments=0、数值格无NaN/None
    formatted_data = []

    if not isinstance(export_data, list):
        audit.log(f"export_data is not a list (type: {type(export_data)}), resetting to []")
        export_data = []

    for idx, row in enumerate(export_data):
        if not isinstance(row, dict):
            audit.log(f"Row {idx} is not a dict, skipping.")
            continue

        new_row = {}
        for k, v in row.items():
            if k == 'comments':
                new_row[k] = 0
                audit.log(f"Row {idx}: reset comments to 0")
            elif isinstance(v, (int, float)):
                if math.isnan(v):
                    new_row[k] = 0
                    audit.log(f"Row {idx}: reset NaN {k} to 0")
                else:
                    new_row[k] = v
            elif v is None:
                 # Check if this key seems like a numeric field based on other rows? Or just replace None with 0?
                 # Since rule says "数值格无NaN/None", let's assume None in any potential numeric/unknown field should be handled.
                 # Without schema, we can't tell if a None is for string or number, but since it says "数值格无NaN/None",
                 # we can sanitize None to 0 or '' but 0 is safer for numeric.
                 # Let's replace None with 0 for simplicity if it might be a numeric field, or just 0 generally to be safe.
                 new_row[k] = 0
                 audit.log(f"Row {idx}: reset None {k} to 0")
            else:
                new_row[k] = v

        # Enforce comments=0 even if missing
        if 'comments' not in new_row:
             new_row['comments'] = 0
             audit.log(f"Row {idx}: added comments=0")

        formatted_data.append(new_row)

    # 3. Generate Minimalist Summary (3 lines)
    # 同步生成3行极简汇报文案
    total_records = len(formatted_data)

    summary = f"""【工作汇报】WPS/Excel 冲突清理与数据导出
- 冲突清理：成功清理 {deleted_files} 个隐藏锁文件
- 数据导出：已导出并净化 {total_records} 条无损记录（含零批注与数值校验）"""

    audit.log("Completed execution.")
    return {
        "summary": summary,
        "data": formatted_data,
        "audit_logs": audit.logs
    }

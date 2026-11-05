import csv
import io

def transcode_and_clean_csv(input_data=None, output_format="dict_list"):
    """
    一键无感转码与Schema向前兼容清洗器 (Auto-Transcoder and Schema Integration Bridge)

    自动检测常见中文及标准编码，静默完成转码，
    并自动将新旧不同版本的考勤/工资CSV字段名映射到标准Schema。

    :param input_data: 输入的 CSV 数据（bytes 或 str）。如缺失，返回安全默认值。
    :param output_format: 输出格式，"dict_list" 返回字典列表，"csv_bytes" 返回 UTF-8 编码的 CSV 字节串。
    :return: 按照 output_format 返回相应的数据格式。如果出现异常，也会静默返回空集合（兼容容错）。
    """
    if input_data is None or not input_data:
        return [] if output_format == "dict_list" else b""

    # 1. 自动探针与无感转码
    text = ""
    if isinstance(input_data, bytes):
        encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'big5']
        decoded = False
        for enc in encodings:
            try:
                text = input_data.decode(enc)
                decoded = True
                break
            except UnicodeDecodeError:
                continue
        if not decoded:
            text = input_data.decode('utf-8', errors='ignore')
    elif isinstance(input_data, str):
        text = input_data
    else:
        return [] if output_format == "dict_list" else b""

    if not text.strip():
        return [] if output_format == "dict_list" else b""

    # 2. 读取 CSV 并静默处理脏数据
    f = io.StringIO(text)
    reader = csv.reader(f)

    headers = None
    for row in reader:
        if row and any(cell.strip() for cell in row):
            headers = row
            break

    if not headers:
        return [] if output_format == "dict_list" else b""

    # 3. Schema 向前兼容与智能映射
    schema_map = {
        "姓名": "name", "员工姓名": "name", "name": "name",
        "工号": "employee_id", "员工号": "employee_id", "id": "employee_id", "employee id": "employee_id",
        "基本工资": "base_salary", "底薪": "base_salary", "base salary": "base_salary",
        "考勤天数": "attendance_days", "出勤天数": "attendance_days", "attendance": "attendance_days"
    }

    standard_headers = []
    for h in headers:
        clean_h = h.strip().lower()
        if clean_h in schema_map:
            standard_headers.append(schema_map[clean_h])
        else:
            val = h.strip()
            standard_headers.append(val if val else "unknown_column")

    # 处理重复列名
    seen = {}
    final_headers = []
    for h in standard_headers:
        if h in seen:
            seen[h] += 1
            final_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            final_headers.append(h)

    # 4. 组装清洗后的数据
    cleaned_data = []
    for row in reader:
        # 跳过空行
        if not row or not any(cell.strip() for cell in row):
            continue

        row_clean = [col.strip() for col in row]
        if len(row_clean) < len(final_headers):
            row_clean.extend([""] * (len(final_headers) - len(row_clean)))
        elif len(row_clean) > len(final_headers):
            row_clean = row_clean[:len(final_headers)]

        row_dict = dict(zip(final_headers, row_clean))
        cleaned_data.append(row_dict)

    if output_format == "csv_bytes":
        output_io = io.StringIO()
        writer = csv.DictWriter(output_io, fieldnames=final_headers)
        writer.writeheader()
        writer.writerows(cleaned_data)
        return output_io.getvalue().encode('utf-8')

    return cleaned_data

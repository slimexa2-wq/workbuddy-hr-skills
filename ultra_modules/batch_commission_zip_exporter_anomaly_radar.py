import os
import zipfile
import tempfile
import statistics
import datetime
from collections import defaultdict
import openpyxl
from openpyxl.styles import PatternFill

def process_commissions(input_data=None, output_path=None, amount_column=None, supplier_column=None):
    """
    Process commission data, detect anomalies, group by supplier, generate Excel files,
    and package them into a single zip file.

    Args:
        input_data: List of dictionaries representing the commission records.
        output_path: Path to the output zip file. Defaults to a temporary file.
        amount_column: Name of the key containing the commission amount. Self-heals if missing.
        supplier_column: Name of the key containing the supplier name. Self-heals if missing.

    Returns:
        The path to the generated zip file.
    """
    if input_data is None:
        input_data = []

    if not input_data:
        # Create empty zip if no data
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.zip')
            os.close(fd)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            pass
        return output_path

    # Self-healing for columns
    if amount_column is None:
        possible_amount_cols = ['amount', 'commission', '提成', '金额']
        for col in possible_amount_cols:
            if col in input_data[0]:
                amount_column = col
                break
        else:
            # Fallback
            amount_column = next(iter(input_data[0].keys()))

    if supplier_column is None:
        possible_supplier_cols = ['supplier', 'vendor', '供应商']
        for col in possible_supplier_cols:
            if col in input_data[0]:
                supplier_column = col
                break
        else:
            # Fallback
            supplier_column = next(iter(input_data[0].keys()))

    # Clean data and extract valid amounts
    cleaned_data = []
    amounts = []
    for row in input_data:
        raw_val = row.get(amount_column)
        try:
            val = float(raw_val)
            amounts.append(val)
            cleaned_row = row.copy()
            cleaned_row['_clean_amount'] = val
            cleaned_data.append(cleaned_row)
        except (ValueError, TypeError):
            # Ignore dirty data that cannot be parsed as float
            cleaned_row = row.copy()
            cleaned_row['_clean_amount'] = None
            cleaned_data.append(cleaned_row)

    # Anomaly detection calculations
    n = len(amounts)
    if n > 1:
        mean_val = statistics.mean(amounts)
        stdev_val = statistics.stdev(amounts)
        if stdev_val == 0:
            stdev_val = 1e-9 # avoid division by zero

        sorted_amounts = sorted(amounts)
        q1_idx = int(n * 0.25)
        q3_idx = int(n * 0.75)
        q1 = sorted_amounts[q1_idx]
        q3 = sorted_amounts[q3_idx]
        iqr = q3 - q1
    else:
        mean_val = amounts[0] if amounts else 0
        stdev_val = 1
        q1 = q3 = iqr = 0

    # Calculate scores and sort to find top 3%
    scored_data = []
    for row in cleaned_data:
        val = row['_clean_amount']
        if val is not None:
            z_score = abs((val - mean_val) / stdev_val)
            scored_data.append((z_score, row))
        else:
            scored_data.append((0, row))

    # Sort by z-score descending
    scored_data.sort(key=lambda x: x[0], reverse=True)

    top_1_percent_count = max(1, int(n * 0.01))
    top_3_percent_count = max(1, int(n * 0.03))

    processed_records = []
    for idx, (z_score, row) in enumerate(scored_data):
        new_row = row.copy()
        if new_row['_clean_amount'] is not None:
            if idx < top_1_percent_count:
                new_row['异常标记'] = 'RED'
                new_row['原因'] = '严重异常：金额远超平均水平'
            elif idx < top_3_percent_count:
                new_row['异常标记'] = 'YELLOW'
                new_row['原因'] = '需要关注：金额存在波动'
            else:
                new_row['异常标记'] = 'GREEN'
                new_row['原因'] = '正常'
        else:
            new_row['异常标记'] = 'GREEN'
            new_row['原因'] = '非数值数据，跳过检查'

        # Remove internal helper column
        del new_row['_clean_amount']
        processed_records.append(new_row)

    # Group by supplier
    grouped_data = defaultdict(list)
    for row in processed_records:
        supp = row.get(supplier_column, 'Unknown')
        grouped_data[supp].append(row)

    # Generate Excel files and zip
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)

    red_fill = PatternFill(start_color="FFFF0000", end_color="FFFF0000", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")
    green_fill = PatternFill(start_color="FF00FF00", end_color="FF00FF00", fill_type="solid")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for supplier, records in grouped_data.items():
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Commissions"

                if not records:
                    continue

                headers = list(records[0].keys())
                ws.append(headers)

                for r_idx, record in enumerate(records, start=2):
                    row_data = [record.get(h) for h in headers]
                    ws.append(row_data)

                    status = record.get('异常标记')
                    if status == 'RED':
                        for c_idx in range(1, len(headers) + 1):
                            ws.cell(row=r_idx, column=c_idx).fill = red_fill
                    elif status == 'YELLOW':
                        for c_idx in range(1, len(headers) + 1):
                            ws.cell(row=r_idx, column=c_idx).fill = yellow_fill
                    elif status == 'GREEN':
                        for c_idx in range(1, len(headers) + 1):
                            ws.cell(row=r_idx, column=c_idx).fill = green_fill

                # Sanitize filename
                safe_supplier = str(supplier).replace('/', '_').replace('\\', '_')
                excel_filename = f"{safe_supplier}_commissions.xlsx"
                excel_path = os.path.join(tmpdir, excel_filename)

                wb.save(excel_path)
                zf.write(excel_path, excel_filename)

    return output_path

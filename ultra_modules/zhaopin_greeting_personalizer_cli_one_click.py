import json
import os
import sys
from ultra_modules.zhaopin_greeting_personalizer_core_engine import generate_greeting
try:
    import openpyxl
except ImportError:
    openpyxl = None

def _process_json(input_source, output_dest):
    """Processes JSON input and writes to output_dest."""
    try:
        with open(input_source, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON {input_source}: {e}")
        return False

    if not isinstance(data, list):
        print("Error: JSON root must be a list of objects.")
        return False

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            greeting = generate_greeting(
                candidate_name=item.get('candidate_name'),
                expected_location=item.get('expected_location'),
                past_companies=item.get('past_companies'),
                role=item.get('role')
            )
            item['generated_greeting'] = greeting
            results.append(item)
        except Exception:
            continue

    try:
        with open(output_dest, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error writing JSON {output_dest}: {e}")
        return False

def _process_excel(input_source, output_dest):
    """Processes Excel input and writes to output_dest."""
    if openpyxl is None:
        print("Error: openpyxl is not installed. Cannot process Excel files.")
        return False

    try:
        wb = openpyxl.load_workbook(input_source)
        ws = wb.active
    except Exception as e:
        print(f"Error reading Excel {input_source}: {e}")
        return False

    # Assume row 1 is header
    headers = [cell.value for cell in ws[1]]

    # We look for candidate_name, expected_location, past_companies, role
    header_map = {}
    for i, header in enumerate(headers):
        if header:
            h = str(header).strip().lower()
            if 'name' in h or '姓名' in h or 'candidate_name' in h:
                header_map['candidate_name'] = i
            elif 'location' in h or '地点' in h or '期望地' in h or 'expected_location' in h:
                header_map['expected_location'] = i
            elif 'company' in h or '公司' in h or '厂区' in h or 'past_companies' in h:
                header_map['past_companies'] = i
            elif 'role' in h or '岗位' in h or '职位' in h:
                header_map['role'] = i

    # Add generated_greeting column header
    ws.cell(row=1, column=len(headers) + 1, value="generated_greeting")

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_col=len(headers)), start=2):
        kwargs = {}
        for key, col_idx in header_map.items():
            if col_idx < len(row):
                val = row[col_idx].value
                kwargs[key] = str(val) if val is not None else None

        try:
            greeting = generate_greeting(**kwargs)
            ws.cell(row=row_idx, column=len(headers) + 1, value=greeting)
        except Exception:
            continue

    try:
        wb.save(output_dest)
        return True
    except Exception as e:
        print(f"Error writing Excel {output_dest}: {e}")
        return False

def adapt_and_generate(input_source=None, output_dest=None):
    """
    Zero-configuration adapter that handles file input/output or single default execution.

    Args:
        input_source (str): Path to input file (.json or .xlsx). If None, prints a default greeting.
        output_dest (str): Path to output file. Defaults to stdout if None, or derived from input.
    """
    if input_source is None:
        # One-click, zero-config default run
        greeting = generate_greeting()
        if output_dest is None:
            print("【一键极简模式运行成功】\n" + greeting)
            return greeting
        else:
            try:
                with open(output_dest, 'w', encoding='utf-8') as f:
                    f.write(greeting)
                return True
            except Exception:
                return False

    if not os.path.exists(input_source):
        print(f"Error: Input file {input_source} does not exist.")
        return False

    ext = os.path.splitext(input_source)[1].lower()

    if output_dest is None:
        base, e = os.path.splitext(input_source)
        output_dest = f"{base}_output{e}"

    if ext == '.json':
        return _process_json(input_source, output_dest)
    elif ext in ['.xlsx', '.xls']:
        return _process_excel(input_source, output_dest)
    else:
        print(f"Error: Unsupported file format {ext}. Only .json and .xlsx are supported.")
        return False

if __name__ == '__main__':
    # Very simple CLI logic.
    if len(sys.argv) > 2:
        adapt_and_generate(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        adapt_and_generate(sys.argv[1])
    else:
        adapt_and_generate()

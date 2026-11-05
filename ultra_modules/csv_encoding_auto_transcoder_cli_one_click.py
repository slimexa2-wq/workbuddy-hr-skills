#!/usr/bin/env python3
"""
One-click CSV Encoding Auto-Transcoder CLI
- Zero configuration
- Self-healing for dirty data
- Auto detects GBK, GB18030, UTF-8, UTF-8-SIG
- Outputs UTF-8 CSV, JSON, and Excel seamlessly
"""

import os
import csv
import json
import argparse
from typing import List, Dict, Tuple
try:
    import openpyxl
except ImportError:
    openpyxl = None

def detect_encoding_and_read(file_path: str) -> Tuple[List[Dict[str, str]], List[str], str]:
    """
    Attempts to read the CSV file using common encodings.
    Uses 'replace' for dirty data self-healing.
    Returns: (records, fieldnames, encoding)
    """
    encodings_to_try = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'big5']

    with open(file_path, 'rb') as f:
        raw_data = f.read()

    # if utf-8 and no BOM, it shouldn't be matched as utf-8-sig
    if not raw_data.startswith(b'\xef\xbb\xbf'):
        encodings_to_try = ['utf-8', 'gb18030', 'gbk', 'big5']

    if not raw_data:
        return [], [], 'utf-8'

    best_encoding = 'utf-8'
    min_errors = float('inf')
    best_text = ""

    for enc in encodings_to_try:
        try:
            # First try strict decoding
            text = raw_data.decode(enc, errors='strict')
            best_encoding = enc
            best_text = text
            break
        except UnicodeDecodeError:
            continue
    else:
        # If strict decoding fails for all, fallback to 'replace'
        # To avoid false positives (e.g. interpreting GBK as broken UTF-8 with many \ufffd)
        # we will count errors for all and pick the one with MINIMUM errors.
        for enc in encodings_to_try:
            try:
                text = raw_data.decode(enc, errors='replace')
                errors = text.count('\ufffd')
                if errors < min_errors:
                    min_errors = errors
                    best_encoding = enc
                    best_text = text
            except Exception:
                continue

    from io import StringIO
    f_str = StringIO(best_text)
    reader = csv.reader(f_str)

    rows = list(reader)
    if not rows:
        return [], [], best_encoding

    raw_fieldnames = rows[0]
    fieldnames = []
    for idx, k in enumerate(raw_fieldnames):
        k_str = str(k).strip() if k is not None else f"Unnamed_{idx}"
        if not k_str:
            k_str = f"Unnamed_{idx}"
        # ensure unique
        original_k_str = k_str
        counter = 1
        while k_str in fieldnames:
            k_str = f"{original_k_str}_{counter}"
            counter += 1
        fieldnames.append(k_str)

    records = []
    for row in rows[1:]:
        clean_row = {}
        for idx, clean_key in enumerate(fieldnames):
            if idx < len(row):
                val = row[idx]
                clean_row[clean_key] = str(val).strip() if val is not None else ''
            else:
                clean_row[clean_key] = ''
        records.append(clean_row)

    return records, fieldnames, best_encoding

def clean_for_excel(text: str) -> str:
    """Removes control characters that break openpyxl."""
    if not isinstance(text, str):
        return text
    return ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')

def export_to_csv(records: List[Dict[str, str]], fieldnames: List[str], output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
        writer.writerows(records)

def export_to_json(records: List[Dict[str, str]], output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def export_to_excel(records: List[Dict[str, str]], fieldnames: List[str], output_path: str) -> None:
    if openpyxl is None:
        print(f"Warning: openpyxl not installed, skipping Excel export for {output_path}")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"

    if fieldnames:
        cleaned_headers = [clean_for_excel(h) for h in fieldnames]
        ws.append(cleaned_headers)

    for row in records:
        ws.append([clean_for_excel(row.get(h, '')) for h in fieldnames])

    wb.save(output_path)

def process_file(file_path: str, formats: List[str] = None) -> None:
    if formats is None:
        formats = ['csv', 'json', 'excel']

    print(f"Processing {file_path}...")
    records, fieldnames, encoding = detect_encoding_and_read(file_path)
    print(f"  Detected encoding: {encoding}, {len(records)} records found.")

    base_name = os.path.splitext(file_path)[0]

    if 'csv' in formats:
        out_csv = f"{base_name}_cleaned.csv"
        export_to_csv(records, fieldnames, out_csv)
        print(f"  Exported {out_csv}")

    if 'json' in formats:
        out_json = f"{base_name}_cleaned.json"
        export_to_json(records, out_json)
        print(f"  Exported {out_json}")

    if 'excel' in formats or 'xlsx' in formats:
        out_excel = f"{base_name}_cleaned.xlsx"
        export_to_excel(records, fieldnames, out_excel)
        if openpyxl is not None:
            print(f"  Exported {out_excel}")

def main():
    parser = argparse.ArgumentParser(description="One-click CSV encoding auto-transcoder and cleaner.")
    parser.add_argument('files', nargs='*', help="CSV files to process. If empty, processes all CSVs in current directory.")
    parser.add_argument('--formats', nargs='+', default=['csv', 'json', 'excel'], help="Output formats (csv, json, excel).")

    args = parser.parse_args()

    files_to_process = args.files

    if not files_to_process:
        files_to_process = [f for f in os.listdir('.') if f.lower().endswith('.csv') and not f.lower().endswith('_cleaned.csv')]
        if not files_to_process:
            print("No CSV files found in the current directory.")
            return

    for f in files_to_process:
        process_file(f, args.formats)

if __name__ == "__main__":
    main()

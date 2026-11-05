import argparse
import json
import os
import tempfile
import openpyxl
from typing import Optional, Dict, Any, Union

def process_excel_guard(input_path: str, output_path: Optional[str] = None, output_mode: str = 'excel') -> Dict[str, Any]:
    """
    Process the Excel file: removes all comments and fills empty cells with 0.
    Returns a report of actions taken.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    wb = openpyxl.load_workbook(input_path)

    report = {
        "comments_removed": 0,
        "nulls_filled_with_zero": 0,
        "sheets_processed": 0
    }

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        report["sheets_processed"] += 1

        # Determine the actual data range to process to avoid processing the whole empty sheet
        # A simple approach: iterate over all rows/cols that are within the dimensions
        max_row = ws.max_row
        max_col = ws.max_column

        for row in range(1, max_row + 1):
            for col in range(1, max_col + 1):
                cell = ws.cell(row=row, column=col)

                # Check for comment
                if cell.comment:
                    cell.comment = None
                    report["comments_removed"] += 1

                # Check for null/empty and fill with 0
                # We only fill with 0 if it's genuinely empty (value is None)
                # But since Excel might consider cells outside data range as max_row/max_col,
                # we'll fill any cell that returns None within this bounding box.
                if cell.value is None:
                    cell.value = 0
                    report["nulls_filled_with_zero"] += 1

    if output_mode == 'excel':
        # Default save to same dir with '_guarded' suffix if no output_path
        if not output_path:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_guarded{ext}"

        wb.save(output_path)
        report["output_file"] = output_path
    elif output_mode == 'json':
        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}_report.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4)
        report["output_file"] = output_path

    wb.close()
    return report

def _create_dummy_excel(path: str):
    """Creates a dummy Excel file with some dirty data (comments and nulls) for zero-config run."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Data"

    # Add some normal data
    ws['A1'] = "Name"
    ws['B1'] = "Value1"
    ws['C1'] = "Value2"

    ws['A2'] = "Item A"
    ws['B2'] = 100
    # C2 is null

    ws['A3'] = "Item B"
    # B3 is null
    ws['C3'] = 300

    # Add comments
    from openpyxl.comments import Comment
    comment = Comment("This is a review comment", "Author")
    ws['B2'].comment = comment

    wb.save(path)
    wb.close()

def main():
    parser = argparse.ArgumentParser(description="Zero Comment & Null Guard CLI for Excel files.")
    parser.add_argument("-i", "--input", type=str, default=None, help="Input Excel file path. If omitted, generates and processes a dummy file.")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file path.")
    parser.add_argument("-m", "--mode", type=str, choices=['excel', 'json'], default='excel', help="Output mode: 'excel' (saves cleaned excel) or 'json' (saves report only).")

    args = parser.parse_args()

    cleanup_dummy = False
    input_file = args.input

    if not input_file:
        # Zero-config fallback: create a dummy file in a temp dir
        temp_dir = tempfile.mkdtemp()
        input_file = os.path.join(temp_dir, "dummy_input.xlsx")
        _create_dummy_excel(input_file)
        cleanup_dummy = True
        print(f"[Auto-Fallback] No input provided. Generated dummy file at {input_file}")

    try:
        print(f"Processing: {input_file}")
        report = process_excel_guard(input_file, args.output, args.mode)
        print(f"Success! Report:\n{json.dumps(report, indent=2)}")
    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        # Optionally clean up dummy file if we generated it, but we might want to keep it
        # to show the user what happened. Let's keep it for demonstration but note it.
        if cleanup_dummy:
            print(f"[Note] Dummy input and output files are kept in {os.path.dirname(input_file)}")

if __name__ == "__main__":
    main()

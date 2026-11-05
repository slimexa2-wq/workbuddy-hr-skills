import json
import argparse
import sys
import re

class XlsxFormulaHealerOneClick:
    def __init__(self, fallback_value=0):
        self.fallback_value = fallback_value
        self.error_types = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"}

    def heal_value(self, val):
        if isinstance(val, str):
            val_upper = val.upper()
            if val_upper in self.error_types or re.search(r'circular', val, re.IGNORECASE):
                return self.fallback_value

            stripped = val.strip()
            # Try to convert text to number
            if re.match(r'^-?\d+(\.\d+)?$', stripped):
                try:
                    if '.' in stripped:
                        return float(stripped)
                    return int(stripped)
                except ValueError:
                    return val
        return val

    def heal_data(self, data):
        """
        Heal list of dicts, list of lists, or flat lists.
        """
        if not data:
            return data

        if isinstance(data, list):
            if all(isinstance(row, dict) for row in data):
                return [{k: self.heal_value(v) for k, v in row.items()} for row in data]
            elif all(isinstance(row, list) for row in data):
                return [[self.heal_value(cell) for cell in row] for row in data]
            else:
                return [self.heal_value(cell) for cell in data]
        elif isinstance(data, dict):
            return {k: self.heal_value(v) for k, v in data.items()}
        return data

def process_file(input_file, output_file=None):
    """
    Process JSON or Excel (xlsx) input and write healed output. Zero configuration.
    """
    try:
        healer = XlsxFormulaHealerOneClick()

        if input_file.lower().endswith('.xlsx'):
            import openpyxl
            wb = openpyxl.load_workbook(input_file, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is not None:
                            healed_val = healer.heal_value(str(cell.value) if isinstance(cell.value, str) else cell.value)
                            if isinstance(healed_val, (int, float)):
                                cell.value = healed_val
                            elif healed_val != cell.value:
                                cell.value = healed_val

            out_path = output_file if output_file else input_file.replace('.xlsx', '_healed.xlsx')
            wb.save(out_path)

        else:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            healed_data = healer.heal_data(data)

            out_path = output_file if output_file else input_file.replace('.json', '_healed.json')

            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(healed_data, f, ensure_ascii=False, indent=2)

        print(f"Successfully healed data and saved to {out_path}")
        return True
    except Exception as e:
        print(f"Error processing file {input_file}: {str(e)}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="One-click Excel Formula Healer CLI")
    parser.add_argument('input', nargs='?', default=None, help="Input JSON file path")
    parser.add_argument('-o', '--output', default=None, help="Output JSON file path")

    args = parser.parse_args()

    if args.input:
        process_file(args.input, args.output)
    else:
        # Default behavior: process from stdin to stdout if no args,
        # or print a helpful message without failing strictly.
        if not sys.stdin.isatty():
            try:
                input_data = sys.stdin.read()
                data = json.loads(input_data)
                healer = XlsxFormulaHealerOneClick()
                healed_data = healer.heal_data(data)
                print(json.dumps(healed_data, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"Error processing stdin: {str(e)}", file=sys.stderr)
                sys.exit(1)
        else:
            print("No input provided. Usage: xlsx_formula_healer_cli_one_click.py [input.json] [-o output.json]")
            print("Example data output as fallback:")
            demo_data = [{"id": 1, "value": "#REF!"}, {"id": 2, "value": " 42.5 "}]
            healer = XlsxFormulaHealerOneClick()
            print(json.dumps(healer.heal_data(demo_data), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

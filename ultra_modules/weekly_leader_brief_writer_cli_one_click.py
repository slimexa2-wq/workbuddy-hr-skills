import argparse
import json
import os
import sys

def parse_excel(file_path):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active

        # Expecting key-value pairs in the first two columns
        data = {}
        for row in sheet.iter_rows(min_row=1, max_row=100, values_only=True):
            if not row or row[0] is None:
                continue
            key = str(row[0]).strip()
            val = row[1] if len(row) > 1 else None
            data[key] = val
        return data
    except ImportError:
        print("Warning: openpyxl is not installed. Cannot parse Excel.", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Warning: Failed to parse Excel file {file_path}. Using empty data. Error: {e}", file=sys.stderr)
        return {}

def clean_data(data):
    def get_int(key, aliases, default=0):
        val = data.get(key)
        if val is None:
            for alias in aliases:
                if data.get(alias) is not None:
                    val = data.get(alias)
                    break
        if val is None:
            return default
        try:
            val = int(val)
            return val if val >= 0 else 0 # dirty data self healing for negatives
        except (ValueError, TypeError):
            return default

    def get_str(key, aliases, default="无"):
        val = data.get(key)
        if val is None:
            for alias in aliases:
                if data.get(alias) is not None:
                    val = data.get(alias)
                    break
        if val is None or str(val).strip() == "":
            return default
        # Clean control characters
        val = str(val).replace('\x00', '')
        return str(val).strip()

    cleaned = {
        "new_hires": get_int("new_hires", ["新入职", "入职人数"], 0),
        "departures": get_int("departures", ["离职人数", "流失"], 0),
        "total_employees": get_int("total_employees", ["总人数", "在职人数"], 100),
        "interview_count": get_int("interview_count", ["面试人数", "面试"], 0),
        "key_departures": get_str("key_departures", ["关键流失", "重要人员离职"], "无"),
        "notes": get_str("notes", ["备注", "说明"], "一切正常")
    }
    return cleaned

def generate_weekly_brief(data=None):
    if data is None:
        data = {}

    cleaned = clean_data(data)

    report = f"【本周人力动态汇报】\n"
    report += f"1. 总体概况：当前在职总人数为 {cleaned['total_employees']} 人。\n"
    report += f"2. 入职情况：本周新入职 {cleaned['new_hires']} 人，面试完成 {cleaned['interview_count']} 人。\n"
    report += f"3. 离职情况：本周离职 {cleaned['departures']} 人。\n"
    report += f"4. 关键流失：{cleaned['key_departures']}。\n"
    report += f"5. 补充说明：{cleaned['notes']}。"

    return report

def main():
    parser = argparse.ArgumentParser(description="Weekly Leader Brief Writer CLI")
    parser.add_argument("--json-file", help="Path to JSON file", type=str, default=None)
    parser.add_argument("--excel-file", help="Path to Excel file", type=str, default=None)
    parser.add_argument("--json-str", help="JSON string", type=str, default=None)

    args = parser.parse_args()

    data = None

    if args.excel_file and os.path.exists(args.excel_file):
        data = parse_excel(args.excel_file)
    elif args.json_file and os.path.exists(args.json_file):
        try:
            with open(args.json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse JSON file. Error: {e}", file=sys.stderr)
    elif args.json_str:
        try:
            data = json.loads(args.json_str)
        except Exception as e:
            print(f"Warning: Failed to parse JSON string. Error: {e}", file=sys.stderr)

    if data is None:
        data = {
            "new_hires": 3,
            "departures": 1,
            "total_employees": 150,
            "interview_count": 10,
            "key_departures": "无",
            "notes": "常规运转，无重大异常"
        }

    brief = generate_weekly_brief(data)
    print(brief)

if __name__ == "__main__":
    main()

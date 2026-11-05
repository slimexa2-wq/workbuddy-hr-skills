import json
import csv
import os
import sys

def parse_project_requirements(data=None):
    if data is None:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # Defaults
    status = data.get('status', 'Unknown')
    count = data.get('count', 0)

    # Dirty data correction
    if not isinstance(count, int):
        try:
            count = int(count)
        except (ValueError, TypeError):
            count = 0

    if not isinstance(status, str):
        status = str(status)

    status = status.strip()
    if not status:
        status = 'Unknown'

    return {
        'type': 'project_requirements',
        'status': status,
        'count': count
    }

def parse_student_workers(data=None):
    if data is None:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # Defaults
    department = data.get('department', 'General')
    headcount = data.get('headcount', 0)

    # Dirty data correction
    if not isinstance(headcount, int):
        try:
            headcount = int(headcount)
        except (ValueError, TypeError):
            headcount = 0

    if not isinstance(department, str):
        department = str(department)

    department = department.strip()
    if not department:
        department = 'General'

    return {
        'type': 'student_workers',
        'department': department,
        'headcount': headcount
    }

def parse_campus_recruitment(data=None):
    if data is None:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # Defaults
    role = data.get('role', 'Any')
    performance = data.get('performance', 'N/A')

    # Dirty data correction
    if not isinstance(role, str):
        role = str(role)
    role = role.strip()
    if not role:
        role = 'Any'

    if not isinstance(performance, str):
        performance = str(performance)
    performance = performance.strip()
    if not performance:
        performance = 'N/A'

    return {
        'type': 'campus_recruitment',
        'role': role,
        'performance': performance
    }

def synthesize_reports(proj_data=None, sw_data=None, cr_data=None):
    proj_report = parse_project_requirements(proj_data)
    sw_report = parse_student_workers(sw_data)
    cr_report = parse_campus_recruitment(cr_data)

    return [proj_report, sw_report, cr_report]

def output_to_json(data, filepath):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def output_to_csv(data, filepath):
    try:
        if not data:
            return False

        # Collect all unique keys
        keys = []
        for row in data:
            for k in row.keys():
                if k not in keys:
                    keys.append(k)

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        return True
    except Exception:
        return False

def run_reports_one_click(output_dir='.'):
    # Generates standard reports with defaults
    reports = synthesize_reports()

    json_path = os.path.join(output_dir, 'monday_reports.json')
    csv_path = os.path.join(output_dir, 'monday_reports.csv')

    json_ok = output_to_json(reports, json_path)
    csv_ok = output_to_csv(reports, csv_path)

    return {
        'success': json_ok and csv_ok,
        'data': reports,
        'json_path': json_path,
        'csv_path': csv_path
    }

if __name__ == '__main__': # pragma: no cover
    # Zero-parameter CLI block
    print("Generating Monday 3-Reports...")
    result = run_reports_one_click()
    if result['success']:
        print(f"Reports generated successfully!")
        print(f"JSON: {result['json_path']}")
        print(f"CSV:  {result['csv_path']}")
    else:
        print("Failed to write report files.", file=sys.stderr)
        sys.exit(1)

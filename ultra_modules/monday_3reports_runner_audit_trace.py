class AuditLogger:
    def __init__(self):
        self.logs = []

    def log(self, entity_type, entity_id, field, original, corrected, reason):
        self.logs.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field": field,
            "original": original,
            "corrected": corrected,
            "reason": reason
        })

def run_monday_reports_with_audit(project_reqs=None, student_workers=None, campus_perf=None):
    """
    Synthesize the 3 weekly Monday reports: Project Requirements, Student Workers, and Campus Recruitment Performance.
    Implements auto-fault-tolerance, default arguments, silent data cleaning (deduplication, boundary normalization, etc).
    Also keeps a silent audit trace of each transformation/correction.
    Returns a tuple: (clean_result, audit_trace)
    """
    audit = AuditLogger()

    if not isinstance(project_reqs, list):
        audit.log("global", "project_reqs", "type", type(project_reqs).__name__, "list", "Invalid type, defaulted to empty list")
        project_reqs = []

    if not isinstance(student_workers, list):
        audit.log("global", "student_workers", "type", type(student_workers).__name__, "list", "Invalid type, defaulted to empty list")
        student_workers = []

    if not isinstance(campus_perf, list):
        audit.log("global", "campus_perf", "type", type(campus_perf).__name__, "list", "Invalid type, defaulted to empty list")
        campus_perf = []

    result = {
        "project_requirements": [],
        "student_workers": [],
        "campus_recruitment_performance": [],
        "summary": {
            "total_projects": 0,
            "total_students": 0,
            "total_campus_hires": 0
        }
    }

    # Deduplication sets
    seen_projects = set()
    seen_students = set()
    seen_employees = set()

    # 1. Process Project Requirements
    for i, req in enumerate(project_reqs):
        if not isinstance(req, dict):
            audit.log("project_reqs", f"index_{i}", "type", type(req).__name__, "skipped", "Entry is not a dictionary")
            continue

        project_name = str(req.get("project_name", "Unknown Project")).strip() or "Unknown Project"
        if req.get("project_name") != project_name:
            audit.log("project_reqs", f"index_{i}", "project_name", req.get("project_name"), project_name, "Normalized missing or invalid project name")

        if project_name in seen_projects and project_name != "Unknown Project":
            audit.log("project_reqs", f"index_{i}", "duplicate", project_name, "skipped", "Duplicate project name found")
            continue
        if project_name != "Unknown Project":
            seen_projects.add(project_name)

        status = str(req.get("status", "Pending")).strip() or "Pending"
        if req.get("status") != status:
            audit.log("project_reqs", project_name, "status", req.get("status"), status, "Normalized status")

        raw_headcount = req.get("headcount", 0)
        headcount = 0
        try:
            headcount = max(0, int(raw_headcount))
        except (ValueError, TypeError):
            pass
        if raw_headcount != headcount:
            audit.log("project_reqs", project_name, "headcount", raw_headcount, headcount, "Fixed invalid or negative headcount")

        result["project_requirements"].append({
            "project_name": project_name,
            "status": status,
            "headcount": headcount
        })
        result["summary"]["total_projects"] += 1

    # 2. Process Student Workers
    for i, student in enumerate(student_workers):
        if not isinstance(student, dict):
            audit.log("student_workers", f"index_{i}", "type", type(student).__name__, "skipped", "Entry is not a dictionary")
            continue

        name = str(student.get("name", "Unknown Student")).strip() or "Unknown Student"
        if student.get("name") != name:
            audit.log("student_workers", f"index_{i}", "name", student.get("name"), name, "Normalized missing or invalid student name")

        if name in seen_students and name != "Unknown Student":
            audit.log("student_workers", f"index_{i}", "duplicate", name, "skipped", "Duplicate student name found")
            continue
        if name != "Unknown Student":
            seen_students.add(name)

        department = str(student.get("department", "Unassigned")).strip() or "Unassigned"
        if student.get("department") != department:
            audit.log("student_workers", name, "department", student.get("department"), department, "Normalized department name")

        raw_hours = student.get("working_hours", 0.0)
        working_hours = 0.0
        try:
            working_hours = max(0.0, float(raw_hours))
        except (ValueError, TypeError):
            pass
        if raw_hours != working_hours:
            audit.log("student_workers", name, "working_hours", raw_hours, working_hours, "Fixed invalid or negative working hours")

        result["student_workers"].append({
            "name": name,
            "department": department,
            "working_hours": working_hours
        })
        result["summary"]["total_students"] += 1

    # 3. Process Campus Recruitment Performance
    valid_scores = {"S", "A", "B", "C", "D"}
    for i, perf in enumerate(campus_perf):
        if not isinstance(perf, dict):
            audit.log("campus_perf", f"index_{i}", "type", type(perf).__name__, "skipped", "Entry is not a dictionary")
            continue

        emp_name = str(perf.get("employee_name", "Unknown Employee")).strip() or "Unknown Employee"
        if perf.get("employee_name") != emp_name:
            audit.log("campus_perf", f"index_{i}", "employee_name", perf.get("employee_name"), emp_name, "Normalized missing or invalid employee name")

        if emp_name in seen_employees and emp_name != "Unknown Employee":
            audit.log("campus_perf", f"index_{i}", "duplicate", emp_name, "skipped", "Duplicate employee name found")
            continue
        if emp_name != "Unknown Employee":
            seen_employees.add(emp_name)

        raw_score = perf.get("performance_score", "C")
        score = str(raw_score).strip().upper()
        if score not in valid_scores:
            score = "C"
        if raw_score != score:
            audit.log("campus_perf", emp_name, "performance_score", raw_score, score, "Normalized invalid performance score to default C")

        feedback = str(perf.get("feedback", "")).strip()
        if perf.get("feedback") != feedback:
            audit.log("campus_perf", emp_name, "feedback", perf.get("feedback"), feedback, "Trimmed whitespace or handled missing feedback")

        result["campus_recruitment_performance"].append({
            "employee_name": emp_name,
            "performance_score": score,
            "feedback": feedback
        })
        result["summary"]["total_campus_hires"] += 1

    return result, audit.logs

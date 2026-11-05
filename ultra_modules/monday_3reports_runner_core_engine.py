def synthesize_monday_reports(project_reqs=None, student_workers=None, campus_perf=None):
    """
    Synthesize the 3 weekly Monday reports: Project Requirements, Student Workers, and Campus Recruitment Performance.
    Implements auto-fault-tolerance, default arguments, and silent data cleaning.
    """

    # 1. Handle missing arguments (Defaulting to empty lists if None or invalid types)
    if not isinstance(project_reqs, list):
        project_reqs = []
    if not isinstance(student_workers, list):
        student_workers = []
    if not isinstance(campus_perf, list):
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

    # 2. Process and clean Project Requirements
    for req in project_reqs:
        if not isinstance(req, dict):
            continue

        # Silent clean
        cleaned_req = {
            "project_name": str(req.get("project_name", "Unknown Project")).strip() or "Unknown Project",
            "status": str(req.get("status", "Pending")).strip() or "Pending",
            "headcount": req.get("headcount", 0)
        }

        # Clean headcount
        try:
            cleaned_req["headcount"] = max(0, int(cleaned_req["headcount"]))
        except (ValueError, TypeError):
            cleaned_req["headcount"] = 0

        result["project_requirements"].append(cleaned_req)
        result["summary"]["total_projects"] += 1

    # 3. Process and clean Student Workers
    for student in student_workers:
        if not isinstance(student, dict):
            continue

        cleaned_student = {
            "name": str(student.get("name", "Unknown Student")).strip() or "Unknown Student",
            "department": str(student.get("department", "Unassigned")).strip() or "Unassigned",
            "working_hours": student.get("working_hours", 0.0)
        }

        # Clean working hours
        try:
            cleaned_student["working_hours"] = max(0.0, float(cleaned_student["working_hours"]))
        except (ValueError, TypeError):
            cleaned_student["working_hours"] = 0.0

        result["student_workers"].append(cleaned_student)
        result["summary"]["total_students"] += 1

    # 4. Process and clean Campus Recruitment Performance
    for perf in campus_perf:
        if not isinstance(perf, dict):
            continue

        cleaned_perf = {
            "employee_name": str(perf.get("employee_name", "Unknown Employee")).strip() or "Unknown Employee",
            "performance_score": perf.get("performance_score", "C"),
            "feedback": str(perf.get("feedback", "")).strip()
        }

        # Clean performance score (Assume valid scores are S, A, B, C, D)
        valid_scores = {"S", "A", "B", "C", "D"}
        score = str(cleaned_perf["performance_score"]).strip().upper()
        if score not in valid_scores:
            score = "C"
        cleaned_perf["performance_score"] = score

        result["campus_recruitment_performance"].append(cleaned_perf)
        result["summary"]["total_campus_hires"] += 1

    return result

import json

def generate_plain_explanation(report_data=None, output_format="markdown"):
    """
    Transforms the complex output of the Monday 3 Reports into a simple,
    plain-text explanation card for business users.

    Zero-configuration, fault-tolerant, and handles missing/dirty data gracefully.
    """

    # 1. Fault Tolerance: Ensure report_data is a dictionary
    if not isinstance(report_data, dict):
        report_data = {}

    # 2. Fault Tolerance: Ensure output_format is valid
    valid_formats = {"markdown", "html", "json"}
    if not isinstance(output_format, str) or output_format.lower().strip() not in valid_formats:
        output_format = "markdown"
    else:
        output_format = output_format.lower().strip()

    # 3. Safe Extraction of Summary Metrics
    summary = report_data.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    try:
        total_projects = max(0, int(summary.get("total_projects", 0)))
    except (ValueError, TypeError):
        total_projects = 0

    try:
        total_students = max(0, int(summary.get("total_students", 0)))
    except (ValueError, TypeError):
        total_students = 0

    try:
        total_campus_hires = max(0, int(summary.get("total_campus_hires", 0)))
    except (ValueError, TypeError):
        total_campus_hires = 0

    # 4. Safe Extraction of Details
    project_reqs = report_data.get("project_requirements", [])
    if not isinstance(project_reqs, list):
        project_reqs = []

    student_workers = report_data.get("student_workers", [])
    if not isinstance(student_workers, list):
        student_workers = []

    campus_perf = report_data.get("campus_recruitment_performance", [])
    if not isinstance(campus_perf, list):
        campus_perf = []

    # Calculate some dynamic simple texts
    active_projects = 0
    total_headcount = 0
    for req in project_reqs:
        if isinstance(req, dict):
            status = str(req.get("status", "")).strip().lower()
            if status in ["active", "in progress", "open"]:
                active_projects += 1
            try:
                total_headcount += max(0, int(req.get("headcount", 0)))
            except (ValueError, TypeError):
                pass

    total_student_hours = 0.0
    for student in student_workers:
        if isinstance(student, dict):
            try:
                total_student_hours += max(0.0, float(student.get("working_hours", 0.0)))
            except (ValueError, TypeError):
                pass

    high_performers = 0
    for perf in campus_perf:
        if isinstance(perf, dict):
            score = str(perf.get("performance_score", "")).strip().upper()
            if score in ["S", "A"]:
                high_performers += 1

    # 5. Build Content Data
    content_data = {
        "title": "每周一报表极简摘要",
        "greeting": "各位领导/同事，本周最新的人力资源数据摘要如下，请查阅：",
        "section_projects": f"【项目需求】本周共追踪到 {total_projects} 个项目需求。其中活跃项目 {active_projects} 个，总计需要 {total_headcount} 人。",
        "section_students": f"【学生工】本周共有 {total_students} 名学生工在岗，累计贡献工时 {total_student_hours:.1f} 小时。",
        "section_campus": f"【校招绩效】本周共评估了 {total_campus_hires} 名存量校招生的绩效，其中表现优异（S/A级）的有 {high_performers} 人。",
        "conclusion": "只需一秒钟，核心数据尽在掌握！如需详细数据，请查看原始报表附件。"
    }

    # 6. Format Output
    if output_format == "json":
        return json.dumps(content_data, ensure_ascii=False, indent=2)

    elif output_format == "html":
        html_str = f"""
<div class="monday-report-card" style="font-family: sans-serif; border: 1px solid #ddd; padding: 20px; border-radius: 8px; max-width: 600px;">
    <h2 style="color: #333; margin-top: 0;">{content_data['title']}</h2>
    <p style="color: #666;">{content_data['greeting']}</p>

    <div style="margin: 15px 0;">
        <p style="margin: 8px 0; background: #f9f9f9; padding: 10px; border-left: 4px solid #4CAF50;">{content_data['section_projects']}</p>
        <p style="margin: 8px 0; background: #f9f9f9; padding: 10px; border-left: 4px solid #2196F3;">{content_data['section_students']}</p>
        <p style="margin: 8px 0; background: #f9f9f9; padding: 10px; border-left: 4px solid #FF9800;">{content_data['section_campus']}</p>
    </div>

    <p style="color: #999; font-size: 0.9em; border-top: 1px solid #eee; padding-top: 10px;">{content_data['conclusion']}</p>
</div>
        """
        return html_str.strip()

    else: # markdown (default)
        md_str = f"""
# {content_data['title']}

{content_data['greeting']}

> **{content_data['section_projects']}**
>
> **{content_data['section_students']}**
>
> **{content_data['section_campus']}**

*{content_data['conclusion']}*
        """
        return md_str.strip()

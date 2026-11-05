import math
from typing import Dict, Any, List

def format_monday_reports(project_needs: Any = None, student_workers: Any = None, campus_recruitment: Any = None) -> Dict[str, Any]:
    """
    Weekly Monday 3 reports runner export formatter.
    Generates a consolidated dataset and a 3-line concise briefing for WeChat/Feishu.
    Ensures zero comments and handles NaN/None in numerical cells.
    """

    # Self-healing missing parameters
    if project_needs is None:
        project_needs = []
    if student_workers is None:
        student_workers = []
    if campus_recruitment is None:
        campus_recruitment = []

    # Dirty data self-healing: force to list if single dict is passed
    if isinstance(project_needs, dict):
        project_needs = [project_needs]
    if isinstance(student_workers, dict):
        student_workers = [student_workers]
    if isinstance(campus_recruitment, dict):
        campus_recruitment = [campus_recruitment]

    # Dirty data self-healing: drop non-list inputs if they are totally invalid (e.g. integer)
    if not isinstance(project_needs, list):
        project_needs = []
    if not isinstance(student_workers, list):
        student_workers = []
    if not isinstance(campus_recruitment, list):
        campus_recruitment = []

    def cleanse_data(dataset: List[Any]) -> List[Dict[str, Any]]:
        cleansed = []
        for item in dataset:
            if not isinstance(item, dict):
                continue # ignore non-dict items
            cleansed_item = {}
            for k, v in item.items():
                if isinstance(v, (int, float)):
                    if math.isnan(v):
                        cleansed_item[k] = 0
                    else:
                        cleansed_item[k] = v
                elif v is None:
                    cleansed_item[k] = 0 # Handle None as 0 for numerical cells logic
                else:
                    cleansed_item[k] = v
            cleansed_item["comments"] = 0
            cleansed.append(cleansed_item)
        return cleansed

    clean_project_needs = cleanse_data(project_needs)
    clean_student_workers = cleanse_data(student_workers)
    clean_campus_recruitment = cleanse_data(campus_recruitment)

    # Generate 3-line briefing text
    project_needs_count = len(clean_project_needs)
    student_workers_count = len(clean_student_workers)
    campus_recruitment_count = len(clean_campus_recruitment)

    briefing = (
        f"项目需求报表已就绪：共 {project_needs_count} 条数据\n"
        f"学生工报表已就绪：共 {student_workers_count} 条数据\n"
        f"校招绩效报表已就绪：共 {campus_recruitment_count} 条数据"
    )

    return {
        "project_needs": clean_project_needs,
        "student_workers": clean_student_workers,
        "campus_recruitment": clean_campus_recruitment,
        "briefing": briefing
    }

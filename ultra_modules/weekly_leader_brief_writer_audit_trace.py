import re
from datetime import datetime
from typing import List, Dict, Any, Tuple

class WeeklyLeaderBriefWriter:
    def __init__(self):
        self.audit_log: List[str] = []

    def _log(self, message: str) -> None:
        """Silently record steps in the audit trail."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.audit_log.append(f"[{timestamp}] {message}")

    def _clean_and_deduplicate(self, data: List[Dict[str, Any]], data_type: str) -> List[Dict[str, Any]]:
        """Clean dirty data, handle missing defaults, and deduplicate by ID."""
        cleaned_data = []
        seen_ids = set()

        if not isinstance(data, list):
            self._log(f"Warning: {data_type} data is not a list. Falling back to empty list.")
            return []

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                self._log(f"Warning: Item at index {index} in {data_type} is not a dictionary. Skipping.")
                continue

            # Default fallbacks
            emp_id = str(item.get("id", f"unknown_id_{index}")).strip()
            name = str(item.get("name", "Unknown")).strip()
            dept = str(item.get("department", "Unassigned")).strip()

            # Deduplication
            if emp_id in seen_ids:
                self._log(f"Deduplicated {data_type} record for ID: {emp_id}, Name: {name}")
                continue

            seen_ids.add(emp_id)

            # Normalization using regex for case-insensitive replacement if needed
            # (Though here we mainly want consistent casing/spacing)
            # Normalizing status - just string conversion, non-destructive
            status = str(item.get("status", "pending")).strip()

            cleaned_item = {
                "id": emp_id,
                "name": name,
                "department": dept,
                "status": status,
                **{k: v for k, v in item.items() if k not in ["id", "name", "department", "status"]}
            }
            cleaned_data.append(cleaned_item)
            self._log(f"Processed valid {data_type} record: ID {emp_id}, Name: {name}, Dept: {dept}")

        return cleaned_data

    def generate_weekly_hr_brief(self,
                                 onboarding_data: List[Dict[str, Any]] = None,
                                 offboarding_data: List[Dict[str, Any]] = None,
                                 report_date: str = None) -> Dict[str, Any]:
        """
        Generate a fixed-format weekly HR report on onboarding and offboarding data.
        Returns a dictionary with 'report' and 'audit_log'.
        """
        self.audit_log = [] # Reset audit log for this generation
        self._log("Started generating weekly HR brief.")

        # 1. Zero-configuration fault tolerance and sensible defaults
        if onboarding_data is None:
            self._log("Onboarding data is missing. Using default empty list.")
            onboarding_data = []

        if offboarding_data is None:
            self._log("Offboarding data is missing. Using default empty list.")
            offboarding_data = []

        if not report_date:
            report_date = datetime.now().strftime("%Y-%m-%d")
            self._log(f"Report date is missing. Defaulting to current date: {report_date}")

        # 2. Dirty data self-healing and deduplication
        clean_onboarding = self._clean_and_deduplicate(onboarding_data, "onboarding")
        clean_offboarding = self._clean_and_deduplicate(offboarding_data, "offboarding")

        # 3. Calculate statistics
        onboarding_count = len(clean_onboarding)
        offboarding_count = len(clean_offboarding)
        net_change = onboarding_count - offboarding_count
        self._log(f"Calculated statistics: Onboarding={onboarding_count}, Offboarding={offboarding_count}, Net={net_change}")

        # 4. Generate report text (Fixed Format)
        report_lines = [
            f"【祥能人力周度在离职数据汇总汇报】",
            f"汇报日期: {report_date}",
            f"--------------------------------------------------",
            f"本周总计入职人数: {onboarding_count}人",
            f"本周总计离职人数: {offboarding_count}人",
            f"本周人员净增减: {net_change}人",
            f"--------------------------------------------------",
            f"[入职明细]"
        ]

        if not clean_onboarding:
            report_lines.append("本周无新入职人员。")
        else:
            for emp in clean_onboarding:
                report_lines.append(f"- {emp['name']} (ID: {emp['id']}) - 部门: {emp['department']} - 状态: {emp['status']}")

        report_lines.append(f"--------------------------------------------------")
        report_lines.append(f"[离职明细]")

        if not clean_offboarding:
            report_lines.append("本周无离职人员。")
        else:
            for emp in clean_offboarding:
                report_lines.append(f"- {emp['name']} (ID: {emp['id']}) - 部门: {emp['department']} - 状态: {emp['status']}")

        report_lines.append(f"==================================================")
        report_lines.append("汇报完毕。")

        final_report = "\n".join(report_lines)
        self._log("Successfully generated report text.")

        return {
            "report": final_report,
            "audit_log": list(self.audit_log)
        }

# Wrapper function for ease of use
def generate_weekly_hr_brief(onboarding_data=None, offboarding_data=None, report_date=None):
    writer = WeeklyLeaderBriefWriter()
    return writer.generate_weekly_hr_brief(onboarding_data, offboarding_data, report_date)

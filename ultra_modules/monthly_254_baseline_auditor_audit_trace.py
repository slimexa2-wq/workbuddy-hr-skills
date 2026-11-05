import logging
import datetime
from typing import List, Dict, Any, Tuple, Optional

class BaselineAuditorEngine:
    def __init__(self):
        self.audit_trace = []
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger("BaselineAuditor")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_audit(self, step: str, details: Any):
        trace_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "step": step,
            "details": details
        }
        self.audit_trace.append(trace_entry)
        self.logger.debug(f"Audit Trace: {step} - {details}")

    def get_audit_trace(self) -> List[Dict]:
        return self.audit_trace

    def clear_audit_trace(self):
        self.audit_trace = []

    def _heal_data(self, record: Dict) -> Dict:
        healed_record = record.copy()

        # Self-healing: missing ID
        if "id" not in healed_record or not healed_record["id"]:
            healed_record["id"] = "unknown_" + str(hash(str(healed_record)))
            self.log_audit("data_healing", {"record": record, "healed_field": "id", "new_value": healed_record["id"]})

        # Self-healing: employment days
        if "employment_days" not in healed_record:
            if "hire_date" in healed_record and healed_record["hire_date"]:
                try:
                    hire_date = datetime.datetime.strptime(healed_record["hire_date"], "%Y-%m-%d")
                    healed_record["employment_days"] = (datetime.datetime.now() - hire_date).days
                    self.log_audit("data_healing", {"record": record, "healed_field": "employment_days", "calculated": True})
                except ValueError:
                    healed_record["employment_days"] = 0
                    self.log_audit("data_healing", {"record": record, "healed_field": "employment_days", "defaulted": 0})
            else:
                healed_record["employment_days"] = 0
                self.log_audit("data_healing", {"record": record, "healed_field": "employment_days", "defaulted": 0})
        else:
            try:
                healed_record["employment_days"] = int(healed_record["employment_days"])
            except (ValueError, TypeError):
                healed_record["employment_days"] = 0
                self.log_audit("data_healing", {"record": record, "healed_field": "employment_days", "type_cast_failed": True, "defaulted": 0})

        return healed_record

    def process_records(self, records: List[Dict], baseline_target: int = 254) -> Dict:
        self.clear_audit_trace()
        self.log_audit("start_processing", {"total_records": len(records), "baseline_target": baseline_target})

        if records is None:
            self.log_audit("input_null", {"action": "defaulting to empty list"})
            records = []

        unique_records = {}
        duplicates = []

        for record in records:
            healed = self._heal_data(record)
            emp_id = healed["id"]

            if emp_id in unique_records:
                duplicates.append(emp_id)
                self.log_audit("deduplication", {"id": emp_id, "action": "dropped"})
            else:
                unique_records[emp_id] = healed

        valid_records = list(unique_records.values())

        # Calculate 7-day employment
        qualified_7_days = [r for r in valid_records if r.get("employment_days", 0) >= 7]
        qualified_count = len(qualified_7_days)

        baseline_achievement_rate = (qualified_count / baseline_target) * 100 if baseline_target > 0 else 0.0

        self.log_audit("calculation_complete", {
            "valid_records_count": len(valid_records),
            "qualified_7_days_count": qualified_count,
            "baseline_achievement_rate": baseline_achievement_rate
        })

        result = {
            "total_processed": len(records),
            "valid_unique": len(valid_records),
            "qualified_7_days": qualified_count,
            "baseline_target": baseline_target,
            "baseline_achievement_rate": round(baseline_achievement_rate, 2),
            "duplicates_dropped": len(duplicates),
            "is_target_met": qualified_count >= baseline_target
        }

        self.log_audit("end_processing", {"result": result})
        return result

def evaluate_baseline(records: Optional[List[Dict]] = None, baseline_target: int = 254) -> Dict:
    """
    一键直达入口：自动校验当月254基准线达成情况，支持在职满7天自动核算。
    缺参自动设合理默认值，容错处理，不抛出不必要的异常。
    """
    if records is None:
        records = []

    engine = BaselineAuditorEngine()
    return engine.process_records(records, baseline_target)

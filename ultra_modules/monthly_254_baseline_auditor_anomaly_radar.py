import logging
import math
import datetime
from typing import List, Dict, Any, Optional

class AnomalyRadarEngine:
    def __init__(self):
        self.audit_trace = []
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger("AnomalyRadarEngine")
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

        if "id" not in healed_record or not healed_record["id"]:
            healed_record["id"] = "unknown_" + str(hash(str(healed_record)))
            self.log_audit("data_healing", {"record_hash": hash(str(healed_record)), "healed_field": "id", "new_value": healed_record["id"]})

        if "employment_days" not in healed_record:
            if "hire_date" in healed_record and healed_record["hire_date"]:
                try:
                    hire_date = datetime.datetime.strptime(healed_record["hire_date"], "%Y-%m-%d")
                    healed_record["employment_days"] = (datetime.datetime.now() - hire_date).days
                    self.log_audit("data_healing", {"id": healed_record["id"], "healed_field": "employment_days", "calculated": True})
                except ValueError:
                    healed_record["employment_days"] = 0
                    self.log_audit("data_healing", {"id": healed_record["id"], "healed_field": "employment_days", "defaulted": 0})
            else:
                healed_record["employment_days"] = 0
                self.log_audit("data_healing", {"id": healed_record["id"], "healed_field": "employment_days", "defaulted": 0})
        else:
            try:
                healed_record["employment_days"] = float(healed_record["employment_days"])
            except (ValueError, TypeError):
                healed_record["employment_days"] = 0.0
                self.log_audit("data_healing", {"id": healed_record["id"], "healed_field": "employment_days", "type_cast_failed": True, "defaulted": 0})

        return healed_record

    def _calculate_z_scores(self, values: List[float]) -> List[float]:
        if not values:
            return []
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return [0.0 for _ in values]

        return [(x - mean) / std_dev for x in values]

    def _scan_anomalies(self, records: List[Dict]) -> List[Dict]:
        if not records:
            return records

        employment_days = [r["employment_days"] for r in records]
        z_scores = self._calculate_z_scores(employment_days)

        for i, record in enumerate(records):
            record["_anomaly_score"] = abs(z_scores[i])
            record["_z_score_raw"] = z_scores[i]

        sorted_records = sorted(records, key=lambda x: x["_anomaly_score"], reverse=True)
        top_3_percent_count = math.ceil(len(records) * 0.03)

        for i, record in enumerate(sorted_records):
            if i < top_3_percent_count:
                if record["_z_score_raw"] > 0:
                    record["status_color"] = "RED"
                    record["reason"] = f"在职天数({record['employment_days']}天)异常偏高，可能存在数据录入错误或异常留存情况。"
                else:
                    record["status_color"] = "YELLOW"
                    record["reason"] = f"在职天数({record['employment_days']}天)异常偏低，需关注极速流失原因。"
            else:
                record["status_color"] = "GREEN"
                record["reason"] = "正常"

        return records

    def process(self, records: List[Dict], baseline_target: int = 254) -> Dict:
        self.clear_audit_trace()
        self.log_audit("start_processing", {"total_records_input": len(records) if records else 0})

        if records is None:
            self.log_audit("input_null", {"action": "defaulting to empty list"})
            records = []

        unique_records = {}
        for record in records:
            healed = self._heal_data(record)
            emp_id = healed["id"]
            if emp_id not in unique_records:
                unique_records[emp_id] = healed
            else:
                self.log_audit("deduplication", {"id": emp_id, "action": "dropped"})

        valid_records = list(unique_records.values())
        processed_records = self._scan_anomalies(valid_records)

        qualified_7_days = [r for r in processed_records if r.get("employment_days", 0) >= 7]
        qualified_count = len(qualified_7_days)
        baseline_achievement_rate = (qualified_count / baseline_target) * 100 if baseline_target > 0 else 0.0

        top_anomalies = [r for r in processed_records if r["status_color"] in ["RED", "YELLOW"]]

        result = {
            "total_processed": len(records),
            "valid_unique": len(processed_records),
            "qualified_7_days": qualified_count,
            "baseline_target": baseline_target,
            "baseline_achievement_rate": round(baseline_achievement_rate, 2),
            "is_target_met": qualified_count >= baseline_target,
            "top_anomalies": top_anomalies,
            "all_records": processed_records
        }

        self.log_audit("end_processing", {"qualified_count": qualified_count, "anomalies_found": len(top_anomalies)})
        return result

def run_anomaly_radar(records: Optional[List[Dict]] = None, baseline_target: int = 254) -> Dict:
    """
    一键直达入口：自动核算达成率，静默扫描异常值并三色标记。
    缺参自动设合理默认值，容错处理。
    """
    if records is None:
        records = []

    engine = AnomalyRadarEngine()
    return engine.process(records, baseline_target)

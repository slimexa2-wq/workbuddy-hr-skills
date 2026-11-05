import datetime
from typing import List, Dict, Any, Optional, Union

class Monthly254BaselineAuditor:
    """
    月初自招台账254人基准线达成率与在职满7天自动核算引擎
    支持跨系统数据契约无缝桥接与Schema版本自动向前兼容转换
    """
    BASELINE_COUNT = 254

    @classmethod
    def audit(cls, records: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
              baseline: int = BASELINE_COUNT,
              current_date: Optional[Union[str, datetime.date, datetime.datetime]] = None) -> Dict[str, Any]:
        """
        极简一键直达入口。
        自动兼容脏数据，缺参设默认值。
        """
        if records is None:
            records = []

        if not isinstance(records, list):
            records = [records] if isinstance(records, dict) else []

        valid_records = []
        for row in records:
            if not isinstance(row, dict):
                continue
            mapped_row = cls._silent_schema_mapping(row)
            valid_records.append(mapped_row)

        active_count = 0
        active_7_days_count = 0

        ref_date = cls._parse_date(current_date) if current_date else datetime.datetime.now().date()

        for row in valid_records:
            status = row.get("status", "")
            if cls._is_active(status):
                active_count += 1
                join_date = row.get("join_date")
                if join_date:
                    join_date_obj = cls._parse_date(join_date)
                    if join_date_obj and ref_date:
                        days_employed = (ref_date - join_date_obj).days
                        if days_employed >= 7:
                            active_7_days_count += 1

        # Ensure baseline is sensible, default fallback if negative or 0 or invalid type
        if not isinstance(baseline, (int, float)) or baseline <= 0:
            baseline = cls.BASELINE_COUNT

        achievement_rate = active_count / baseline

        return {
            "total_records_processed": len(valid_records),
            "baseline": baseline,
            "active_count": active_count,
            "active_7_days_count": active_7_days_count,
            "achievement_rate": achievement_rate,
            "achievement_percentage": f"{achievement_rate * 100:.2f}%",
            "is_baseline_met": active_count >= baseline,
            "schema_version": "auto-forward-compatible"
        }

    @classmethod
    def _silent_schema_mapping(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        自动识别新旧版本字段差异并静默映射转换
        """
        mapped = {}

        schema_mappings = {
            "name": ["name", "emp_name", "employee_name", "姓名", "员工姓名", "人员姓名"],
            "join_date": ["join_date", "hire_date", "entry_date", "入职日期", "入职时间", "报到日期", "入司时间"],
            "status": ["status", "emp_status", "state", "状态", "在职状态", "员工状态", "任职状态", "是否在职"]
        }

        normalized_row = {str(k).strip().lower(): v for k, v in row.items() if v is not None}

        for target, aliases in schema_mappings.items():
            mapped[target] = None
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in normalized_row:
                    mapped[target] = normalized_row[alias_lower]
                    break

                # Partial matching (容错：应对前缀或后缀变化，如“在职状态(最新)”)
                for k, v in normalized_row.items():
                    if alias_lower in k:
                        mapped[target] = v
                        break
                if mapped[target] is not None:
                    break

        # Dirty data self healing for status
        if mapped.get("status") is None:
            # If no status column but join date exists, default to active
            if mapped.get("join_date"):
                mapped["status"] = "在职"
            else:
                mapped["status"] = "未知"

        return mapped

    @staticmethod
    def _is_active(status: Any) -> bool:
        if status is None:
            return False

        if isinstance(status, bool):
            return status

        status_str = str(status).strip().lower()
        active_keywords = ['active', '在职', 'yes', '1', 'true', '正常', '试用', '正式', '是']
        inactive_keywords = ['离职', 'inactive', 'quit', 'left', 'no', '0', 'false', '淘汰', '辞职', '否']

        for kw in inactive_keywords:
            if kw in status_str:
                return False

        for kw in active_keywords:
            if kw in status_str:
                return True

        return False

    @staticmethod
    def _parse_date(date_val: Any) -> Optional[datetime.date]:
        if not date_val:
            return None
        if isinstance(date_val, datetime.date) and not isinstance(date_val, datetime.datetime):
            return date_val
        if isinstance(date_val, datetime.datetime):
            return date_val.date()

        date_str = str(date_val).strip()

        formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d",
            "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

def audit(records: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
          baseline: int = Monthly254BaselineAuditor.BASELINE_COUNT,
          current_date: Optional[Union[str, datetime.date, datetime.datetime]] = None) -> Dict[str, Any]:
    return Monthly254BaselineAuditor.audit(records, baseline, current_date)

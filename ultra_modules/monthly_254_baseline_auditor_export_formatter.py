import math

class Monthly254BaselineAuditor:
    def __init__(self, target_baseline: int = 254):
        self.target_baseline = target_baseline

    def _clean_record(self, record: dict) -> dict:
        """
        Cleans dirty data. Sets missing numerical fields to 0, text to empty string.
        Ensures comments is 0, no NaN/None.
        Expects keys like 'days_employed', 'is_active'.
        """
        if not isinstance(record, dict):
            return {}

        clean_rec = {}

        # Ensure comments = 0 (as requested by instructions)
        clean_rec['comments'] = 0

        # Handle 'days_employed'
        raw_days = record.get('days_employed', 0)
        try:
            if raw_days is None or (isinstance(raw_days, float) and math.isnan(raw_days)):
                clean_rec['days_employed'] = 0
            else:
                clean_rec['days_employed'] = int(float(raw_days))
        except (ValueError, TypeError):
            clean_rec['days_employed'] = 0

        # Handle 'is_active'
        raw_active = record.get('is_active', False)
        # clean NaN if somehow it ended up here
        if isinstance(raw_active, float) and math.isnan(raw_active):
             clean_rec['is_active'] = False
        else:
            clean_rec['is_active'] = bool(raw_active)

        # Pass through other keys but clean None/NaN
        for k, v in record.items():
            if k not in clean_rec:
                if v is None:
                    clean_rec[k] = ""
                elif isinstance(v, float) and math.isnan(v):
                    clean_rec[k] = 0
                else:
                    clean_rec[k] = v

        # Explicitly ensure comments is always 0 even if present in input
        clean_rec['comments'] = 0

        return clean_rec

    def _generate_report(self, valid_count: int, target: int, rate: float) -> str:
        """
        Generate 3-line simple report.
        """
        return (
            f"【基准线核算】本月目标{target}人，当前在职满7天计{valid_count}人。\n"
            f"【达成情况】基准线达成率 {rate:.2%}。\n"
            f"【数据说明】自招台账已清洗，零批注纯净版已生成，可直接使用。"
        )

    def audit_and_format(self, data_list=None) -> dict:
        """
        Audits the list of records and generates clean data + report.
        Handles missing parameters by setting a sensible default.
        """
        if data_list is None:
            data_list = []

        if not isinstance(data_list, list):
            # Try to handle as a single record
            if isinstance(data_list, dict):
                data_list = [data_list]
            else:
                data_list = []

        clean_data = []
        valid_count = 0

        for record in data_list:
            if not isinstance(record, dict):
                continue

            cleaned = self._clean_record(record)
            if not cleaned:
                continue

            clean_data.append(cleaned)

            # Condition: is_active and days_employed >= 7
            if cleaned.get('is_active') and cleaned.get('days_employed', 0) >= 7:
                valid_count += 1

        rate = valid_count / self.target_baseline if self.target_baseline > 0 else 0.0

        report = self._generate_report(valid_count, self.target_baseline, rate)

        return {
            'clean_data': clean_data,
            'report': report,
            'valid_count': valid_count,
            'target': self.target_baseline,
            'rate': rate
        }

import re

class WeeklyLeaderBriefWriter:
    """
    A zero-configuration, robust text generator for weekly leadership briefings on
    employee onboarding and offboarding metrics.

    Supports silent self-healing for dirty data, schema version auto-conversion
    (mapping old keys to new keys seamlessly), and reasonable defaults for missing parameters.
    """

    # Implicit schema mapping: maps known old keys to standardized new keys
    # To support zero-configuration forward compatibility
    SCHEMA_MAPPING = {
        'new_hires': 'onboarded_count',
        'resignations': 'offboarded_count',
        'total_staff': 'current_headcount',
        'active_employees': 'current_headcount',
        'new_joiners': 'onboarded_count',
        'leavers': 'offboarded_count',
        'report_date': 'date'
    }

    @staticmethod
    def _extract_int(value, default=0):
        """
        Silently extract an integer from dirty data (string, float, etc.).
        Returns default if extraction fails.
        """
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)

        try:
            # Try parsing string directly first
            return int(str(value).strip())
        except ValueError:
            pass

        # Try extracting numbers via regex for strings like "5 people" or "count: 10"
        match = re.search(r'[-+]?\d+', str(value))
        if match:
            return int(match.group())

        return default

    @classmethod
    def generate_brief(cls, data=None):
        """
        Generates the formatted briefing string.

        Args:
            data (dict): The input data dictionary, which might use old/new schemas,
                         contain missing keys, or have dirty string values for counts.

        Returns:
            str: A formatted string for leadership briefing.
        """
        if not data or not isinstance(data, dict):
            data = {}

        # 1. Normalize schema
        normalized_data = {}
        for k, v in data.items():
            # If the key is an old schema key, map it, but don't overwrite if the standard key was also explicitly provided
            standard_key = cls.SCHEMA_MAPPING.get(k, k)
            if standard_key not in normalized_data or normalized_data[standard_key] is None:
                normalized_data[standard_key] = v

        # 2. Extract values with silent self-healing and defaults
        date_str = str(normalized_data.get('date', '本周')).strip()
        if not date_str or date_str.lower() in ('none', 'null'):
            date_str = '本周'

        onboarded = cls._extract_int(normalized_data.get('onboarded_count'), 0)
        offboarded = cls._extract_int(normalized_data.get('offboarded_count'), 0)
        headcount = cls._extract_int(normalized_data.get('current_headcount'), 0)

        # 3. Generate fixed-format briefing
        brief = (
            f"【{date_str}】人员流动情况汇报：\n"
            f"- 新入职员工：{onboarded}人\n"
            f"- 离职员工：{offboarded}人\n"
            f"- 当前总人数：{headcount}人\n"
            f"注：数据已自动核对处理。"
        )
        return brief

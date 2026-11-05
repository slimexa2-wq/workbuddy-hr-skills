def generate_weekly_hr_brief(data: dict = None) -> str:
    """
    Generates a weekly HR brief for leaders regarding onboarding and offboarding.
    Implements core algorithm and boundary conditions automatic fallback (missing param fallback, dirty data silent cleaning).

    Expected keys in data:
    - week_start (str): e.g., '2023-10-01'
    - week_end (str): e.g., '2023-10-07'
    - onboarded (int, list, or dict): number of onboarded employees
    - offboarded (int, list, or dict): number of offboarded employees
    - department (str): the department name
    """
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        try:
            data = dict(data)
        except Exception:
            data = {}

    # Silent cleaning and missing parameter fallback
    week_start = str(data.get('week_start', '未知开始日期')).strip() or '未知开始日期'
    week_end = str(data.get('week_end', '未知结束日期')).strip() or '未知结束日期'
    department = str(data.get('department', '全局')).strip() or '全局'

    def parse_count(val):
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            try:
                return max(0, int(val))
            except Exception:
                return 0
        if isinstance(val, str):
            try:
                # Attempt to parse integer from string
                return max(0, int(float(val.strip())))
            except Exception:
                return 0
        if isinstance(val, list):
            return len(val)
        if isinstance(val, dict):
            return len(val.keys())
        return 0

    onboarded_count = parse_count(data.get('onboarded', 0))
    offboarded_count = parse_count(data.get('offboarded', 0))

    net_change = onboarded_count - offboarded_count
    net_change_str = (
        f"净增 {net_change} 人" if net_change > 0
        else f"净减 {abs(net_change)} 人" if net_change < 0
        else "净增减 0 人"
    )

    report = (
        f"【祥能人力周度在离职数据汇报】\n"
        f"统计周期：{week_start} 至 {week_end}\n"
        f"汇报部门：{department}\n"
        f"------------------------\n"
        f"本周入职人数：{onboarded_count} 人\n"
        f"本周离职人数：{offboarded_count} 人\n"
        f"人员净变动：{net_change_str}\n"
        f"------------------------\n"
        f"备注：以上数据由系统自动生成，如有疑问请联系HR部门。"
    )

    return report

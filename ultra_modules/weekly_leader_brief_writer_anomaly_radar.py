import math

def _clean_value(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            cleaned = val.replace(',', '').strip()
            if not cleaned:
                return default
            return float(cleaned)
        except ValueError:
            return default
    return default

def generate_weekly_leader_brief(data=None):
    """
    自动高亮真正需要人工关注的Top 3%异常项并给出大白话原因，其余97%正常项静默放行及测试。
    统计分布异常值(Z-Score/IQR)后台静默扫描与红黄绿三色极简标记器。
    """
    if data is None:
        data = []

    if not isinstance(data, list):
        return "【周度在离职数据汇报】\n输入数据格式异常，已静默放行。🟢"

    if not data:
        return "【周度在离职数据汇报】\n本周无数据，静默放行。🟢"

    cleaned_data = []
    for item in data:
        if not isinstance(item, dict):
            continue

        dept = str(item.get("department", item.get("dept", item.get("name", "未知部门")))).strip()
        if not dept:
            dept = "未知部门"

        exit_count = _clean_value(item.get("exit_count", item.get("exits", item.get("turnover", 0))))
        total_employees = _clean_value(item.get("total_employees", item.get("total", item.get("headcount", 0))))

        exit_count = max(0.0, exit_count)
        total_employees = max(0.0, total_employees)

        exit_rate = 0.0
        if total_employees > 0:
            exit_rate = exit_count / total_employees
        elif exit_count > 0:
            exit_rate = 1.0

        cleaned_data.append({
            "dept": dept,
            "exit_count": exit_count,
            "total_employees": total_employees,
            "exit_rate": exit_rate
        })

    if not cleaned_data:
        return "【周度在离职数据汇报】\n本周无有效数据，静默放行。🟢"

    rates = [d["exit_rate"] for d in cleaned_data]
    mean_rate = sum(rates) / len(rates)
    variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)
    std_dev = math.sqrt(variance)

    sorted_rates = sorted(rates)
    n = len(sorted_rates)

    def get_percentile(p):
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_rates[int(k)]
        d0 = sorted_rates[int(f)] * (c - k)
        d1 = sorted_rates[int(c)] * (k - f)
        return d0 + d1

    if n > 1:
        q1 = get_percentile(0.25)
        q3 = get_percentile(0.75)
    else:
        q1 = q3 = mean_rate

    iqr = q3 - q1
    iqr_upper_bound = q3 + 1.5 * iqr

    for d in cleaned_data:
        rate = d["exit_rate"]
        z_score = (rate - mean_rate) / std_dev if std_dev > 0 else 0.0
        d["z_score"] = z_score

        d["is_anomaly"] = (z_score >= 1.5 or (rate > iqr_upper_bound and iqr > 0) or rate >= 0.5) and rate > 0

    cleaned_data.sort(key=lambda x: x["exit_rate"], reverse=True)

    top_3_percent_count = max(1, math.ceil(len(cleaned_data) * 0.03))

    anomalies = []
    normal_count = 0

    for d in cleaned_data:
        if d["is_anomaly"] and len(anomalies) < top_3_percent_count:
            d["tag"] = "🔴" if d["z_score"] >= 3.0 or d["exit_rate"] >= 0.5 else "🟡"
            anomalies.append(d)
        else:
            d["tag"] = "🟢"
            normal_count += 1

    brief = "【周度在离职数据汇报】\n"

    if anomalies:
        brief += f"发现 {len(anomalies)} 项异常波动需要关注：\n"
        for a in anomalies:
            rate_pct = a["exit_rate"] * 100
            z = a["z_score"]

            if a["exit_rate"] >= 0.5:
                reason = "离职率达50%或以上，存在重大管理或业务风险"
            elif z >= 3.0:
                reason = "离职率极度异常，远超公司正常波动范围"
            elif a["exit_rate"] > iqr_upper_bound and iqr > 0:
                reason = "离职率显著高于公司中位数水平"
            else:
                reason = "离职率较高，存在潜在波动风险"

            brief += f"- {a['tag']} {a['dept']}：离职 {int(a['exit_count'])} 人 (离职率 {rate_pct:.1f}%)。原因：{reason}。\n"

        brief += f"其余 {normal_count} 个部门数据处于正常 🟢 范围，已静默放行。"
    else:
        brief += f"全部 {len(cleaned_data)} 个部门在离职率均在正常 🟢 范围内，无明显异常波动（已静默放行）。"

    return brief

import json

def process_records(records):
    """
    极度宽容的数据清洗与自愈引擎
    处理缺失字段、类型错误、嵌套结构等脏数据
    """
    if records is None:
        return []

    if isinstance(records, dict):
        if "data" in records and isinstance(records["data"], list):
            records = records["data"]
        elif "records" in records and isinstance(records["records"], list):
            records = records["records"]
        else:
            records = [records]

    if not isinstance(records, list):
        try:
            records = list(records)
        except Exception:
            return []

    valid_records = []
    for r in records:
        if not isinstance(r, dict):
            continue

        # 宽容获取招聘渠道信息
        channel = str(r.get("channel", r.get("source", ""))).strip().lower()
        is_self_recruited = ("自招" in channel) or ("self" in channel) or (r.get("is_self_recruited") in (True, 'true', 'True', 1, '1'))

        # 如果未指定任何渠道信息，基于容错设为 False

        # 宽容获取在职天数
        days = 0
        raw_days = r.get("days_employed", r.get("days", 0))
        try:
            days = float(raw_days)
        except (ValueError, TypeError):
            pass

        # 宽容获取在职状态
        status = str(r.get("status", "在职")).strip().lower()
        is_active = ("在职" in status) or ("active" in status) or ("在岗" in status)

        if is_self_recruited and is_active and days >= 7:
            valid_records.append(r)

    return valid_records


def audit_and_explain(records=None, baseline=254, format_type='json'):
    """
    月初自招台账254人基准线审核与大白话解释器。

    :param records: 员工数据列表，支持极度脏数据（缺参、格式错误等）
    :param baseline: 基准线人数，默认254
    :param format_type: 导出格式，支持 'json', 'dict', 'markdown', 'html'，默认 'json'
    :return: 易于普通业务人员理解的大白话结论卡
    """
    # 参数自动容错与类型修正
    try:
        baseline = float(baseline)
        if baseline < 0:
            baseline = 254
    except (ValueError, TypeError):
        baseline = 254

    if not isinstance(format_type, str):
        format_type = 'json'

    format_type = format_type.strip().lower()
    if format_type not in ('json', 'dict', 'markdown', 'html'):
        format_type = 'json'

    qualified_records = process_records(records)
    qualified_count = len(qualified_records)

    if baseline > 0:
        achievement_rate = (qualified_count / baseline) * 100
    else:
        achievement_rate = 100.0 if qualified_count >= 0 else 0.0

    is_passed = qualified_count >= baseline

    if is_passed:
        title = "🎉 达标！月初自招基准线已达成"
        conclusion = f"太棒了！当前已有 {qualified_count} 名自招员工在职满7天，超过了 {int(baseline)} 人的目标底线。达成率 {achievement_rate:.1f}%。"
        status_color = "#28a745"
    else:
        title = "⚠️ 未达标：月初自招基准线预警"
        shortfall = int(baseline - qualified_count)
        conclusion = f"当前仅有 {qualified_count} 名自招员工在职满7天，距离 {int(baseline)} 人的目标还差 {shortfall} 人。达成率 {achievement_rate:.1f}%，请抓紧跟进新入职员工的留存！"
        status_color = "#dc3545"

    card_data = {
        "title": title,
        "qualified_count": qualified_count,
        "baseline": int(baseline),
        "achievement_rate_percent": round(achievement_rate, 1),
        "is_passed": is_passed,
        "conclusion": conclusion
    }

    if format_type == 'dict':
        return card_data

    if format_type == 'json':
        return json.dumps(card_data, ensure_ascii=False, indent=2)

    if format_type == 'markdown':
        return f"### {title}\n" \
               f"**数据速览：**\n" \
               f"- 目标基准线：{int(baseline)} 人\n" \
               f"- 合格在职人数（满7天）：{qualified_count} 人\n" \
               f"- 当前达成率：{achievement_rate:.1f}%\n\n" \
               f"**结论：**\n" \
               f"> {conclusion}"

    # HTML format
    return f'''<div style="border: 1px solid #eee; padding: 20px; border-radius: 12px; font-family: sans-serif; box-shadow: 0 2px 8px rgba(0,0,0,0.05); max-width: 600px;">
    <h3 style="color: {status_color}; margin-top: 0; font-size: 18px;">{title}</h3>
    <ul style="line-height: 1.8; color: #333; font-size: 15px;">
        <li><strong>目标基准线：</strong> {int(baseline)} 人</li>
        <li><strong>合格在职人数（自招且满7天）：</strong> {qualified_count} 人</li>
        <li><strong>当前达成率：</strong> {achievement_rate:.1f}%</li>
    </ul>
    <div style="background: #fdfdfd; padding: 15px; border-left: 4px solid {status_color}; margin-top: 20px; border-radius: 0 8px 8px 0; color: #555; font-size: 15px;">
        <strong>结论：</strong>{conclusion}
    </div>
</div>'''

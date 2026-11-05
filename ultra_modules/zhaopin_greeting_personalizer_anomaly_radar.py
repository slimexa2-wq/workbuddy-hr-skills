import statistics

def generate_greetings_and_scan_anomalies(candidates):
    """
    一键定制生成器（统计分布异常值(Z-Score)后台静默扫描与红黄绿三色极简标记器）。

    自动高亮真正需要人工关注的Top 3%异常项并给出大白话原因，其余正常项静默放行。

    Args:
        candidates (list): 候选人字典列表，预期包含 'name', 'past_companies' (list/str), 'expected_location', 'job_transitions' (int)

    Returns:
        list: 处理后的候选人字典列表，增加 'greeting', 'anomaly_color' (RED/YELLOW/GREEN), 'anomaly_reason'
    """
    if not candidates:
        return []

    results = []
    transitions_data = []

    # 第一遍：数据清洗和收集统计数据
    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        transitions = cand.get('job_transitions')

        # 脏数据自愈与缺参兜底：如果没提供跳槽次数，尝试从公司列表推算，如果都没有则默认为 1
        if transitions is None or not isinstance(transitions, (int, float)):
            companies = cand.get('past_companies', [])
            if isinstance(companies, list):
                transitions = len(companies)
            elif isinstance(companies, str):
                transitions = len([c for c in companies.split(',') if c.strip()])
            else:
                transitions = 1

        transitions_data.append(transitions)

        # 复制字典以防修改原数据
        processed_cand = dict(cand)
        processed_cand['_clean_transitions'] = transitions
        results.append(processed_cand)

    # 计算统计特征
    if not transitions_data or len(transitions_data) < 2:
        mean_val = transitions_data[0] if transitions_data else 0
        stdev_val = 0
    else:
        try:
            mean_val = statistics.mean(transitions_data)
            stdev_val = statistics.stdev(transitions_data)
        except statistics.StatisticsError:
            mean_val = sum(transitions_data) / len(transitions_data)
            stdev_val = 0

    # 防止除以0
    stdev_val = stdev_val if stdev_val > 0 else 1

    # 第二遍：生成话术和异常标记
    for cand in results:
        # 1. 话术生成
        name = str(cand.get('name', '')).strip() or '同学'
        location = str(cand.get('expected_location', '')).strip() or '我们这边'
        companies_raw = cand.get('past_companies', [])

        if isinstance(companies_raw, list) and companies_raw:
            company_text = str(companies_raw[0]).strip()
        elif isinstance(companies_raw, str) and companies_raw.strip():
            company_text = companies_raw.split(',')[0].strip()
        else:
            company_text = '您过往平台'

        cand['greeting'] = f"你好{name}，看到你在{company_text}的经历很不错，考虑{location}的机会吗？"

        # 2. 异常扫描 (Z-Score)
        transitions = cand.pop('_clean_transitions')
        z_score = (transitions - mean_val) / stdev_val

        if len(transitions_data) >= 2:
            # Top 3% 单侧大概对应 Z-Score > 1.88
            if z_score > 1.88:
                cand['anomaly_color'] = 'RED'
                cand['anomaly_reason'] = f'跳槽过于频繁（高于平均水平，跳槽次数：{transitions}次）'
            # 次级警告 大概对应 Z-Score > 1.0 左右（约前 16%）
            elif z_score > 1.0:
                cand['anomaly_color'] = 'YELLOW'
                cand['anomaly_reason'] = f'跳槽略微频繁（跳槽次数：{transitions}次）'
            else:
                cand['anomaly_color'] = 'GREEN'
                cand['anomaly_reason'] = ''
        else:
            # 数据量不足以进行统计分析，全部放行
            cand['anomaly_color'] = 'GREEN'
            cand['anomaly_reason'] = ''

    return results

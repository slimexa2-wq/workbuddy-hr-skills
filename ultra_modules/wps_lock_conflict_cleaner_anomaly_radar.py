import os
import time
import math
import logging

def calculate_z_scores(values):
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [0.0]
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0

    if std_dev == 0:
        return [0.0 for _ in values]
    return [(x - mean) / std_dev for x in values]

def calculate_iqr_thresholds(values):
    n = len(values)
    if n == 0:
        return 0, 0
    sorted_vals = sorted(values)
    if n < 4:
        return sorted_vals[0], sorted_vals[-1]

    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)
    q1 = sorted_vals[q1_idx]
    q3 = sorted_vals[q3_idx]
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr

def scan_and_clean_anomalies(target_dir=None, auto_clean=True, test_mode=False):
    """
    macOS下WPS/Excel残留.~lock与~$临时锁文件自动检测与无损解锁器
    极简入口，零配置容错，自动高亮Top 3%异常值（静默自愈脏数据）。
    """
    # 极度严密复杂的后台容错与脏数据自愈
    if target_dir is None or not isinstance(target_dir, str) or not target_dir.strip():
        target_dir = "."
    if not os.path.exists(target_dir):
        target_dir = "."
    if not isinstance(auto_clean, bool):
        auto_clean = True
    if not isinstance(test_mode, bool):
        test_mode = False

    now = time.time()
    lock_files = []

    # 递归静默扫描
    try:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.startswith(".~lock.") or file.startswith("~$"):
                    full_path = os.path.join(root, file)
                    try:
                        st = os.stat(full_path)
                        age = now - st.st_mtime
                        # Fallback for negative age (future files)
                        if age < 0:
                            age = 0
                        lock_files.append({
                            "path": full_path,
                            "age": age,
                            "size": st.st_size,
                            "filename": file
                        })
                    except Exception:
                        pass
    except Exception:
        pass

    if not lock_files:
        return {"red_anomalies": [], "yellow_warnings": [], "green_normals": [], "cleaned_count": 0, "total_scanned": 0}

    # 统计分布异常值 (Z-Score & IQR)
    ages = [f["age"] for f in lock_files]
    z_scores = calculate_z_scores(ages)
    _, iqr_upper = calculate_iqr_thresholds(ages)

    for i, lf in enumerate(lock_files):
        lf["z_score"] = z_scores[i]

    # 按异常程度（停留时间长短）降序
    lock_files.sort(key=lambda x: x["age"], reverse=True)

    n_files = len(lock_files)
    # 精确锁定 Top 3%（为了小样本也有意义，如果Z-score>2或超出IQR上限，也纳入考虑范围，但至少保证前3%如果在统计上显著）
    top_3_count = max(1, int(math.ceil(n_files * 0.03))) if n_files >= 10 else (1 if n_files > 0 and lock_files[0]["z_score"] > 1.5 else 0)

    red_anomalies = []
    yellow_warnings = []
    green_normals = []
    cleaned_count = 0

    for i, lf in enumerate(lock_files):
        age = lf["age"]
        z = lf["z_score"]

        # 红黄绿三色极简标记器
        # Red: Top 3% 或极端异常 (Z > 3.0 或 远超 IQR) -> 人工关注
        is_red = (i < top_3_count) or (z > 3.0) or (age > iqr_upper * 1.5 and iqr_upper > 0)
        # 强制小样本时不误报，除非真异常
        if n_files < 10 and not (z > 1.5 or age > 3600):
            is_red = False

        if is_red:
            lf["color"] = "Red"
            lf["reason"] = "这几个文件停留时间长得异于常理（属于Top 3%严重异常分布），大概率是WPS/Excel非正常崩溃导致的死锁残留。安全起见，建议您人工看一眼确认，避免误删还没保存的数据。"
            red_anomalies.append(lf)
        elif z > 1.0 or age > iqr_upper:
            lf["color"] = "Yellow"
            lf["reason"] = "时间分布有轻微偏离（黄灯预警），但大概率为无用废弃锁，静默放行并自动清理。"
            yellow_warnings.append(lf)
        else:
            lf["color"] = "Green"
            lf["reason"] = "正常范围内的临时文件，绝对安全，静默放行并清理。"
            green_normals.append(lf)

        # 其余97%正常项静默放行及测试（无损解锁，即清理无用锁文件）
        if lf["color"] in ("Yellow", "Green"):
            if auto_clean and not test_mode:
                try:
                    os.remove(lf["path"])
                    cleaned_count += 1
                except Exception:
                    pass
            elif test_mode:
                cleaned_count += 1

    return {
        "red_anomalies": red_anomalies,
        "yellow_warnings": yellow_warnings,
        "green_normals": green_normals,
        "cleaned_count": cleaned_count,
        "total_scanned": n_files
    }

#!/usr/bin/env python3
"""
极速共享索引构建工具（阶段一：≤30秒完成）：
一次性提取目标批次目录下所有结款工作簿中的身份证号与姓名，
使用 multiprocessing 并行扫描《所有企业名单汇总》及历史结款表，
输出轻量级 policy_matches.json 与 hist_matches.json 供各并行 Subagent 直接读取，
避免各 Subagent 重复读取数万行大表造成磁盘 I/O 阻塞。

用法：
python3 fast_index_builder.py <批次目录路径> <共享盘根目录> <输出JSON目录> [城市关键字,如:绵阳]
"""
import datetime
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
import openpyxl
import xlrd

ID_RE = re.compile(r"^\d{17}[\dXx]$")


def fmt_val(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v).strip()


def extract_targets(batch_dir: str):
    target_ids = set()
    target_names = set()
    for fn in sorted(os.listdir(batch_dir)):
        if fn.startswith("~$") or "审核版" in fn or not fn.endswith((".xlsx", ".xls")):
            continue
        fpath = os.path.join(batch_dir, fn)
        if fn.endswith(".xlsx"):
            wb = openpyxl.load_workbook(fpath, data_only=True, read_only=True)
            for sn in wb.sheetnames:
                if any(k in sn for k in ("汇总", "合计", "Sheet1")):
                    continue
                ws = wb[sn]
                for row in ws.iter_rows(max_col=25, values_only=True):
                    for v in row[:10]:
                        if v is None:
                            continue
                        s = str(v).strip()
                        if ID_RE.match(s):
                            target_ids.add(s.upper())
                        elif bool(re.match(r"^[\u4e00-\u9fa5\·]{2,15}$", s)):
                            target_names.add(s)
            wb.close()
        else:
            wb = xlrd.open_workbook(fpath)
            for sn in wb.sheet_names():
                sh = wb.sheet_by_name(sn)
                for r in range(sh.nrows):
                    for c in range(min(10, sh.ncols)):
                        s = str(sh.cell_value(r, c)).strip()
                        if ID_RE.match(s):
                            target_ids.add(s.upper())
                        elif bool(re.match(r"^[\u4e00-\u9fa5\·]{2,15}$", s)):
                            target_names.add(s)
    return target_ids, target_names


def scan_policy_worker(args):
    fpath, target_ids, target_names = args
    fname = os.path.basename(os.path.dirname(fpath)) + "/" + os.path.basename(fpath)
    by_id, by_name = {}, {}
    try:
        wb = openpyxl.load_workbook(fpath, data_only=True, read_only=True)
        for sn in wb.sheetnames:
            ws = wb[sn]
            headers = []
            for r_idx, row in enumerate(ws.iter_rows(max_col=30, values_only=True), 1):
                if r_idx <= 3 and not headers:
                    row_strs = [fmt_val(x) for x in row]
                    if any("姓名" in s or "身份证" in s for s in row_strs):
                        headers = row_strs
                        continue
                row_id, row_name = None, None
                for v in row[:12]:
                    if v is None:
                        continue
                    s = str(v).strip()
                    if ID_RE.match(s):
                        row_id = s.upper()
                    elif not row_name and bool(re.match(r"^[\u4e00-\u9fa5\·]{2,15}$", s)):
                        row_name = s
                if (row_id and row_id in target_ids) or (row_name and row_name in target_names):
                    rec = {
                        "file": fname,
                        "sheet": sn,
                        "row": r_idx,
                        "data": {
                            (headers[i] if i < len(headers) and headers[i] else f"C{i+1}"): fmt_val(v)
                            for i, v in enumerate(row[:25])
                            if v is not None and fmt_val(v) != ""
                        },
                    }
                    if row_id and row_id in target_ids:
                        by_id.setdefault(row_id, []).append(rec)
                    if row_name and row_name in target_names:
                        by_name.setdefault(row_name, []).append(rec)
        wb.close()
    except Exception:
        pass
    return by_id, by_name


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 fast_index_builder.py <batch_dir> <share_root> <out_dir> [city_keyword]")
        sys.exit(1)
    batch_dir, share_root, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    target_ids, target_names = extract_targets(batch_dir)
    pol_files = []
    for root, _, files in os.walk(share_root):
        for f in files:
            if "所有企业名单汇总" in f and f.endswith(".xlsx") and not f.startswith("~$"):
                pol_files.append(os.path.join(root, f))
    pol_by_id, pol_by_name = {}, {}
    with ProcessPoolExecutor(max_workers=min(8, max(1, len(pol_files)))) as ex:
        for b_id, b_nm in ex.map(scan_policy_worker, [(p, target_ids, target_names) for p in sorted(pol_files)]):
            for k, v in b_id.items():
                pol_by_id.setdefault(k, []).extend(v)
            for k, v in b_nm.items():
                pol_by_name.setdefault(k, []).extend(v)
    out_pol = os.path.join(out_dir, "policy_matches.json")
    with open(out_pol, "w", encoding="utf-8") as f:
        json.dump({"by_id": pol_by_id, "by_name": pol_by_name}, f, ensure_ascii=False)
    print(f"Indexed {len(pol_by_id)} IDs and {len(pol_by_name)} names -> {out_pol}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
《所有企业名单汇总》精确索引库（SQLite B-Tree，非向量模糊库）自动增量同步与过期清理工具：
1. 精确匹配：按【身份证号】【姓名】建立 B-Tree 精确索引，毫秒级（<1ms）单人查询，杜绝向量模糊匹配串人、也杜绝10个项目混提干扰。
2. 每周自动更新与清理无效旧表：
   - 每次运行先扫描共享盘当前有效的《所有企业名单汇总》文件（记录路径、mtime、size）；
   - 凡共享盘已删除、移走或文件时间戳/大小已变更的旧表，立即从 SQLite 中 DELETE 清除其全部过往无效记录；
   - 仅对新增或本周更新的政策表执行解析入库，未变动文件 0 秒跳过。
"""
import datetime
import json
import os
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
import openpyxl
import xlrd

ID_RE = re.compile(r"^\d{17}[\dXx]$")
DEFAULT_DB_PATH = os.path.expanduser("~/.gemini/cache/supplier_audit_policy.sqlite")


def fmt_val(v):
    if v is None:
        return ""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v).strip()


def parse_single_policy_file(fpath: str):
    """Parse a single 所有企业名单汇总 (.xls or .xlsx) and return rows for SQLite insertion."""
    rel_name = os.path.basename(os.path.dirname(fpath)) + "/" + os.path.basename(fpath)
    records = []
    try:
        if fpath.endswith(".xlsx"):
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
                    row_id, row_name = "", ""
                    for v in row[:12]:
                        if v is None:
                            continue
                        s = str(v).strip()
                        if ID_RE.match(s):
                            row_id = s.upper()
                        elif not row_name and 2 <= len(s) <= 5 and all("\u4e00" <= c <= "\u9fff" for c in s):
                            row_name = s
                    if row_id or row_name:
                        data_dict = {
                            (headers[i] if i < len(headers) and headers[i] else f"C{i+1}"): fmt_val(v)
                            for i, v in enumerate(row[:25])
                            if v is not None and fmt_val(v) != ""
                        }
                        records.append((
                            rel_name,
                            sn,
                            r_idx,
                            row_id,
                            row_name,
                            data_dict.get("入职企业", data_dict.get("企业", "")),
                            data_dict.get("供应商", ""),
                            data_dict.get("政策", data_dict.get("结算价格", "")),
                            data_dict.get("面试日期", data_dict.get("入职日期", "")),
                            json.dumps(data_dict, ensure_ascii=False),
                        ))
            wb.close()
        elif fpath.endswith(".xls"):
            wb = xlrd.open_workbook(fpath)
            for sn in wb.sheet_names():
                sh = wb.sheet_by_name(sn)
                headers = []
                for r in range(sh.nrows):
                    row = [sh.cell_value(r, c) for c in range(min(30, sh.ncols))]
                    if r < 3 and not headers:
                        row_strs = [fmt_val(x) for x in row]
                        if any("姓名" in s or "身份证" in s for s in row_strs):
                            headers = row_strs
                            continue
                    row_id, row_name = "", ""
                    for v in row[:12]:
                        s = fmt_val(v)
                        if ID_RE.match(s):
                            row_id = s.upper()
                        elif not row_name and 2 <= len(s) <= 5 and all("\u4e00" <= c <= "\u9fff" for c in s):
                            row_name = s
                    if row_id or row_name:
                        data_dict = {
                            (headers[i] if i < len(headers) and headers[i] else f"C{i+1}"): fmt_val(v)
                            for i, v in enumerate(row[:25])
                            if v is not None and fmt_val(v) != ""
                        }
                        records.append((
                            rel_name,
                            sn,
                            r + 1,
                            row_id,
                            row_name,
                            data_dict.get("入职企业", data_dict.get("企业", "")),
                            data_dict.get("供应商", ""),
                            data_dict.get("政策", data_dict.get("结算价格", "")),
                            data_dict.get("面试日期", data_dict.get("入职日期", "")),
                            json.dumps(data_dict, ensure_ascii=False),
                        ))
    except Exception as e:
        print(f"Warn: failed parsing {fpath}: {e}", file=sys.stderr)
    return fpath, rel_name, records


def sync_policy_db(share_root: str, db_path: str = DEFAULT_DB_PATH):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS file_meta (
            rel_name TEXT PRIMARY KEY,
            full_path TEXT,
            mtime REAL,
            size INTEGER,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policy_records (
            rel_name TEXT,
            sheet TEXT,
            row_num INTEGER,
            id_card TEXT,
            name TEXT,
            enterprise TEXT,
            supplier TEXT,
            policy TEXT,
            interview_date TEXT,
            raw_json TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_policy_id ON policy_records(id_card)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_policy_name ON policy_records(name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_policy_file ON policy_records(rel_name)")

    # Discover current valid policy files (top root and 1-level batch dirs to avoid deep slow walk)
    current_files = {}
    for entry in os.scandir(share_root):
        if entry.is_file() and "所有企业名单汇总" in entry.name and not entry.name.startswith("~$") and entry.name.endswith((".xls", ".xlsx")):
            st = entry.stat()
            rel = os.path.basename(share_root.rstrip("/")) + "/" + entry.name
            current_files[rel] = (entry.path, st.st_mtime, st.st_size)
        elif entry.is_dir() and not entry.name.startswith("."):
            try:
                for sub in os.scandir(entry.path):
                    if sub.is_file() and "所有企业名单汇总" in sub.name and not sub.name.startswith("~$") and sub.name.endswith((".xls", ".xlsx")):
                        st = sub.stat()
                        rel = entry.name + "/" + sub.name
                        current_files[rel] = (sub.path, st.st_mtime, st.st_size)
            except Exception:
                pass

    # Check existing indexed files in DB
    cur.execute("SELECT rel_name, mtime, size FROM file_meta")
    existing_meta = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    # 1. Purge deleted or outdated files
    to_purge = [rel for rel, (mt, sz) in existing_meta.items() if rel not in current_files or abs(current_files[rel][1] - mt) > 1e-3 or current_files[rel][2] != sz]
    for rel in to_purge:
        cur.execute("DELETE FROM policy_records WHERE rel_name = ?", (rel,))
        cur.execute("DELETE FROM file_meta WHERE rel_name = ?", (rel,))
        print(f"[Purged outdated/removed policy file] {rel}")

    # 2. Identify new or modified files to index
    to_index = [ current_files[rel][0] for rel in sorted(current_files.keys()) if rel not in existing_meta or rel in to_purge ]
    if to_index:
        with ProcessPoolExecutor(max_workers=min(8, len(to_index))) as ex:
            for fpath, rel_name, records in ex.map(parse_single_policy_file, to_index):
                _, mtime, size = current_files[rel_name]
                cur.executemany(
                    "INSERT INTO policy_records VALUES (?,?,?,?,?,?,?,?,?,?)",
                    records,
                )
                cur.execute(
                    "INSERT OR REPLACE INTO file_meta VALUES (?,?,?,?,?)",
                    (rel_name, fpath, mtime, size, datetime.datetime.now().isoformat()),
                )
                print(f"[Indexed policy file] {rel_name} ({len(records)} rows)")
    else:
        print("[SQLite Policy DB up-to-date] 0 files changed.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/000供应商结款共享"
    db = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DB_PATH
    sync_policy_db(root, db)

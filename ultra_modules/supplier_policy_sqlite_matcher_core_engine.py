import sqlite3
import datetime
from typing import Optional, Dict, Any, Union

def _cleanse_date(date_val: Any) -> str:
    """脏数据静默清洗 - 日期格式"""
    if isinstance(date_val, datetime.date):
        return date_val.isoformat()
    if not date_val:
        return datetime.date.today().isoformat()

    try:
        date_str = str(date_val).strip()
        date_str = date_str.replace('/', '-').replace('.', '-')
        if len(date_str) > 10:
            date_str = date_str[:10]
        # Validate date
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except (ValueError, TypeError):
        return datetime.date.today().isoformat()

def _cleanse_job_type(job_val: Any) -> str:
    """脏数据静默清洗 - 工种"""
    if not job_val:
        return "GENERAL"
    val_str = str(job_val).strip().upper()
    if val_str in ("NONE", "NULL", ""):
        return "GENERAL"
    return val_str

def _cleanse_quantity(qty_val: Any) -> int:
    """脏数据静默清洗 - 数量"""
    if qty_val is None:
        return 1
    try:
        val = int(float(qty_val))
        return val if val >= 0 else 1
    except (ValueError, TypeError):
        return 1

def init_db(db_path: str):
    """零配置容错：如果表不存在自动创建并建索引"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_policies (
            policy_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            min_quantity INTEGER NOT NULL,
            max_quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        )
    """)
    # Add indexes for millisecond-level exact matching
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_policy_match ON supplier_policies(job_type, start_date, end_date)")
    conn.commit()
    conn.close()

def match_supplier_policy(
    db_path: str,
    target_date: Union[str, datetime.date, None] = None,
    job_type: Optional[str] = None,
    quantity: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    SQLite原始政策库按日期区间与工种阶梯单价毫秒级精确匹配器.
    核心纯函数算法与零配置自动容错实现.
    """
    # 1. 缺参赋默认值 & 脏数据静默清洗
    clean_date = _cleanse_date(target_date)
    clean_job = _cleanse_job_type(job_type)
    clean_qty = _cleanse_quantity(quantity)

    # 2. 零配置自动容错建表
    try:
        init_db(db_path)
    except Exception:
        pass # ignore setup errors to maintain fault tolerance

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        return {
            "status": "error",
            "matched_price": 100.0,
            "policy_id": "ERROR_FALLBACK",
            "reason": f"Connection Error: {str(e)}"
        }

    try:
        query = """
            SELECT policy_id, unit_price
            FROM supplier_policies
            WHERE job_type = ?
              AND start_date <= ?
              AND end_date >= ?
              AND min_quantity <= ?
              AND max_quantity >= ?
            ORDER BY unit_price ASC
            LIMIT 1
        """
        cursor.execute(query, (clean_job, clean_date, clean_date, clean_qty, clean_qty))
        row = cursor.fetchone()

        if row:
            return {
                "status": "success",
                "matched_price": float(row["unit_price"]),
                "policy_id": row["policy_id"],
                "reason": "Exact match found"
            }
        else:
            return {
                "status": "fallback",
                "matched_price": 100.0,
                "policy_id": "DEFAULT_FALLBACK",
                "reason": "No policy matched, using default fallback"
            }

    except sqlite3.OperationalError as e:
        return {
            "status": "error",
            "matched_price": 100.0,
            "policy_id": "ERROR_FALLBACK",
            "reason": f"DB Operational Error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "matched_price": 100.0,
            "policy_id": "ERROR_FALLBACK",
            "reason": f"Unexpected Error: {str(e)}"
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass

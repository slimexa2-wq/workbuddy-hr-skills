import codecs
import time
from typing import Dict, Any, Tuple

def process_csv_with_audit(raw_content: bytes = b"", fallback_encoding: str = "utf-8-sig") -> Tuple[str, Dict[str, Any]]:
    """
    一键无感转码清洗器（带审计日志）：将乱码/不同编码的CSV字节流转换为标准UTF-8字符串，并记录全链路审计日志。

    :param raw_content: 原始字节流。缺省为b""。
    :param fallback_encoding: 兜底编码格式，用于所有尝试均失败时。
    :return: (清洗后的标准UTF-8字符串, 审计日志字典)
    """
    audit_log = {
        "timestamp": time.time(),
        "input_type": type(raw_content).__name__,
        "input_length": 0,
        "steps": [],
        "success": False,
        "final_encoding": None,
        "dirty_data_healed": False
    }

    if raw_content is None:
        raw_content = b""
        audit_log["steps"].append("Null parameter self-healed to empty bytes.")

    if isinstance(raw_content, str):
        audit_log["steps"].append("Input is already a string. No decoding needed.")
        audit_log["success"] = True
        audit_log["final_encoding"] = "utf-8 (assumed)"
        audit_log["input_length"] = len(raw_content.encode('utf-8'))
        return raw_content, audit_log

    if not isinstance(raw_content, bytes):
        try:
            raw_content = bytes(raw_content)
            audit_log["steps"].append(f"Coerced input of type {audit_log['input_type']} to bytes.")
        except Exception as e:
            audit_log["steps"].append(f"Failed to coerce input to bytes: {str(e)}")
            raw_content = b""

    audit_log["input_length"] = len(raw_content)

    if not raw_content:
        audit_log["steps"].append("Empty input content.")
        audit_log["success"] = True
        return "", audit_log

    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16"]

    # 尝试无损解码
    for enc in encodings:
        try:
            decoded = raw_content.decode(enc)
            audit_log["steps"].append(f"Successfully decoded with {enc} without errors.")
            audit_log["success"] = True
            audit_log["final_encoding"] = enc
            return decoded, audit_log
        except (UnicodeDecodeError, TypeError, ValueError) as e:
            audit_log["steps"].append(f"Decoding with {enc} failed: {type(e).__name__}")
            continue

    # 如果全部失败，使用 fallback_encoding 并替换非法字符，实现静默容错清洗
    audit_log["steps"].append(f"All standard decodings failed. Falling back to {fallback_encoding} with error replacement.")
    audit_log["dirty_data_healed"] = True
    audit_log["success"] = True
    audit_log["final_encoding"] = f"{fallback_encoding} (replaced)"

    return raw_content.decode(fallback_encoding, errors="replace"), audit_log

import codecs

def transcode_csv_to_utf8(raw_content: bytes = b"") -> str:
    """
    一键无感转码清洗器：将各种乱码/不同编码的CSV字节流转换为标准UTF-8字符串。

    特性：
    - 支持 UTF-8-SIG (BOM), UTF-8, GB18030, GBK, BIG5 等常见编码。
    - 缺省自动赋默认值，脏数据静默清洗。
    - 零异常抛出（100% 自动兜底）。
    """
    if not raw_content:
        return ""

    if isinstance(raw_content, str):
        return raw_content

    if not isinstance(raw_content, bytes):
        try:
            raw_content = bytes(raw_content)
        except Exception:
            return ""

    encodings = ["utf-8-sig", "utf-8", "gb18030", "big5", "utf-16"]

    # 尝试无损解码
    for enc in encodings:
        try:
            return raw_content.decode(enc)
        except (UnicodeDecodeError, TypeError, ValueError):
            continue

    # 如果全部失败，使用 utf-8-sig 并替换非法字符，实现静默容错清洗
    return raw_content.decode("utf-8-sig", errors="replace")

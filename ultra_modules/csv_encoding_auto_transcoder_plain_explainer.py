import json

def generate_explainer_card(result_data: dict = None, output_format: str = "markdown") -> str:
    """
    将后台CSV转码与清洗的结果数据，转化为业务人员一秒看懂的结论卡片。
    支持自动容错、缺参自愈。
    """
    if result_data is None or not isinstance(result_data, dict):
        result_data = {}

    if not isinstance(output_format, str):
        output_format = "markdown"

    output_format = output_format.lower().strip()
    if output_format not in ["markdown", "html", "json"]:
        output_format = "markdown"

    # 提取参数，带自愈功能
    try:
        success = bool(result_data.get("success", True))
    except Exception:
        success = True

    try:
        original_encoding = str(result_data.get("original_encoding", "未知")).strip()
        if not original_encoding:
            original_encoding = "未知"
    except Exception:
        original_encoding = "未知"

    try:
        rows_processed = int(result_data.get("rows_processed", 0))
        if rows_processed < 0:
            rows_processed = 0
    except Exception:
        rows_processed = 0

    try:
        dirty_data_fixed = int(result_data.get("dirty_data_fixed", 0))
        if dirty_data_fixed < 0:
            dirty_data_fixed = 0
    except Exception:
        dirty_data_fixed = 0

    # 拼接白话结论
    if success:
        status_text = "✅ 考勤数据解析成功"
        detail_text = f"我们发现您的文件原本是【{original_encoding}】格式，已自动为您转换为标准的通用格式。共顺利读取了 {rows_processed} 条考勤记录。"
        if dirty_data_fixed > 0:
            detail_text += f" 另外，我们还顺手帮您修补了 {dirty_data_fixed} 处小瑕疵（乱码或错位），现在数据干干净净啦！"
        else:
            detail_text += " 数据非常健康，没有发现乱码。"
    else:
        status_text = "❌ 考勤数据解析遇到点小麻烦"
        detail_text = "我们尝试了多种方式解读您的文件，但还是差一点点。这通常是因为文件损坏或者采用了极其罕见的格式。您可以尝试重新下载一次文件再上传哦！"

    # 根据输出格式渲染
    if output_format == "json":
        return json.dumps({
            "title": status_text,
            "summary": detail_text,
            "metrics": {
                "rows": rows_processed,
                "fixed": dirty_data_fixed,
                "encoding": original_encoding
            }
        }, ensure_ascii=False, indent=2)

    elif output_format == "html":
        card_color = "#e6f4ea" if success else "#fce8e6"
        text_color = "#137333" if success else "#c5221f"
        return (f"<div style='border: 1px solid #ddd; border-radius: 8px; padding: 16px; "
                f"background-color: {card_color}; font-family: sans-serif; max-width: 600px;'>"
                f"<h3 style='margin-top: 0; color: {text_color};'>{status_text}</h3>"
                f"<p style='color: #333; line-height: 1.5;'>{detail_text}</p>"
                f"</div>")

    else:
        # Markdown
        return f"### {status_text}\n\n**处理摘要**：{detail_text}\n"

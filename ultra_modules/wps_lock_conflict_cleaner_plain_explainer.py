import os
import json
from typing import List, Optional

def clean_and_explain(target_dir: Optional[str] = None, output_format: Optional[str] = None) -> str:
    """
    一键无损清理 WPS/Excel 残留的锁文件，并生成极简大白话报告。

    :param target_dir: 目标目录，缺省自动使用当前工作目录。
    :param output_format: 输出格式 ('markdown', 'json', 'html')，缺省自动使用 'markdown'。
    :return: 大白话诊断和清理结果字符串。
    """
    # 1. 零配置容错与缺参自动设合理默认值
    if not target_dir or not isinstance(target_dir, str):
        target_dir = "."

    if not output_format or not isinstance(output_format, str):
        output_format = "markdown"

    output_format = output_format.lower().strip()
    if output_format not in ["markdown", "json", "html"]:
        output_format = "markdown"

    cleaned_files: List[str] = []
    error_msg = ""

    # 2. 脏数据自愈与基础校验
    if not os.path.exists(target_dir):
        error_msg = "指定的文件夹不存在，已跳过清理。"
        return _generate_card([], output_format, error_msg)

    if not os.path.isdir(target_dir):
        error_msg = "给定的路径不是文件夹，已跳过清理。"
        return _generate_card([], output_format, error_msg)

    # 3. 核心解锁逻辑：扫描并安全清理锁文件
    try:
        for root, _, files in os.walk(target_dir):
            for file in files:
                # 匹配 macOS 下 Excel/WPS 产生的残留临时锁文件
                if file.startswith("~$") or file.startswith(".~lock."):
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.isfile(file_path):
                            # 删除锁文件以实现无损解锁
                            os.remove(file_path)
                            cleaned_files.append(file_path)
                    except Exception:
                        # 极端边界情况（如权限不足）安全静默忽略，保证流程健壮性
                        pass
    except Exception as e:
        error_msg = f"扫描时遇到意外（{str(e)}），不过已完成部分工作。"

    # 4. 生成大白话报告卡片
    return _generate_card(cleaned_files, output_format, error_msg)


def _generate_card(cleaned_files: List[str], fmt: str, error: str = "") -> str:
    """
    内部可视化卡片生成器，提供极简大白话结论。
    """
    count = len(cleaned_files)

    if error:
        conclusion = f"遇到小状况：{error}"
    elif count == 0:
        conclusion = "太棒了！没有发现任何卡住的文档，一切顺畅！"
    else:
        conclusion = f"搞定！成功为您解锁了 {count} 个被卡住的办公文件，现在可以正常打开编辑了！"

    if fmt == "json":
        return json.dumps({
            "status": "success" if not error else "warning",
            "summary": conclusion,
            "unlocked_count": count,
            "unlocked_files": cleaned_files
        }, ensure_ascii=False, indent=2)

    elif fmt == "html":
        items = "".join([f"<li style='margin-bottom: 5px; color: #555;'>{f}</li>" for f in cleaned_files])
        list_html = f"<ul style='background: #f9f9f9; padding: 10px 20px; border-radius: 4px;'>{items}</ul>" if items else ""
        return (
            "<div style='font-family: sans-serif; border: 1px solid #eee; border-radius: 10px; "
            "padding: 20px; max-width: 500px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);'>"
            "<h2 style='margin-top: 0; color: #4CAF50;'>✨ 办公文档极速卫士</h2>"
            f"<p style='font-size: 16px; font-weight: bold; color: #333;'>{conclusion}</p>"
            f"{list_html}"
            "</div>"
        )

    else:
        # Markdown
        items = "\n".join([f"- `{f}`" for f in cleaned_files])
        list_md = f"\n\n**已解锁的文件名单：**\n{items}" if items else ""
        return (
            "### ✨ 办公文档极速卫士\n\n"
            f"**{conclusion}**"
            f"{list_md}"
        )

import json
from typing import Any, Dict, List, Optional, Union

def explain_reaped_processes(
    raw_data: Optional[List[Dict[str, Any]]] = None,
    output_format: str = "json"
) -> Union[str, Dict[str, Any]]:
    """
    Analyzes raw process data, filters for orphaned (PPID=1) Agent/Playwright/MCP processes,
    and returns a plain language summary in the requested format (html, markdown, or json).

    Zero-configuration and auto-fault-tolerant:
    - Handles None or missing data gracefully by defaulting to empty lists.
    - Gracefully ignores dirty data (missing keys, wrong types).
    - Automatically cleans and summarizes memory usage.
    """
    if raw_data is None:
        raw_data = []

    if not isinstance(raw_data, list):
        raw_data = []

    valid_processes = []
    total_memory_mb = 0.0

    for item in raw_data:
        if not isinstance(item, dict):
            continue

        try:
            ppid = item.get("ppid")
            name = item.get("name", "")
            memory_mb = item.get("memory_mb", 0)

            # Auto-healing for weird types
            if ppid is not None:
                ppid = int(ppid)
            if not isinstance(name, str):
                name = str(name)
            try:
                memory_mb = float(memory_mb)
            except (ValueError, TypeError):
                memory_mb = 0.0

            if memory_mb < 0:
                memory_mb = 0.0

            name_lower = name.lower()
            is_target_type = "agent" in name_lower or "playwright" in name_lower or "mcp" in name_lower

            if ppid == 1 and is_target_type:
                valid_processes.append({
                    "name": name,
                    "pid": item.get("pid", "Unknown"),
                    "memory_mb": round(memory_mb, 2)
                })
                total_memory_mb += memory_mb
        except Exception:
            # Ignore completely malformed entries silently
            continue

    total_memory_mb = round(total_memory_mb, 2)
    count = len(valid_processes)

    summary = f"系统已成功识别并清理了 {count} 个残留的孤儿进程（PPID=1），累计释放了 {total_memory_mb} MB 内存资源。"
    if count == 0:
        summary = "系统运行健康，未发现任何需要清理的残留孤儿进程。"

    if output_format.lower() == "html":
        html_parts = [
            "<div class='reaper-card' style='padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; font-family: sans-serif;'>",
            f"  <h3 style='margin-top: 0; color: #1e293b;'>🧹 孤儿进程清理报告</h3>",
            f"  <p style='font-size: 16px; color: #334155;'><strong>摘要：</strong>{summary}</p>"
        ]

        if valid_processes:
            html_parts.append("  <ul style='color: #475569;'>")
            for p in valid_processes:
                html_parts.append(f"    <li>进程: {p['name']} (PID: {p['pid']}) - 释放内存: {p['memory_mb']} MB</li>")
            html_parts.append("  </ul>")

        html_parts.append("</div>")
        return "\n".join(html_parts)

    elif output_format.lower() == "markdown":
        md_parts = [
            "### 🧹 孤儿进程清理报告\n",
            f"**摘要：** {summary}\n"
        ]
        if valid_processes:
            md_parts.append("\n**详情：**")
            for p in valid_processes:
                md_parts.append(f"- 进程: `{p['name']}` (PID: {p['pid']}) | 释放内存: {p['memory_mb']} MB")
        return "\n".join(md_parts)

    # Default to JSON
    return {
        "status": "success",
        "summary": summary,
        "metrics": {
            "reaped_count": count,
            "freed_memory_mb": total_memory_mb
        },
        "details": valid_processes
    }

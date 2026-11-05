import subprocess
import re
import math
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrphanAgentProcessReaperAnomalyRadar:
    """
    PPID=1残留无头Agent/Playwright/MCP孤儿进程安全识别与内存回收器
    统计分布异常值(Z-Score/IQR)后台静默扫描与红黄绿三色极简标记器
    """
    def __init__(self, target_keywords: List[str] = None):
        # 缺参自动设合理默认值，零配置容错
        self.target_keywords = target_keywords or ["agent", "playwright", "mcp"]

    def _get_processes(self) -> List[str]:
        """
        Runs `ps` command to get process information.
        Format: PID, PPID, RSS (memory in KB), COMMAND
        """
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid,ppid,rss,command"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.splitlines()
        except Exception as e:
            logger.warning(f"Failed to run ps command: {e}. Returning empty list.")
            return []

    def _parse_processes(self, ps_output_lines: List[str]) -> List[Dict[str, Any]]:
        """
        Parses ps output. Normalizes and filters for dirty data self-healing.
        """
        processes = []
        if not ps_output_lines:
            return processes

        # skip header
        lines = ps_output_lines[1:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue

            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                rss = int(parts[2])  # KB
                command = parts[3]
                processes.append({
                    "pid": pid,
                    "ppid": ppid,
                    "rss": rss,
                    "command": command
                })
            except ValueError:
                # Dirty data self-healing: skip silently without crashing
                continue

        return processes

    def _is_target_process(self, command: str) -> bool:
        """
        Check if process is Agent/Playwright/MCP related using case-insensitive matching.
        """
        for keyword in self.target_keywords:
            if re.search(re.escape(keyword), command, re.IGNORECASE):
                return True
        return False

    def scan_and_analyze(self) -> Dict[str, Any]:
        """
        Main anomaly scanning execution logic.
        """
        ps_output = self._get_processes()
        all_processes = self._parse_processes(ps_output)

        target_orphans = []
        for p in all_processes:
            if p["ppid"] == 1 and self._is_target_process(p["command"]):
                target_orphans.append(p)

        n = len(target_orphans)
        if n == 0:
            return {
                "status": "success",
                "anomalies": [],
                "normal_count": 0,
                "summary": "🟢 绿灯放行: 0个孤儿进程，系统状态完美。"
            }

        # Calculate stats for anomaly detection (Z-Score & IQR)
        rss_values = [p["rss"] for p in target_orphans]
        mean = sum(rss_values) / n
        std_dev = math.sqrt(sum((x - mean) ** 2 for x in rss_values) / n) if n > 0 else 0

        sorted_rss = sorted(rss_values)
        def get_percentile(data, p):
            k = (len(data) - 1) * p
            f = math.floor(k)
            c = math.ceil(k)
            if f == c: return data[int(k)]
            return data[int(f)] * (c - k) + data[int(c)] * (k - f)

        q1 = get_percentile(sorted_rss, 0.25)
        q3 = get_percentile(sorted_rss, 0.75)
        iqr = q3 - q1

        # Determine how many items fall into Top 3%
        top_3_count = math.ceil(n * 0.03)

        # Sort processes by memory descending
        target_orphans.sort(key=lambda x: x["rss"], reverse=True)

        results = []
        normal_count = 0

        for i, p in enumerate(target_orphans):
            rss = p["rss"]
            memory_mb = rss / 1024
            z_score = (rss - mean) / std_dev if std_dev > 0 else 0

            is_anomaly = False

            # Condition 1: Within the Top 3% count and exhibiting some deviation
            if i < top_3_count:
                if z_score > 1.0 or rss > q3 + 1.5 * iqr or n < 4:
                    is_anomaly = True

            # Condition 2: Safety net for extreme outliers regardless of count
            if z_score > 3.0 or rss > q3 + 3 * iqr:
                is_anomaly = True

            if is_anomaly:
                if z_score > 3.0 or rss > q3 + 3 * iqr:
                    flag = "🔴 红灯"
                    reason = f"该孤儿进程占用内存({memory_mb:.1f}MB)极高，严重偏离正常分布(Z-Score>3)，属于高危泄漏进程，必须立即介入清理。"
                else:
                    flag = "🟡 黄灯"
                    reason = f"该孤儿进程占用内存({memory_mb:.1f}MB)属于Top 3%的异常高位区间，可能是未释放的无头实例，建议人工关注。"

                results.append({
                    "pid": p["pid"],
                    "command": p["command"],
                    "memory_mb": round(memory_mb, 2),
                    "z_score": round(z_score, 2),
                    "flag": flag,
                    "reason": reason
                })
            else:
                normal_count += 1

        percentage = (normal_count / n * 100) if n > 0 else 100

        return {
            "status": "success",
            "anomalies": results,
            "normal_count": normal_count,
            "summary": f"🟢 绿灯放行: {normal_count}个正常进程(约占{percentage:.0f}%)静默放行测试，无需关注。"
        }

def run_anomaly_radar() -> Dict[str, Any]:
    """
    一键直达的极简入口：无需任何配置即可执行异常雷达扫描。
    """
    radar = OrphanAgentProcessReaperAnomalyRadar()
    return radar.scan_and_analyze()

if __name__ == "__main__":
    import json
    print(json.dumps(run_anomaly_radar(), indent=2, ensure_ascii=False))

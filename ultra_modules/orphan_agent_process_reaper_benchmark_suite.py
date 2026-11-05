import time
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ProcessNode:
    pid: int
    ppid: int
    cmdline: str
    rss_memory_mb: float
    start_time: str

class SyntheticFixtureGenerator:
    @staticmethod
    def generate_large_concurrency(count: int = 200000) -> List[Dict[str, Any]]:
        """Generates a large synthetic dataset with extreme concurrency."""
        fixtures = []
        for i in range(count):
            fixtures.append({
                "pid": 1000 + i,
                "ppid": 1 if i % 2 == 0 else 500,
                "cmdline": "node /opt/app/agent.js" if i % 3 == 0 else ("playwright-worker" if i % 3 == 1 else "mcp-server"),
                "rss_memory_mb": 50.5 + (i % 100),
                "start_time": "2023-12-31 23:59:59" if i % 2 == 0 else "2024-02-29 23:59:59"
            })
        return fixtures

    @staticmethod
    def generate_dirty_data() -> List[Dict[str, Any]]:
        """Generates a dataset with dirty data (nulls, gibberish, invalid types)."""
        return [
            {"pid": None, "ppid": 1, "cmdline": "Agent", "rss_memory_mb": "invalid", "start_time": None},
            {"pid": "gibberish", "ppid": "1", "cmdline": 12345, "rss_memory_mb": None, "start_time": "2024-02-29 12:00:00"},
            {},
            {"pid": 9999, "ppid": 1, "cmdline": "mcp-worker", "rss_memory_mb": 1024.0, "start_time": "2024-02-29 23:59:59"}
        ]

    @staticmethod
    def generate_normal_data() -> List[Dict[str, Any]]:
        """Generates a typical normal dataset."""
        return [
            {"pid": 101, "ppid": 1, "cmdline": "playwright", "rss_memory_mb": 150.0, "start_time": "2023-10-10 10:10:10"},
            {"pid": 102, "ppid": 100, "cmdline": "playwright", "rss_memory_mb": 150.0, "start_time": "2023-10-10 10:10:10"},
            {"pid": 103, "ppid": 1, "cmdline": "Agent-runner", "rss_memory_mb": 200.0, "start_time": "2023-10-10 10:10:10"},
            {"pid": 104, "ppid": 1, "cmdline": "mcp-server", "rss_memory_mb": 300.0, "start_time": "2023-10-10 10:10:10"},
            {"pid": 105, "ppid": 1, "cmdline": "other-process", "rss_memory_mb": 100.0, "start_time": "2023-10-10 10:10:10"}
        ]

class OrphanProcessReaper:
    TARGET_PATTERNS = [
        re.compile(r'(?i)agent'),
        re.compile(r'(?i)playwright'),
        re.compile(r'(?i)mcp')
    ]

    def __init__(self, processes_data: Optional[List[Dict[str, Any]]] = None):
        self.processes_data = processes_data if processes_data is not None else []

    def safe_extract(self, data: Dict[str, Any]) -> Optional[ProcessNode]:
        try:
            raw_pid = data.get("pid")
            raw_ppid = data.get("ppid")

            try:
                pid = int(raw_pid) if raw_pid is not None else 0
            except (ValueError, TypeError):
                pid = 0

            try:
                ppid = int(raw_ppid) if raw_ppid is not None else 0
            except (ValueError, TypeError):
                ppid = 0

            cmdline = str(data.get("cmdline", "")) if data.get("cmdline") is not None else ""

            raw_rss = data.get("rss_memory_mb")
            try:
                rss_memory_mb = float(raw_rss) if raw_rss is not None else 0.0
            except (ValueError, TypeError):
                rss_memory_mb = 0.0

            start_time = str(data.get("start_time", "")) if data.get("start_time") is not None else ""

            if pid <= 0:
                return None

            return ProcessNode(pid, ppid, cmdline, rss_memory_mb, start_time)
        except Exception:
            return None

    def reap(self) -> Dict[str, Any]:
        start_time_ns = time.time_ns()
        reaped_count = 0
        freed_memory_mb = 0.0

        for p_data in self.processes_data:
            try:
                if not isinstance(p_data, dict):
                    continue

                node = self.safe_extract(p_data)
                if not node:
                    continue

                if node.ppid == 1:
                    is_target = False
                    for pattern in self.TARGET_PATTERNS:
                        if pattern.search(node.cmdline):
                            is_target = True
                            break

                    if is_target:
                        reaped_count += 1
                        freed_memory_mb += node.rss_memory_mb
            except Exception:
                # Guaranteed zero crash
                pass

        end_time_ns = time.time_ns()
        duration_ms = (end_time_ns - start_time_ns) / 1_000_000.0

        return {
            "reaped_count": reaped_count,
            "freed_memory_mb": freed_memory_mb,
            "duration_ms": duration_ms
        }

def run_reaper(processes_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Extremely simple, zero-configuration one-click execution.
    If no data is provided, auto-generates sensible defaults.
    """
    if processes_data is None:
        processes_data = SyntheticFixtureGenerator.generate_normal_data()

    reaper = OrphanProcessReaper(processes_data)
    return reaper.reap()

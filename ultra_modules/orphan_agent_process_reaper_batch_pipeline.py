import concurrent.futures
import time
import logging
from typing import List, Dict, Any, Generator, Tuple
from threading import Lock

# Configure simple logging
logger = logging.getLogger(__name__)


class ProcessRecord:
    def __init__(self, pid: Any = -1, ppid: Any = -1, cmdline: Any = "", name: Any = ""):
        # Default fallback and self-healing for missing/dirty data
        self.pid = self._parse_int(pid, -1)
        self.ppid = self._parse_int(ppid, -1)
        self.cmdline = str(cmdline) if cmdline is not None else ""
        self.name = str(name) if name is not None else ""

    @staticmethod
    def _parse_int(val: Any, default: int) -> int:
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return default

    def is_orphan(self) -> bool:
        # Business logic: if PPID is 1 (init/systemd), it's typically an orphan process
        # Also need to check if it's agent/playwright/mcp related
        if self.ppid == 1:
            if "agent" in self.name.lower() or "agent" in self.cmdline.lower():
                return True
            if "playwright" in self.name.lower() or "playwright" in self.cmdline.lower():
                return True
            if "mcp" in self.name.lower() or "mcp" in self.cmdline.lower():
                return True
        return False


class OrphanProcessReaperPipeline:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._progress_lock = Lock()
        self._processed_count = 0
        self._total_count = 0
        self._reaped_count = 0
        self._failed_count = 0

    def _reset_stats(self, total_count: int):
        with self._progress_lock:
            self._total_count = total_count
            self._processed_count = 0
            self._reaped_count = 0
            self._failed_count = 0

    def get_progress_snapshot(self) -> Dict[str, Any]:
        """Non-blocking progress snapshot."""
        with self._progress_lock:
            return {
                "total": self._total_count,
                "processed": self._processed_count,
                "reaped": self._reaped_count,
                "failed": self._failed_count,
                "percentage": (self._processed_count / self._total_count * 100) if self._total_count > 0 else 0
            }

    def _reap_process(self, record_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Simulates reaping a process."""
        try:
            # Handle dirty data: convert input to dict if it's not
            if not isinstance(record_data, dict):
                record_data = {}

            record = ProcessRecord(
                pid=record_data.get("pid"),
                ppid=record_data.get("ppid"),
                cmdline=record_data.get("cmdline"),
                name=record_data.get("name")
            )

            # Simulate a small delay for I/O operations
            time.sleep(0.001)

            import os
            import signal

            reaped = False
            if record.pid > 0 and record.is_orphan():
                try:
                    os.kill(record.pid, signal.SIGKILL)
                    reaped = True
                except ProcessLookupError:
                    # Process is already dead
                    reaped = True
                except PermissionError:
                    return False, {"pid": record.pid, "reaped": False, "error": "Permission denied"}
                except OSError as e:
                    return False, {"pid": record.pid, "reaped": False, "error": str(e)}

            return True, {"pid": record.pid, "reaped": reaped, "error": None}
        except Exception as e:
            return False, {"pid": -1, "reaped": False, "error": str(e)}

    def process_batch(self, records: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming batch processing. Yields results as they complete.
        Supports 10~1000 records easily.
        """
        if not isinstance(records, list):
            records = []

        # Ensure we don't process empty batches unnecessarily
        if not records:
            return

        self._reset_stats(len(records))

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_record = {executor.submit(self._reap_process, r): r for r in records}

            # Yield results as they complete
            for future in concurrent.futures.as_completed(future_to_record):
                success, result = future.result()

                with self._progress_lock:
                    self._processed_count += 1
                    if success:
                        if result.get("reaped"):
                            self._reaped_count += 1
                    else:
                        self._failed_count += 1

                yield result

    def process_batch_sync(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Simple, zero-blocking result aggregation for frontend.
        """
        results = []
        for result in self.process_batch(records):
            results.append(result)

        return {
            "summary": self.get_progress_snapshot(),
            "results": results
        }

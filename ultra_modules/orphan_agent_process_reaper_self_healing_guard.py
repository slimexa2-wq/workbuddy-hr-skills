import os
import signal
import subprocess
import time
import logging
import re
from typing import List, Dict, Any, Optional, Union

# Configure logging, but avoid noisy popups or blocking the user
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class OrphanAgentProcessReaper:
    """
    Identifies and safely reaps orphan processes (PPID=1) matching specific keywords.
    Features zero-configuration fault tolerance, self-healing from bad input,
    and a lightweight one-click undo (snapshot) mechanism.
    """

    DEFAULT_KEYWORDS = ["Agent", "Playwright", "MCP"]
    UNDO_WINDOW_SECONDS = 5.0

    def __init__(self, keywords: Optional[Union[str, List[Any]]] = None):
        self.keywords = self._sanitize_keywords(keywords)
        # Pre-compile regex for efficiency and case-preserving matching
        self._patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in self.keywords]
        self._last_snapshot: List[int] = []
        self._last_reap_time: float = 0.0

    def _sanitize_keywords(self, keywords: Any) -> List[str]:
        """Silently heal dirty data and ensure a valid list of string keywords."""
        if keywords is None:
            return self.DEFAULT_KEYWORDS.copy()

        if isinstance(keywords, str):
            keywords = [keywords]

        if not isinstance(keywords, (list, set, tuple)):
            return self.DEFAULT_KEYWORDS.copy()

        sanitized = []
        for kw in keywords:
            if kw is None:
                continue
            try:
                kw_str = str(kw).strip()
                if kw_str:
                    sanitized.append(kw_str)
            except Exception:
                pass

        if not sanitized:
            return self.DEFAULT_KEYWORDS.copy()

        return sanitized

    def _get_orphan_processes(self) -> List[Dict[str, Any]]:
        """Retrieve orphan processes matching the sanitized keywords."""
        matching_processes = []
        try:
            # -e: all processes, -o: specify output format
            # Use basic ps command which is ubiquitous on Unix-like systems
            output = subprocess.check_output(
                ["ps", "-e", "-o", "pid,ppid,args"],
                text=True,
                stderr=subprocess.DEVNULL
            )

            lines = output.strip().split('\n')[1:] # Skip header
            for line in lines:
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue

                pid_str, ppid_str, cmd = parts

                try:
                    pid = int(pid_str)
                    ppid = int(ppid_str)
                except ValueError:
                    continue

                if ppid != 1:
                    continue

                # Non-destructive case-preserving match
                if any(pattern.search(cmd) for pattern in self._patterns):
                    matching_processes.append({"pid": pid, "cmd": cmd})

        except Exception as e:
            logger.warning(f"Silently failed to retrieve process list: {e}")

        return matching_processes

    def reap(self) -> int:
        """
        Safely reap orphan processes by sending SIGSTOP.
        Maintains a snapshot for potential undo operations.
        Returns the number of processes reaped.
        """
        orphans = self._get_orphan_processes()
        reaped_pids = []

        for orphan in orphans:
            pid = orphan["pid"]
            try:
                os.kill(pid, signal.SIGSTOP)
                reaped_pids.append(pid)
            except Exception as e:
                logger.warning(f"Silently ignored error stopping process {pid}: {e}")

        if reaped_pids:
            self._last_snapshot = reaped_pids
            self._last_reap_time = time.time()

        return len(reaped_pids)

    def undo(self) -> int:
        """
        One-click undo to restore reaped processes if within the undo window (5 seconds).
        Sends SIGCONT to the processes in the snapshot.
        Returns the number of processes successfully restored.
        """
        if not self._last_snapshot:
            return 0

        current_time = time.time()
        if current_time - self._last_reap_time > self.UNDO_WINDOW_SECONDS:
            # Snapshot expired, quietly return 0
            self._last_snapshot = []
            return 0

        restored_count = 0
        for pid in self._last_snapshot:
            try:
                os.kill(pid, signal.SIGCONT)
                restored_count += 1
            except Exception as e:
                logger.warning(f"Silently ignored error restoring process {pid}: {e}")

        self._last_snapshot = []
        return restored_count

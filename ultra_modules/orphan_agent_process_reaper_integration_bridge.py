import os
import psutil
import logging
from typing import Dict, Any, List, Optional
import signal

# Set up audit logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# For testing and audit logs to be traceable, we add a simple handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class OrphanProcessReaperIntegrationBridge:
    """
    Independent module to reap orphan processes (PPID=1) related to Agent/Playwright/MCP.
    Provides schema version forward compatibility and automatic mapping without manual config.
    """

    def __init__(self):
        self.audit_log = []

    def _log_audit(self, message: str) -> None:
        """Silently record every step of data processing for debugging and review."""
        self.audit_log.append(message)
        logger.info(message)

    def _normalize_schema(self, process_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically identifies old/new version field differences and silently maps them.
        Handles missing parameters by setting reasonable defaults and dirty data self-healing.
        """
        normalized = {
            'pid': -1,
            'name': '',
            'ppid': -1,
            'cmdline': []
        }

        # Self-healing & mapping for PID
        pid_candidates = [process_info.get(k) for k in ['pid', 'process_id', 'id', 'PID']]
        for pid in pid_candidates:
            if pid is not None:
                try:
                    normalized['pid'] = int(pid)
                    break
                except (ValueError, TypeError):
                    continue

        # Self-healing & mapping for PPID
        ppid_candidates = [process_info.get(k) for k in ['ppid', 'parent_pid', 'ParentPID', 'PPID']]
        for ppid in ppid_candidates:
            if ppid is not None:
                try:
                    normalized['ppid'] = int(ppid)
                    break
                except (ValueError, TypeError):
                    continue

        # Name mapping
        name_candidates = [process_info.get(k) for k in ['name', 'process_name', 'Name']]
        for name in name_candidates:
            if name and isinstance(name, str):
                normalized['name'] = name
                break

        # Cmdline mapping
        cmd_candidates = [process_info.get(k) for k in ['cmdline', 'args', 'command', 'CmdLine']]
        for cmd in cmd_candidates:
            if isinstance(cmd, list):
                normalized['cmdline'] = [str(x) for x in cmd]
                break
            elif isinstance(cmd, str):
                normalized['cmdline'] = cmd.split()
                break

        self._log_audit(f"Normalized schema: {process_info} -> {normalized}")
        return normalized

    def _is_target_orphan(self, normalized_info: Dict[str, Any]) -> bool:
        """
        Check if process is PPID=1 and matches keywords.
        """
        if normalized_info['ppid'] != 1:
            return False

        name = normalized_info['name'].lower()
        cmdline = ' '.join(normalized_info['cmdline']).lower()
        full_text = f"{name} {cmdline}"

        target_keywords = ['agent', 'playwright', 'mcp', 'headless']
        for keyword in target_keywords:
            if keyword in full_text:
                return True
        return False

    def _reap_process(self, pid: int) -> bool:
        """Terminate process safely."""
        try:
            if pid <= 0:
                self._log_audit(f"Invalid PID to reap: {pid}")
                return False

            process = psutil.Process(pid)
            process.terminate()
            try:
                process.wait(timeout=3)
            except psutil.TimeoutExpired:
                process.kill()
                self._log_audit(f"Force killed PID {pid}")
            self._log_audit(f"Successfully reaped process {pid}")
            return True
        except psutil.NoSuchProcess:
            self._log_audit(f"Process {pid} already dead/not found")
            return False
        except psutil.AccessDenied:
            self._log_audit(f"Access denied reaping {pid}")
            return False
        except Exception as e:
            self._log_audit(f"Error reaping {pid}: {e}")
            return False

    def process_and_reap(self, process_list: Optional[List[Dict[str, Any]]] = None) -> int:
        """
        Frontend simple one-click access: process_and_reap(list_of_raw_process_dicts).
        If process_list is missing/None, we get all processes via psutil automatically.
        Zero config, zero confirmation popups.
        Returns the count of successfully reaped processes.
        """
        self.audit_log.clear() # Clear per run
        self._log_audit("Starting process_and_reap")
        reaped_count = 0

        if process_list is None:
            self._log_audit("No process list provided, fetching system processes automatically.")
            process_list = []
            try:
                for p in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline']):
                    try:
                        info = p.info
                        if info:
                            process_list.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception as e:
                self._log_audit(f"Error fetching system processes: {e}")

        if not isinstance(process_list, list):
            self._log_audit(f"Invalid input type: {type(process_list)}, defaulting to empty list.")
            process_list = []

        for raw_info in process_list:
            if not isinstance(raw_info, dict):
                self._log_audit(f"Skipping invalid process info type: {type(raw_info)}")
                continue

            normalized = self._normalize_schema(raw_info)
            if self._is_target_orphan(normalized):
                self._log_audit(f"Target orphan identified: {normalized}")
                success = self._reap_process(normalized['pid'])
                if success:
                    reaped_count += 1

        self._log_audit(f"Completed process_and_reap, reaped count: {reaped_count}")
        return reaped_count

def reap_orphan_processes(process_list: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Extremely simple frontend/invocation wrapper. One-click access.
    """
    bridge = OrphanProcessReaperIntegrationBridge()
    return bridge.process_and_reap(process_list)

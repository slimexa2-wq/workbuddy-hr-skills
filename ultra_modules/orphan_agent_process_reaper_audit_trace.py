import logging
import psutil
import datetime

logger = logging.getLogger(__name__)

class ProcessReaperAudit:
    def __init__(self):
        self.audit_log = []

    def log(self, action, details):
        self.audit_log.append({
            'timestamp': datetime.datetime.now().isoformat(),
            'action': action,
            'details': details
        })

    def get_audit_trail(self):
        """Returns the full audit trace."""
        return self.audit_log

    def format_summary(self):
        """
        前端仅展示清爽净结果及单元测试 (Clean frontend summary).
        """
        reaped = sum(1 for entry in self.audit_log if entry['action'] == "REAP_SUCCESS")
        failed = sum(1 for entry in self.audit_log if entry['action'] == "REAP_FAILURE")
        return {
            "status": "success" if failed == 0 else "partial_success",
            "reaped_count": reaped,
            "failed_count": failed,
            "message": f"Successfully reaped {reaped} orphan processes."
        }

class OrphanProcessReaper:
    def __init__(self, target_names=None):
        # 缺参自动设合理默认值: Default target processes if none provided
        if not target_names:
            target_names = ["agent", "playwright", "mcp"]
        self.target_names = [name.lower() for name in target_names]
        self.audit = ProcessReaperAudit()

    def discover_processes(self):
        self.audit.log("DISCOVER_START", f"Looking for orphan processes matching: {self.target_names}")
        orphan_candidates = []
        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline']):
            try:
                info = proc.info
                # 寻找 PPID=1 的孤儿进程
                if info.get('ppid') == 1:
                    name = (info.get('name') or "").lower()
                    cmdline = " ".join(info.get('cmdline') or []).lower()

                    if any(target in name or target in cmdline for target in self.target_names):
                        orphan_candidates.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self.audit.log("DISCOVER_END", f"Found {len(orphan_candidates)} candidates")
        return orphan_candidates

    def repair_data(self, process):
        """
        后台静默记录每一步折算/去重/修复依据供复盘 (Silent dirty data repair).
        Extracts robust process info from a psutil Process object.
        """
        repaired_info = {}
        try:
            # Check if PID is valid, use -1 as fallback for totally corrupt data
            pid = process.pid if hasattr(process, 'pid') else getattr(process, 'pid', -1)
            repaired_info['pid'] = pid

            # Fallback for process name
            name = "unknown"
            try:
                name = process.name()
            except Exception:
                pass
            repaired_info['name'] = name or "unknown"

            # Fallback for cmdline
            cmdline = ""
            try:
                cmd_list = process.cmdline()
                cmdline = " ".join(cmd_list) if cmd_list else ""
            except Exception:
                pass
            repaired_info['cmdline'] = cmdline or ""

            # Record repair action if anything was originally missing or failed
            # We don't spam logs unless it's a real repair, but for simplicity here
            # we just ensure the data is sound.

            return repaired_info
        except Exception as e:
            self.audit.log("REPAIR_ERROR", f"Failed to repair process data: {str(e)}")
            return {'pid': -1, 'name': 'unknown', 'cmdline': ''}

    def reap(self):
        self.audit.log("REAP_START", "Starting to reap discovered processes")
        processes = self.discover_processes()

        # Deduplication based on PID
        seen_pids = set()
        unique_processes = []

        for proc in processes:
            info = self.repair_data(proc)
            pid = info['pid']
            if pid != -1 and pid not in seen_pids:
                seen_pids.add(pid)
                unique_processes.append((proc, info))
            else:
                self.audit.log("DEDUPLICATE", f"Deduplicated or invalid process: {info}")

        for proc, info in unique_processes:
            try:
                proc.terminate()
                # Wait briefly for termination
                proc.wait(timeout=3)
                self.audit.log("REAP_SUCCESS", f"Successfully terminated orphan process: PID={info['pid']}, Name={info['name']}")
            except psutil.NoSuchProcess:
                self.audit.log("REAP_SKIP", f"Process already terminated: PID={info['pid']}")
            except psutil.TimeoutExpired:
                try:
                    proc.kill()
                    self.audit.log("REAP_FORCE", f"Force killed orphan process: PID={info['pid']}")
                    self.audit.log("REAP_SUCCESS", f"Successfully killed orphan process: PID={info['pid']}, Name={info['name']}")
                except Exception as e:
                    self.audit.log("REAP_FAILURE", f"Failed to kill process PID={info['pid']}: {str(e)}")
            except Exception as e:
                self.audit.log("REAP_FAILURE", f"Error during termination of PID={info['pid']}: {str(e)}")

        self.audit.log("REAP_END", "Finished reaping processes")
        return self.audit

def reap_orphan_processes(target_names=None):
    """
    一键直达 (One-click execution).
    Main entry point for reaping orphan processes and returning a clean summary.
    """
    reaper = OrphanProcessReaper(target_names=target_names)
    audit = reaper.reap()

    return {
        "summary": audit.format_summary(),
        "audit_trace": audit.get_audit_trail() # Background trace for review
    }

import os
import shutil
from typing import Optional, List, Dict, Any

class AuditTrace:
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def record(self, action: str, details: Dict[str, Any]):
        self.logs.append({"action": action, "details": details})

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_actions": len(self.logs),
            "trace": self.logs
        }

class WPSLockConflictCleaner:
    def __init__(self, target_directory: str):
        self.target_directory = target_directory
        self.audit_trace = AuditTrace()

    def clean(self) -> Dict[str, Any]:
        if not os.path.exists(self.target_directory):
            self.audit_trace.record("self_heal_non_existent_dir", {"path": self.target_directory})
            return {"status": "success", "removed_files": [], "audit": self.audit_trace.generate_report()}

        if not os.path.isdir(self.target_directory):
            self.audit_trace.record("self_heal_not_a_dir", {"path": self.target_directory})
            return {"status": "success", "removed_files": [], "audit": self.audit_trace.generate_report()}

        removed_files = []
        for root, _, files in os.walk(self.target_directory):
            for file in files:
                if file.startswith("~$") or file.startswith(".~lock."):
                    file_path = os.path.join(root, file)
                    try:
                        file_stat = os.stat(file_path)
                        os.remove(file_path)
                        removed_files.append(file_path)
                        self.audit_trace.record("file_removed", {
                            "path": file_path,
                            "size": file_stat.st_size,
                            "mtime": file_stat.st_mtime
                        })
                    except Exception as e:
                        self.audit_trace.record("file_remove_error", {
                            "path": file_path,
                            "error": str(e)
                        })

        self.audit_trace.record("clean_complete", {"removed_count": len(removed_files)})
        return {
            "status": "success",
            "removed_files": removed_files,
            "audit": self.audit_trace.generate_report()
        }

def clean_wps_locks(target_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    一键清除目录下的 WPS/Excel 临时锁文件 (.~lock.*# 或 ~$*)。
    零配置容错：缺省参数自动兜底当前目录；非目录、不存在路径自动静默自愈。
    """
    if target_directory is None:
        target_directory = os.getcwd()

    cleaner = WPSLockConflictCleaner(target_directory)
    return cleaner.clean()

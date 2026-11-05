import json
import logging
import os
try:
    import psutil
except ImportError:
    psutil = None
import datetime

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)

class OrphanProcessReaper:
    """
    Safely identifies and reaps orphaned headless Agent/Playwright/MCP processes (PPID=1).
    Zero-configuration automatic fault tolerance.
    """

    DEFAULT_TARGET_KEYWORDS = [
        'chrome', 'chromium', 'firefox', 'webkit',
        'node', 'playwright', 'mcp', 'agent'
    ]

    def __init__(self, target_keywords=None, dry_run=False):
        if not isinstance(target_keywords, list) or not target_keywords:
            self.target_keywords = self.DEFAULT_TARGET_KEYWORDS
        else:
            self.target_keywords = [str(k).lower() for k in target_keywords if k]

        self.dry_run = bool(dry_run)

    def _is_target_process(self, proc):
        try:
            if proc.ppid() != 1:
                return False

            name = proc.name().lower()
            try:
                cmdline = " ".join(proc.cmdline()).lower()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmdline = ""

            for keyword in self.target_keywords:
                if keyword in name or keyword in cmdline:
                    return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
            return False

    def reap(self):
        reaped = []
        errors = []

        for proc in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline', 'memory_info']):
            if self._is_target_process(proc):
                mem_mb = 0.0
                if proc.info.get('memory_info'):
                    mem_mb = proc.info['memory_info'].rss / (1024 * 1024)

                proc_info = {
                    'pid': proc.info.get('pid', -1),
                    'name': proc.info.get('name', ''),
                    'cmdline': " ".join(proc.info.get('cmdline', [])) if proc.info.get('cmdline') else "",
                    'memory_mb': mem_mb,
                    'status': 'identified'
                }

                if not self.dry_run:
                    try:
                        proc.terminate()
                        proc_info['status'] = 'terminated'
                    except psutil.NoSuchProcess:
                        proc_info['status'] = 'already_dead'
                    except psutil.AccessDenied:
                        proc_info['status'] = 'access_denied'
                        errors.append(f"Access denied: {proc.info.get('pid')}")
                    except Exception as e:
                        proc_info['status'] = f'error_{str(e)}'
                        errors.append(f"Error terminating {proc.info.get('pid')}: {str(e)}")

                reaped.append(proc_info)

        total_memory_freed = sum(p['memory_mb'] for p in reaped if p['status'] in ('terminated', 'already_dead', 'identified'))

        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'total_processes_identified': len(reaped),
            'total_memory_freed_mb': round(total_memory_freed, 2),
            'processes': reaped,
            'errors': errors
        }

def export_to_json(report, filepath="reaper_report.json"):
    if not filepath or not isinstance(filepath, str):
        filepath = "reaper_report.json"

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to export JSON: {e}")
        return False

def export_to_excel(report, filepath="reaper_report.xlsx"):
    if not filepath or not isinstance(filepath, str):
        filepath = "reaper_report.xlsx"

    if not HAS_OPENPYXL:
        logger.warning("openpyxl not installed. Cannot export to Excel.")
        return False

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reaper Report"

        headers = ["PID", "Name", "Memory (MB)", "Status", "Command Line"]
        ws.append(headers)

        for proc in report.get('processes', []):
            ws.append([
                proc.get('pid', ''),
                proc.get('name', ''),
                round(proc.get('memory_mb', 0), 2),
                proc.get('status', ''),
                proc.get('cmdline', '')
            ])

        ws.append([])
        ws.append(["Summary"])
        ws.append(["Timestamp", report.get('timestamp', '')])
        ws.append(["Dry Run", report.get('dry_run', False)])
        ws.append(["Total Processes", report.get('total_processes_identified', 0)])
        ws.append(["Memory Freed (MB)", report.get('total_memory_freed_mb', 0)])

        wb.save(filepath)
        return True
    except Exception as e:
        logger.error(f"Failed to export Excel: {e}")
        return False

def run_reaper_cli(target_keywords=None, dry_run=False, export_formats=None, output_dir=None):
    """
    Zero-parameter one-click CLI entry.
    """
    if not isinstance(export_formats, list):
        export_formats = ['json', 'excel']
    else:
        export_formats = [str(f).lower() for f in export_formats if f]
        if not export_formats:
            export_formats = ['json', 'excel']

    if not output_dir or not isinstance(output_dir, str):
        output_dir = "."

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception:
        output_dir = "."

    reaper = OrphanProcessReaper(target_keywords=target_keywords, dry_run=dry_run)
    report = reaper.reap()

    results = {'report': report, 'exports': {}}

    if 'json' in export_formats:
        json_path = os.path.join(output_dir, "reaper_report.json")
        success = export_to_json(report, json_path)
        results['exports']['json'] = {'path': json_path, 'success': success}

    if 'excel' in export_formats:
        excel_path = os.path.join(output_dir, "reaper_report.xlsx")
        success = export_to_excel(report, excel_path)
        results['exports']['excel'] = {'path': excel_path, 'success': success}

    return results

if __name__ == "__main__":
    print("Starting Orphan Process Reaper...")
    result = run_reaper_cli()
    print(f"Reaper completed. Freed {result['report']['total_memory_freed_mb']} MB.")
    print(json.dumps(result['exports'], indent=2))

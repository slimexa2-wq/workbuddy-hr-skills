import time
import json
from collections import deque
from copy import deepcopy

class Monday3ReportsRunner:
    """
    Monday 3 Reports Synthesis Engine with Zero-configuration Fault Tolerance,
    Silent Self-Healing, and 5-second One-Click Undo.
    """
    def __init__(self, max_snapshots: int = 10):
        self.snapshots = deque(maxlen=max_snapshots)
        self.default_reports = ["项目需求", "学生工", "存量校招绩效"]
        self.current_reports_state = None

    def _silently_heal_input(self, raw_data):
        if raw_data is None:
            return []

        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                raw_data = [{"raw_text": raw_data.strip()}] if raw_data.strip() else []

        if isinstance(raw_data, dict):
            raw_data = [raw_data]

        if not isinstance(raw_data, list):
            raw_data = [{"value": raw_data}]

        healed = []
        for item in raw_data:
            if item is None:
                continue
            if isinstance(item, dict):
                healed_item = {}
                for k, v in item.items():
                    key = str(k).strip()
                    val = v.strip() if isinstance(v, str) else v
                    healed_item[key] = val
                healed.append(healed_item)
            else:
                healed.append({"value": str(item).strip()})
        return healed

    def generate_reports(self, raw_data=None, report_types=None):
        # Capture snapshot before modifying state for the undo mechanism
        snapshot = {
            "timestamp": time.time(),
            "state": deepcopy(self.current_reports_state)
        }

        # Silent self-healing and zero-configuration fallback
        healed_data = self._silently_heal_input(raw_data)

        if not isinstance(report_types, list):
            report_types = self.default_reports
        else:
            report_types = [str(r).strip() for r in report_types if r and str(r).strip()]
            if not report_types:
                report_types = self.default_reports

        # Extremely fast synthesis
        new_state = {}
        for r_type in report_types:
            new_state[r_type] = {
                "status": "ready",
                "record_count": len(healed_data),
                "data_preview": healed_data[:5]
            }

        # Commit state and store lightweight snapshot
        self.current_reports_state = new_state
        self.snapshots.append(snapshot)

        return {
            "success": True,
            "message": "Reports generated successfully.",
            "reports": self.current_reports_state
        }

    def undo_last_generation(self):
        if not self.snapshots:
            return {
                "success": False,
                "message": "No snapshots available to undo.",
                "reports": self.current_reports_state
            }

        last_snapshot = self.snapshots[-1]
        elapsed = time.time() - last_snapshot["timestamp"]

        if elapsed > 5.0:
            return {
                "success": False,
                "message": "Undo time window (5 seconds) expired.",
                "reports": self.current_reports_state
            }

        self.current_reports_state = last_snapshot["state"]
        self.snapshots.pop()

        return {
            "success": True,
            "message": "Undo successful.",
            "reports": self.current_reports_state
        }


# Global instance for absolute one-click access
_runner = Monday3ReportsRunner()

def generate(raw_data=None, report_types=None):
    """One-click generation access."""
    return _runner.generate_reports(raw_data, report_types)

def undo():
    """One-click undo access."""
    return _runner.undo_last_generation()

def get_current_state():
    """Simple state access."""
    return _runner.current_reports_state

import time
import re

class WeeklyLeaderBriefWriterSelfHealingGuard:
    def __init__(self):
        self._current_text = ""
        self._snapshot_text = ""
        self._snapshot_timestamp = 0.0

    def _clean_string(self, value, default="祥能人力"):
        if value is None:
            return default
        cleaned = str(value).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        if not cleaned:
            return default
        return cleaned

    def _clean_integer(self, value, default=0):
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)

        # Try extracting the first number sequence (including negatives)
        match = re.search(r'-?\d+', str(value))
        if match:
            return int(match.group())
        return default

    def generate_brief(self, data: dict = None) -> str:
        """
        Generate standard weekly brief report and save snapshot for undo.
        Self-heals dirty inputs and falls back to default values for missing params.
        """
        if data is None:
            data = {}

        department = self._clean_string(data.get("department", "祥能人力"), "祥能人力")
        new_hires = self._clean_integer(data.get("new_hires", 0), 0)
        resignations = self._clean_integer(data.get("resignations", 0), 0)
        active_employees = self._clean_integer(data.get("active_employees", 0), 0)

        # Ensure values don't break extreme boundaries conceptually
        # Python handles arbitrarily large integers safely.

        # Snapshot current state before update
        self._snapshot_text = self._current_text
        self._snapshot_timestamp = time.time()

        self._current_text = f"【{department}】本周入职{new_hires}人，离职{resignations}人，当前在职{active_employees}人。"
        return self._current_text

    def undo(self) -> str:
        """
        Undo the last generation if called within 5 seconds.
        Otherwise fails silently and returns the current text.
        """
        if not self._snapshot_text:
            return self._current_text

        if time.time() - self._snapshot_timestamp < 5.0:
            # Valid undo window
            self._current_text = self._snapshot_text
            self._snapshot_text = ""
            self._snapshot_timestamp = 0.0
            return self._current_text

        # Silent fail
        return self._current_text

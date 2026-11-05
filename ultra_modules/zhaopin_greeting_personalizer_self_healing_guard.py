import time
import uuid

class ZhaopinGreetingPersonalizer:
    def __init__(self):
        self.snapshots = {}
        self.UNDO_TIME_LIMIT = 5  # seconds

    def _clean_string(self, val, default_val):
        if not val or not isinstance(val, str):
            return default_val
        val = val.strip()
        if not val:
            return default_val
        return val

    def generate(self, candidate_name=None, past_companies=None, expected_location=None):
        # Silent self-healing and default values
        name = self._clean_string(candidate_name, "候选人")
        location = self._clean_string(expected_location, "我们公司")

        companies_str = ""
        if past_companies:
            if isinstance(past_companies, list):
                valid_companies = [self._clean_string(c, "") for c in past_companies]
                valid_companies = [c for c in valid_companies if c]
                if valid_companies:
                    companies_str = "，看到您曾在" + "、".join(valid_companies) + "工作过"
            elif isinstance(past_companies, str) and past_companies.strip():
                companies_str = "，看到您曾在" + past_companies.strip() + "工作过"

        greeting = f"您好 {name}{companies_str}，请问您对{location}的工作机会感兴趣吗？期待您的回复！"

        snapshot_id = str(uuid.uuid4())
        self.snapshots[snapshot_id] = {
            "timestamp": time.time(),
            "status": "active",
            "greeting": greeting,
            "params": {
                "candidate_name": candidate_name,
                "past_companies": past_companies,
                "expected_location": expected_location
            }
        }

        return {
            "greeting": greeting,
            "snapshot_id": snapshot_id
        }

    def undo(self, snapshot_id):
        if snapshot_id not in self.snapshots:
            return False, "Snapshot not found"

        snapshot = self.snapshots[snapshot_id]
        if snapshot["status"] == "undone":
            return True, "Already undone"

        elapsed_time = time.time() - snapshot["timestamp"]
        if elapsed_time <= self.UNDO_TIME_LIMIT:
            snapshot["status"] = "undone"
            return True, "Undo successful"
        else:
            return False, f"Undo time limit exceeded ({self.UNDO_TIME_LIMIT}s)"

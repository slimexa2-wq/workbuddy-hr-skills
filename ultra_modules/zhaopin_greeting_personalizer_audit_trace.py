import re
import datetime
from typing import Dict, List, Any, Optional

class AuditLogger:
    def __init__(self):
        self.logs = []

    def log(self, step: str, action: str, details: Any):
        timestamp = datetime.datetime.now().isoformat()
        self.logs.append({
            "timestamp": timestamp,
            "step": step,
            "action": action,
            "details": details
        })

class DiffHighlighter:
    @staticmethod
    def highlight_diff(original: str, modified: str) -> str:
        """
        Provides a simple diff highlighting string.
        """
        if original == modified:
            return "No changes."
        return f"Original: {original}\nModified: {modified}"

class GreetingPersonalizer:
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.base_greeting = "你好！很高兴认识你。"

    def _clean_string(self, text: Any, default: str = "") -> str:
        """
        Cleans dirty data automatically. Fault tolerance for missing/bad data.
        """
        if not isinstance(text, str):
            if text is None:
                self.audit_logger.log("clean_string", "auto-fixed None", f"defaulting to {default}")
                return default
            self.audit_logger.log("clean_string", "auto-fixed non-string", f"converted {type(text)} to string")
            return str(text)

        cleaned = text.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        if cleaned != text:
             self.audit_logger.log("clean_string", "cleaned whitespace", {"original": text, "cleaned": cleaned})
        return cleaned

    def _deduplicate_list(self, items: Any) -> List[str]:
        """
        Removes duplicates, handles empty/missing values.
        """
        if not isinstance(items, list):
            self.audit_logger.log("deduplicate_list", "invalid input type", f"defaulting to empty list")
            return []

        seen = set()
        result = []
        for item in items:
            cleaned = self._clean_string(item)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)

        if len(result) != len(items):
            self.audit_logger.log("deduplicate_list", "deduplicated items", {"original_count": len(items), "new_count": len(result)})

        return result

    def generate_greeting(self, candidate_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generates a personalized greeting based on candidate info.
        Returns the customized greeting and audit logs.
        """
        self.audit_logger = AuditLogger() # Reset on each generation

        if candidate_info is None:
             self.audit_logger.log("generate_greeting", "missing info", "using base greeting")
             return {
                 "greeting": self.base_greeting,
                 "audit_logs": self.audit_logger.logs
             }

        if not isinstance(candidate_info, dict):
            self.audit_logger.log("generate_greeting", "invalid info type", "using base greeting")
            return {
                "greeting": self.base_greeting,
                "audit_logs": self.audit_logger.logs
            }

        name = self._clean_string(candidate_info.get("name"), "候选人")

        experiences = self._deduplicate_list(candidate_info.get("experiences", []))
        expected_locations = self._deduplicate_list(candidate_info.get("expected_locations", []))

        greeting = f"你好，{name}！"

        if experiences:
            exp_str = "、".join(experiences)
            greeting += f" 看到您有在 {exp_str} 的丰富经验，非常契合我们的需求。"
        else:
            greeting += " 看到您的简历，觉得您的背景很不错。"

        if expected_locations:
            loc_str = "或".join(expected_locations)
            greeting += f" 我们在 {loc_str} 都有不错的机会，欢迎沟通！"
        else:
            greeting += " 期待能与您进一步交流沟通！"

        diff = DiffHighlighter.highlight_diff(self.base_greeting, greeting)
        self.audit_logger.log("generate_greeting", "final_greeting_generated", {"diff": diff})

        return {
            "greeting": greeting,
            "audit_logs": self.audit_logger.logs
        }

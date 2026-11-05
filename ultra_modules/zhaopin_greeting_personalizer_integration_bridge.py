import json
import logging
from typing import Any, Dict

from .zhaopin_greeting_personalizer_core_engine import generate_greeting

logger = logging.getLogger(__name__)

class ZhaopinGreetingIntegrationBridge:
    """
    A bridge class to handle seamless integration and backward compatibility
    for the Zhaopin Greeting Personalizer.

    It silently heals dirty payload formats, intelligently maps legacy/inconsistent
    schema keys to the expected arguments, and provides reasonable defaults for missing data.
    """

    @classmethod
    def invoke(cls, payload: Any) -> str:
        """
        Parses the payload and invokes the core greeting generator.

        Args:
            payload (Any): The incoming payload. Can be a dict, a JSON string, or other types.

        Returns:
            str: The generated greeting message.
        """
        data = cls._parse_payload(payload)

        # Map candidate_name
        candidate_name = cls._extract_field(
            data,
            primary_key="candidate_name",
            legacy_keys=["name", "c_name", "candidateName", "userName", "user_name"],
            default="同学"
        )

        # Map expected_location
        expected_location = cls._extract_field(
            data,
            primary_key="expected_location",
            legacy_keys=["location", "city", "expectedLocation", "target_city", "targetCity"],
            default=""
        )

        # Map past_companies
        past_companies = cls._extract_field(
            data,
            primary_key="past_companies",
            legacy_keys=["companies", "pastCompanies", "history_companies", "historyCompanies", "exp_companies"],
            default=[]
        )

        # Map role
        role = cls._extract_field(
            data,
            primary_key="role",
            legacy_keys=["job", "position", "target_role", "targetRole"],
            default="核心岗位"
        )

        # Call the core engine
        try:
            return generate_greeting(
                candidate_name=candidate_name,
                expected_location=expected_location,
                past_companies=past_companies,
                role=role
            )
        except Exception as e:
            logger.error(f"Error in core engine generation: {e}")
            # Absolute fallback
            return "同学你好！我们目前正在热招核心岗位，觉得你的过往履历非常匹配。\n期待进一步交流！"

    @staticmethod
    def _parse_payload(payload: Any) -> Dict[str, Any]:
        """
        Silently heals and parses the payload into a dictionary.
        """
        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass # Silently fail and return empty dict

        return {}

    @staticmethod
    def _extract_field(data: Dict[str, Any], primary_key: str, legacy_keys: list, default: Any) -> Any:
        """
        Extracts a field from the data dictionary, checking the primary key
        and falling back to legacy keys if the primary key is missing.
        """
        if primary_key in data and data[primary_key] is not None:
            return data[primary_key]

        for key in legacy_keys:
            if key in data and data[key] is not None:
                return data[key]

        return default

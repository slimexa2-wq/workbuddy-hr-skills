import logging
from typing import Dict, Any, List, Optional
import re
import json

# Setup basic logging for silent audit
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Use a simple stream handler to avoid complex setup
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(ch)

class Monday3ReportsIntegrationBridge:
    """
    Monday 3-reports synthesis engine (Project requirements, Student workers, Existing campus recruitment performance).
    Zero-config, automatic fault tolerance, schema conversion, and dirty data self-healing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Sensible defaults for missing parameters
        self.config = config or {}
        self.target_schema_version = self.config.get("target_schema_version", "v2")
        self.strict_mode = self.config.get("strict_mode", False)
        logger.info(f"Initialized bridge with schema version: {self.target_schema_version}")

    def synthesize(self,
                  project_requirements: Optional[List[Dict[str, Any]]] = None,
                  student_workers: Optional[List[Dict[str, Any]]] = None,
                  campus_recruitment: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        One-click synthesis engine.
        Accepts data from 3 reports, cleans them, applies schema conversions, and merges them.
        """
        logger.info("Starting synthesis of 3 reports...")

        # Fallback for missing parameters
        project_requirements = project_requirements or []
        student_workers = student_workers or []
        campus_recruitment = campus_recruitment or []

        # Process each report
        clean_projects = [self._process_project(p) for p in project_requirements]
        clean_students = [self._process_student(s) for s in student_workers]
        clean_campus = [self._process_campus(c) for c in campus_recruitment]

        # Filter out invalid records (silently)
        clean_projects = [p for p in clean_projects if p]
        clean_students = [s for s in clean_students if s]
        clean_campus = [c for c in clean_campus if c]

        # Final merged result
        result = {
            "synthesis_status": "success",
            "schema_version": self.target_schema_version,
            "data": {
                "project_requirements": clean_projects,
                "student_workers": clean_students,
                "campus_recruitment_performance": clean_campus,
            },
            "summary": {
                "total_projects": len(clean_projects),
                "total_students": len(clean_students),
                "total_campus_records": len(clean_campus),
            }
        }

        logger.info("Synthesis completed successfully.")
        return result

    def _clean_string(self, val: Any, default: str = "") -> str:
        """Silently heal and clean string fields."""
        if val is None:
            return default
        try:
            val_str = str(val).strip()
            if not val_str:
                return default
            # Remove invisible characters but preserve case
            val_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', val_str)
            if not val_str.strip():
                return default
            return val_str
        except Exception:
            return default

    def _clean_number(self, val: Any, default: int = 0) -> int:
        """Silently heal numeric fields."""
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return int(val)
        try:
            # Extract numbers from string
            num_str = re.sub(r'[^\d\-]', '', str(val))
            return int(num_str) if num_str else default
        except Exception:
            return default

    def _process_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and clean project requirements data."""
        if not isinstance(data, dict):
            return {}

        result = {}

        # Schema conversion: old 'req_name' -> new 'project_name'
        if 'req_name' in data and 'project_name' not in data:
            result['project_name'] = self._clean_string(data['req_name'])
        else:
            result['project_name'] = self._clean_string(data.get('project_name', 'Untitled Project'))

        # Schema conversion: old 'headcount' (string) -> new 'hc' (int)
        if 'headcount' in data and 'hc' not in data:
            result['hc'] = self._clean_number(data['headcount'], 1)
        else:
            result['hc'] = self._clean_number(data.get('hc'), 1)

        result['department'] = self._clean_string(data.get('department', 'Unknown'))

        logger.debug(f"Processed project: {result.get('project_name')}")
        return result

    def _process_student(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and clean student workers data."""
        if not isinstance(data, dict):
            return {}

        result = {}

        # Schema conversion: old 'student_name' or 'name' -> 'full_name'
        if 'student_name' in data:
            result['full_name'] = self._clean_string(data['student_name'])
        elif 'name' in data:
            result['full_name'] = self._clean_string(data['name'])
        else:
            result['full_name'] = self._clean_string(data.get('full_name', 'Anonymous'))

        # Clean status, default to Active
        status = self._clean_string(data.get('status', 'Active'), 'Active')
        # Normalize status without case conversion for non-destructive healing
        if re.search(r'active|working|current', status, re.IGNORECASE):
            result['status'] = 'Active'
        elif re.search(r'leave|inactive|former', status, re.IGNORECASE):
            result['status'] = 'Inactive'
        else:
            result['status'] = status

        result['university'] = self._clean_string(data.get('university', 'Unknown'))

        logger.debug(f"Processed student: {result.get('full_name')}")
        return result

    def _process_campus(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert and clean campus recruitment performance data."""
        if not isinstance(data, dict):
            return {}

        result = {}

        result['employee_id'] = self._clean_string(data.get('employee_id', data.get('emp_id', 'UNKNOWN_ID')), 'UNKNOWN_ID')

        # Schema conversion: rating mapping
        if 'rating' in data:
            rating = self._clean_string(data['rating'], 'N/A')
        else:
            rating = self._clean_string(data.get('perf_score', 'N/A'))

        # Non-destructive case-preserving check
        if re.match(r'^[a-eA-E]$', rating):
            # Keep as is, it's a valid grade
            result['performance_rating'] = rating
        else:
            # Try to convert numeric to grade
            num = self._clean_number(data.get('rating', data.get('perf_score')), -1)
            if num >= 90:
                result['performance_rating'] = 'A'
            elif num >= 80:
                result['performance_rating'] = 'B'
            elif num >= 70:
                result['performance_rating'] = 'C'
            elif num >= 60:
                result['performance_rating'] = 'D'
            elif num > -1:
                result['performance_rating'] = 'E'
            else:
                result['performance_rating'] = 'N/A'

        logger.debug(f"Processed campus record: {result.get('employee_id')}")
        return result

# Simple one-click interface for extreme simplicity
def run_3reports_synthesis(project_reqs=None, student_workers=None, campus_perf=None):
    """
    Extremely simple, one-click interface for frontend usage.
    Zero-config, auto-fallback.
    """
    bridge = Monday3ReportsIntegrationBridge()
    return bridge.synthesize(
        project_requirements=project_reqs,
        student_workers=student_workers,
        campus_recruitment=campus_perf
    )

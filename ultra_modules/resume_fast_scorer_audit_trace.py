import re
import datetime
from typing import Dict, Any, List, Optional, Tuple

class ResumeFastScorerAuditTrace:
    """
    A module to quickly score resumes (extract age, experience, and skills)
    and match them against job requirements.

    Features:
    - Silent auto-healing for dirty data.
    - Zero-config sensible defaults for missing parameters.
    - Non-destructive regex (case-preserving).
    - Invisible backend audit tracing.
    """

    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []

    def _log_trace(self, step: str, before: Any, after: Any, reason: str = "") -> None:
        """Silently record state changes for auditing."""
        self.audit_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "step": step,
            "before": before,
            "after": after,
            "reason": reason
        })

    def _extract_age(self, text: str) -> Optional[int]:
        """Extract age from text with non-destructive regex."""
        # E.g., '25岁', 'Age: 30', '年龄35'
        match = re.search(r'(?:age|年龄|岁数)\s*[:：]?\s*(\d{1,3})|(\d{1,3})\s*(?:岁|years? old)', text, re.IGNORECASE)
        if match:
            age = int(match.group(1) or match.group(2))
            if 16 <= age <= 100:  # Sensible bounds
                return age
        return None

    def _extract_experience(self, text: str) -> Optional[int]:
        """Extract years of experience from text."""
        # E.g., '5年经验', 'Experience: 10 years', '工作经验3年', '工龄: 4'
        match = re.search(r'(?:exp|experience|经验|工龄|工作时间)\s*[:：]?\s*(\d+)\s*(?:年|years?)?', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Handle 'X年工作经验'
        match = re.search(r'(\d+)\s*(?:年|years?)\s*(?:工作)?(?:经验|experience)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from text (simple keyword matching simulation for now)."""
        skills = []
        # Extract English alphabetic skills (e.g. Python, Java, C++)
        eng_skills = re.findall(r'[A-Za-z+#]+', text)
        for s in eng_skills:
            if len(s) > 1 and s.lower() not in ['and', 'or', 'the', 'a', 'an', 'in', 'of', 'with', 'years', 'old', 'age', 'exp', 'experience']:
                skills.append(s)
        return list(set(skills)) # Deduplicate

    def _clean_text(self, text: Any) -> str:
        """Silent auto-healing for dirty inputs."""
        original = text
        if text is None:
            text = ""
        elif not isinstance(text, str):
            text = str(text)

        # Remove unprintable characters but preserve case
        cleaned = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\u4e00-\u9fa5]', '', text)

        if original != cleaned:
            self._log_trace("text_cleaning", original, cleaned, "Sanitized dirty text input")
        return cleaned

    def score_resume(self, resume_text: Any, job_req: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point for scoring a resume against requirements.
        Returns a clean, simple result for the frontend.
        """
        # 1. Dirty data auto-healing & defaults
        clean_resume = self._clean_text(resume_text)
        job_req = job_req or {}

        # Sensible defaults for missing params
        req_min_exp = job_req.get('min_experience', 0)
        req_max_age = job_req.get('max_age', 99)
        req_skills = job_req.get('required_skills', [])
        if not isinstance(req_skills, list):
             req_skills = []

        # 2. Extraction
        extracted_age = self._extract_age(clean_resume)
        extracted_exp = self._extract_experience(clean_resume)
        extracted_skills = self._extract_skills(clean_resume)

        self._log_trace("extraction", clean_resume,
                        {"age": extracted_age, "exp": extracted_exp, "skills": extracted_skills},
                        "Extracted structured data from resume")

        # 3. Matching & Scoring
        score = 0
        reasons = []

        # Age matching (default pass if age not found but within bounds generally)
        if extracted_age:
            if extracted_age <= req_max_age:
                score += 30
                reasons.append(f"Age {extracted_age} <= {req_max_age}")
            else:
                reasons.append(f"Age {extracted_age} > {req_max_age}")
        else:
             score += 15 # Partial score for missing age
             reasons.append("Age not found")

        # Experience matching
        if extracted_exp is not None:
            if extracted_exp >= req_min_exp:
                score += 40
                reasons.append(f"Experience {extracted_exp} >= {req_min_exp}")
            else:
                reasons.append(f"Experience {extracted_exp} < {req_min_exp}")
        else:
            if req_min_exp == 0:
                score += 40
                reasons.append("No experience required")
            else:
                reasons.append("Experience not found")

        # Skills matching
        skill_score = 0
        matched_skills = []
        if req_skills:
            # Case-insensitive match for skills
            resume_skills_lower = [s.lower() for s in extracted_skills]
            for rs in req_skills:
                if rs.lower() in resume_skills_lower:
                    skill_score += (30 / len(req_skills))
                    # Find original cased skill for highlight
                    original_skill = next((s for s in extracted_skills if s.lower() == rs.lower()), rs)
                    matched_skills.append(original_skill)

            score += skill_score
            reasons.append(f"Matched {len(matched_skills)}/{len(req_skills)} skills")
        else:
            score += 30 # No skills required
            reasons.append("No specific skills required")

        final_score = min(100, max(0, round(score)))

        self._log_trace("scoring", {"req": job_req}, {"score": final_score, "reasons": reasons}, "Calculated match score")

        # Frontend gets a simple, clean result.
        # Audit trace is available via self.audit_log for backend review.
        return {
            "score": final_score,
            "extracted": {
                "age": extracted_age,
                "experience": extracted_exp,
                "skills": extracted_skills
            },
            "matched_skills": matched_skills,
            "is_match": final_score >= 60
        }

    def get_audit_trace(self) -> List[Dict[str, Any]]:
        """Retrieve the backend audit trace."""
        return self.audit_log

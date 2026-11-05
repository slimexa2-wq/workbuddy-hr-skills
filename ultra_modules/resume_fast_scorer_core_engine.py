import re
from datetime import datetime
from typing import Dict, Any, List

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            # Extract first number found
            match = re.search(r'\d+', value)
            if match:
                return int(match.group())
        return int(value)
    except (ValueError, TypeError):
        return default

def _extract_age(resume_text: str) -> int:
    # 1. Look for explicit age (e.g., 25岁, 年龄：25)
    age_match = re.search(r'(?:年龄)[:：\s]*(\d{2})岁?|(\d{2})岁', resume_text)
    if age_match:
        age = int(age_match.group(1) or age_match.group(2))
        if 18 <= age <= 65:
            return age

    # 2. Look for birth year (e.g., 1995年出生, 出生年月：1995.05)
    birth_match = re.search(r'(?:出生|生日|出\s*生\s*年\s*月)[:：\s]*(\d{4})|(\d{4})年出?生', resume_text)
    if birth_match:
        year_str = birth_match.group(1) or birth_match.group(2)
        birth_year = int(year_str)
        current_year = datetime.now().year
        age = current_year - birth_year
        if 18 <= age <= 65:
            return age

    return 0  # Fallback

def _extract_experience(resume_text: str) -> int:
    # 1. Look for explicit experience years (e.g., 5年经验, 工作经验：5年)
    exp_match = re.search(r'(?:经验|工作)[:：\s]*(\d+)[年\+]+|(\d+)[年\+]+(?:工作经验|经验)', resume_text)
    if exp_match:
        return int(exp_match.group(1) or exp_match.group(2))

    # 2. Check for graduation year to infer max possible experience (naive fallback)
    grad_match = re.search(r'(?:毕业|毕\s*业\s*时\s*间)[:：\s]*(\d{4})|(\d{4})年毕?业', resume_text)
    if grad_match:
        year_str = grad_match.group(1) or grad_match.group(2)
        grad_year = int(year_str)
        current_year = datetime.now().year
        exp = current_year - grad_year
        return max(0, exp)

    return 0

def _check_skill_match(resume_text: str, skill: str) -> bool:
    # If skill is alphanumeric (like Python, C++), use word boundaries
    # but since C++ has special chars, we need to handle it carefully
    text_lower = resume_text.lower()
    skill_lower = skill.lower()

    # Escape skill for regex
    escaped_skill = re.escape(skill_lower)

    # If purely alphabetic/numeric, use custom boundaries to avoid issues with Chinese characters
    # \b fails when adjacent to Chinese characters.
    if re.match(r'^[a-zA-Z0-9]+$', skill_lower):
        pattern = r'(?<![a-zA-Z0-9])' + escaped_skill + r'(?![a-zA-Z0-9])'
        return bool(re.search(pattern, text_lower))
    else:
        # Otherwise simple substring match
        return skill_lower in text_lower

def score_resume(resume_text: str, requirements: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Evaluates a resume against project requirements.

    Args:
        resume_text: The text content of the resume.
        requirements: Dict containing requirements like:
            - min_age (int)
            - max_age (int)
            - min_experience (int)
            - required_skills (List[str])
            - nice_to_have_skills (List[str])

    Returns:
        Dict containing score details and extracted information.
    """
    if not resume_text or not isinstance(resume_text, str):
        return {"score": 0, "extracted": {}, "errors": "Invalid resume text"}

    reqs = requirements or {}

    # Default requirements if not provided to avoid breaking
    min_age = _safe_int(reqs.get('min_age'), 18)
    max_age = _safe_int(reqs.get('max_age'), 65)
    min_exp = _safe_int(reqs.get('min_experience'), 0)
    req_skills = reqs.get('required_skills', [])
    if not isinstance(req_skills, list):
        req_skills = [req_skills] if req_skills else []

    nice_skills = reqs.get('nice_to_have_skills', [])
    if not isinstance(nice_skills, list):
        nice_skills = [nice_skills] if nice_skills else []

    # Extraction
    extracted_age = _extract_age(resume_text)
    extracted_exp = _extract_experience(resume_text)

    matched_req_skills = [s for s in req_skills if _check_skill_match(resume_text, s)]
    matched_nice_skills = [s for s in nice_skills if _check_skill_match(resume_text, s)]

    # Scoring Logic
    total_score = 0

    # Age score (max 20)
    age_score = 0
    if extracted_age > 0:
        if min_age <= extracted_age <= max_age:
            age_score = 20
        elif extracted_age < min_age and (min_age - extracted_age) <= 2:
            age_score = 10 # Near miss
        elif extracted_age > max_age and (extracted_age - max_age) <= 2:
            age_score = 10 # Near miss
    else:
        # Age not found, neutral middle ground
        age_score = 10

    # Experience score (max 30)
    exp_score = 0
    if extracted_exp >= min_exp:
        exp_score = 30
    elif extracted_exp > 0 and (min_exp - extracted_exp) <= 1:
        exp_score = 15 # Near miss
    else:
        exp_score = 0

    # Skills score (max 50)
    skills_score = 0
    if req_skills:
        req_match_ratio = len(matched_req_skills) / len(req_skills)
        skills_score += req_match_ratio * 40 # Up to 40 for required skills
    else:
        skills_score += 40 # If no required skills, free points

    if nice_skills:
        nice_match_ratio = len(matched_nice_skills) / len(nice_skills)
        skills_score += nice_match_ratio * 10 # Up to 10 for nice to have
    else:
        skills_score += 10 # If no nice-to-have, free points

    total_score = age_score + exp_score + skills_score

    return {
        "score": round(total_score, 1),
        "details": {
            "age_score": age_score,
            "experience_score": exp_score,
            "skills_score": round(skills_score, 1)
        },
        "extracted": {
            "age": extracted_age,
            "experience": extracted_exp,
            "matched_required_skills": matched_req_skills,
            "matched_nice_to_have_skills": matched_nice_skills
        }
    }

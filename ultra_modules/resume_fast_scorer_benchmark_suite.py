import re
import datetime
import time
import concurrent.futures
from typing import Dict, List, Any, Optional

class ResumeFastScorer:
    """
    Resume text fast scorer.
    Extracts age, experience, and skills from raw resume text and calculates a match score.
    """

    def __init__(self):
        # Using lookarounds for Chinese context as standard \b doesn't work well
        self.age_pattern = re.compile(r'(?<![a-zA-Z0-9])(?:出生年月|出生日期|年龄)[:：]?\s*(\d{4}[年-]?\d{0,2}月?|[12]\d|3\d|4\d|5\d)(?![a-zA-Z0-9])')
        self.exp_pattern = re.compile(r'(?<![a-zA-Z0-9])(?:工作经验|工龄)[:：]?\s*(\d+)\s*(?:年)?(?![a-zA-Z0-9])')

    def _extract_age(self, text: str) -> Optional[int]:
        match = self.age_pattern.search(text)
        if match:
            val = match.group(1)
            if '年' in val or '-' in val:
                try:
                    year = int(re.split(r'[年-]', val)[0])
                    return datetime.datetime.now().year - year
                except ValueError:
                    return None
            else:
                try:
                    return int(val)
                except ValueError:
                    return None
        return None

    def _extract_experience(self, text: str) -> Optional[int]:
        match = self.exp_pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_skills(self, text: str, required_skills: List[str]) -> List[str]:
        found_skills = []
        for skill in required_skills:
            # Escape skill for regex and use lookarounds for Chinese context
            escaped_skill = re.escape(skill)
            # Use negative lookahead/lookbehind for alphanumeric to simulate word boundaries in Chinese text
            pattern = re.compile(f'(?<![a-zA-Z0-9]){escaped_skill}(?![a-zA-Z0-9])', re.IGNORECASE)
            if pattern.search(text):
                found_skills.append(skill)
        return found_skills

    def score(self, resume_text: Any, job_requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculates a match score for a resume against job requirements.
        Extreme fault tolerance: Handles None, non-string, missing parameters with default fallbacks.
        """
        # Self-healing for missing job requirements
        if job_requirements is None or not isinstance(job_requirements, dict):
            job_requirements = {}

        req_skills = job_requirements.get('skills', [])
        if not isinstance(req_skills, list):
            req_skills = []

        min_exp = job_requirements.get('min_experience', 0)
        max_age = job_requirements.get('max_age', 99)

        # Self-healing for dirty inputs
        if not isinstance(resume_text, str):
            resume_text = str(resume_text) if resume_text is not None else ""

        # If text is extremely short or garbled, just return default values
        if len(resume_text) < 2:
            return {
                "score": 0,
                "extracted_age": None,
                "extracted_experience": None,
                "matched_skills": [],
                "error": "Text too short or empty"
            }

        age = self._extract_age(resume_text)
        experience = self._extract_experience(resume_text)
        matched_skills = self._extract_skills(resume_text, req_skills)

        # Calculate score (0-100)
        score = 0

        # Skill score (up to 50 points)
        if req_skills:
            score += (len(matched_skills) / len(req_skills)) * 50
        else:
            score += 50 # Default if no skills required

        # Experience score (up to 30 points)
        if experience is not None:
            if min_exp == 0:
                 score += 30
            elif experience >= min_exp:
                 score += 30
            else:
                 score += max(0, (experience / min_exp) * 30)
        else:
            score += 15 # Default fallback

        # Age score (up to 20 points)
        if age is not None:
            if age <= max_age:
                score += 20
            else:
                score += max(0, 20 - (age - max_age) * 2)
        else:
            score += 10 # Default fallback

        return {
            "score": round(score, 2),
            "extracted_age": age,
            "extracted_experience": experience,
            "matched_skills": matched_skills
        }


class BenchmarkSuite:
    """
    Synthetic Fixtures and Performance Benchmark Validator.
    """
    @staticmethod
    def generate_synthetic_fixtures(count: int = 100) -> List[Dict[str, Any]]:
        fixtures = []
        for i in range(count):
            if i % 5 == 0:
                # Null/Dirty data
                fixtures.append({"text": None, "reqs": None})
            elif i % 5 == 1:
                # Extremely long string (boundary)
                long_text = "开发工程师 " * 1000 + "出生年月: 1990-05 工龄: 5年 技能: Python, Java"
                fixtures.append({"text": long_text, "reqs": {"skills": ["Python", "C++"], "min_experience": 3, "max_age": 35}})
            elif i % 5 == 2:
                # Normal case
                fixtures.append({"text": "我是一名前端，出生日期：1995年，工作经验: 3年。精通React和Vue。", "reqs": {"skills": ["React", "Vue", "Node.js"], "min_experience": 2, "max_age": 30}})
            elif i % 5 == 3:
                # Cross-year boundary and garbled text
                fixtures.append({"text": "￥%……&*（）年龄：24 技能：Golang \x00\x01", "reqs": {"skills": ["Golang", "Docker"], "min_experience": 1, "max_age": 28}})
            else:
                # Missing parameters (empty reqs)
                fixtures.append({"text": "出生年月：1988年 工龄：10年 技能：Java, Spring Boot", "reqs": {}})
        return fixtures

    @staticmethod
    def run_benchmark(concurrency: int = 10, total_tasks: int = 1000) -> Dict[str, Any]:
        scorer = ResumeFastScorer()
        fixtures = BenchmarkSuite.generate_synthetic_fixtures(total_tasks)

        start_time = time.time()

        def _process_task(fixture):
            return scorer.score(fixture["text"], fixture["reqs"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(_process_task, fixtures))

        end_time = time.time()
        duration = end_time - start_time

        return {
            "total_tasks": total_tasks,
            "concurrency": concurrency,
            "duration_seconds": round(duration, 4),
            "throughput_req_per_sec": round(total_tasks / duration, 2) if duration > 0 else 0,
            "success_count": len(results)
        }

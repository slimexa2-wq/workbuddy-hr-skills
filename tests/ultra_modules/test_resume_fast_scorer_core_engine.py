import unittest
from datetime import datetime
import sys
import os

# Add project root to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ultra_modules.resume_fast_scorer_core_engine import (
    score_resume,
    _safe_int,
    _extract_age,
    _extract_experience,
    _check_skill_match
)

class TestResumeFastScorerCoreEngine(unittest.TestCase):

    def setUp(self):
        self.current_year = datetime.now().year

    def test_normal_extraction_and_scoring(self):
        # Case 1: Normal extraction with perfect matching
        resume = "张三，男，年龄：28岁。Python高级开发工程师，拥有5年经验。熟练使用Java, C++。"
        reqs = {
            "min_age": 25,
            "max_age": 35,
            "min_experience": 3,
            "required_skills": ["Python", "Java"],
            "nice_to_have_skills": ["C++"]
        }
        result = score_resume(resume, reqs)
        self.assertEqual(result['extracted']['age'], 28)
        self.assertEqual(result['extracted']['experience'], 5)
        self.assertEqual(len(result['extracted']['matched_required_skills']), 2)
        self.assertEqual(len(result['extracted']['matched_nice_to_have_skills']), 1)
        # Score: 20 (age) + 30 (exp) + 40 (req skills) + 10 (nice skills) = 100
        self.assertEqual(result['score'], 100.0)

    def test_dirty_data_auto_healing(self):
        # Case 2: Dirty data in requirements and missing/dirty fields
        resume = f"李四，1995年出生，毕业时间：{self.current_year - 2}。技术栈：javascript、typescript。"
        reqs = {
            "min_age": "25a",  # Dirty, should fallback to default 18
            "max_age": None,   # Should fallback to default 65
            "min_experience": "1", # String integer
            "required_skills": "JavaScript",  # String instead of list
            "nice_to_have_skills": None
        }
        result = score_resume(resume, reqs)

        expected_age = self.current_year - 1995
        self.assertEqual(result['extracted']['age'], expected_age)
        self.assertEqual(result['extracted']['experience'], 2) # Calculated from grad year
        self.assertIn("JavaScript", result['extracted']['matched_required_skills'])

        # Age score: 20 (since 18 <= age <= 65)
        # Exp score: 30 (since 2 >= 1)
        # Skills: 40 (1/1 req) + 10 (no nice-to-have, free points)
        self.assertEqual(result['score'], 100.0)

    def test_missing_parameters_fallback(self):
        # Case 3: Empty/None requirements or text
        result_empty_text = score_resume(None, {})
        self.assertEqual(result_empty_text['score'], 0)

        resume = "无经验应届生，无明确技能"
        # None requirements
        result_no_req = score_resume(resume, None)

        # Age not extracted -> 10 points
        # Exp not extracted (0) -> 0 points (min_exp defaults to 0, so 0 >= 0 is true, so 30 points)
        # Actually min_exp defaults to 0, extracted is 0. 0 >= 0 is True, so exp_score = 30.
        # Skills: no reqs -> 40 points, no nice -> 10 points
        # Total: 10 + 30 + 40 + 10 = 90
        self.assertEqual(result_no_req['score'], 90.0)
        self.assertEqual(result_no_req['extracted']['age'], 0)
        self.assertEqual(result_no_req['extracted']['experience'], 0)

    def test_edge_boundary_values(self):
        # Case 4: Near miss scoring
        resume = "王五，年龄23。2年经验。会Go语言"
        reqs = {
            "min_age": 25,
            "max_age": 30,
            "min_experience": 3,
            "required_skills": ["Go", "Rust"]
        }
        result = score_resume(resume, reqs)

        # Age: 23 is < 25, difference 2 <= 2 -> 10 points
        self.assertEqual(result['details']['age_score'], 10)

        # Exp: 2 is < 3, difference 1 <= 1 -> 15 points
        self.assertEqual(result['details']['experience_score'], 15)

        # Skills: 1/2 req matched -> 20 points, no nice-to-have -> 10 points
        self.assertEqual(result['details']['skills_score'], 30.0)

        self.assertEqual(result['score'], 55.0)

    def test_non_alpha_skills_and_branch_coverage(self):
        # Case 5: Special characters in skills, max_age near miss, _safe_int types
        resume = "赵六，年龄：67。会C++，C#，.NET。"
        reqs = {
            "max_age": 65,
            "required_skills": ["C++", "C#", ".NET"]
        }
        result = score_resume(resume, reqs)

        # Age: 67 is > 65, diff 2 <= 2 -> 10 points
        self.assertEqual(result['details']['age_score'], 10)

        # All 3 skills should match (they trigger the non-alphanumeric branch)
        self.assertEqual(len(result['extracted']['matched_required_skills']), 3)

        # Test safe_int with completely invalid types
        self.assertEqual(_safe_int({"a": 1}), 0)
        self.assertEqual(_safe_int("no numbers here", 5), 5)

        # Test extreme age fallback
        resume_extreme_age = "年龄：10岁" # Not between 18 and 65
        self.assertEqual(_extract_age(resume_extreme_age), 0)

        resume_extreme_birth = "出生年月：2020" # Not between 18 and 65
        self.assertEqual(_extract_age(resume_extreme_birth), 0)

        # Test empty exp string
        self.assertEqual(_extract_experience("毫无经验"), 0)

if __name__ == '__main__':
    unittest.main()

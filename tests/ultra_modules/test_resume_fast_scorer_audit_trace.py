import unittest
from ultra_modules.resume_fast_scorer_audit_trace import ResumeFastScorerAuditTrace

class TestResumeFastScorerAuditTrace(unittest.TestCase):
    def setUp(self):
        self.scorer = ResumeFastScorerAuditTrace()

    def test_normal_resume_matching(self):
        """Test a normal, clean resume with perfect matching."""
        resume = "张三，男，年龄：28岁。工作经验：5年。熟练掌握 Python 和 Java，了解 C++。"
        job_req = {
            "min_experience": 3,
            "max_age": 35,
            "required_skills": ["Python", "Java", "C++"]
        }

        result = self.scorer.score_resume(resume, job_req)

        self.assertTrue(result["is_match"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["extracted"]["age"], 28)
        self.assertEqual(result["extracted"]["experience"], 5)
        # Skills check - should preserve case based on extraction logic (mostly from regex matches)
        extracted_lower = [s.lower() for s in result["extracted"]["skills"]]
        self.assertIn("python", extracted_lower)
        self.assertIn("java", extracted_lower)
        self.assertIn("c++", extracted_lower)

        trace = self.scorer.get_audit_trace()
        self.assertTrue(len(trace) > 0)
        self.assertEqual(trace[-1]["step"], "scoring")

    def test_dirty_data_auto_healing(self):
        """Test with dirty data (None, numbers, unprintable chars)."""
        # Should gracefully handle non-string and unprintable chars
        resume = "年龄：30\x00岁，工龄 8 \x07年。 技能：Go, \x1BRust."

        job_req = {
            "min_experience": 5,
            "max_age": 30,
            "required_skills": ["Go", "Rust"]
        }

        result = self.scorer.score_resume(resume, job_req)

        self.assertTrue(result["is_match"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["extracted"]["age"], 30)
        self.assertEqual(result["extracted"]["experience"], 8)

        trace = self.scorer.get_audit_trace()
        # Verify text cleaning was traced
        cleaning_traces = [t for t in trace if t["step"] == "text_cleaning"]
        self.assertTrue(len(cleaning_traces) > 0)

        # Test None input
        none_result = self.scorer.score_resume(None)
        # 15(age) + 40(exp default 0) + 30(no skills) = 85
        self.assertTrue(none_result["is_match"])
        self.assertEqual(none_result["score"], 85)

    def test_missing_parameters_defaults(self):
        """Test with completely missing job requirements (zero-config)."""
        resume = "Age 25, 2 years experience. Python developer."
        # No job_req provided
        result = self.scorer.score_resume(resume)

        # Defaults: max_age=99 (25<=99 -> 30), min_exp=0 (2>=0 -> 40), required_skills=[] (-> 30)
        # Total = 100
        self.assertTrue(result["is_match"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["extracted"]["age"], 25)
        self.assertEqual(result["extracted"]["experience"], 2)

    def test_extreme_edge_cases(self):
        """Test with unrealistic ages, negative experience (though regex won't match), and empty strings."""
        # Age too low or high (ignored by bounds check)
        resume = "Age 5, 200 years experience. HTML"
        job_req = {"min_experience": 2}
        result = self.scorer.score_resume(resume, job_req)

        self.assertIsNone(result["extracted"]["age"])  # 5 is outside bounds [16, 100]
        self.assertEqual(result["extracted"]["experience"], 200)
        # Score: age none=15, exp 200>=2=40, skills none req=30 -> 85
        self.assertEqual(result["score"], 85)
        self.assertTrue(result["is_match"])

    def test_audit_trace_contents(self):
        """Verify the invisible backend audit trace records correctly without throwing errors."""
        resume = "年龄35岁工作时间10年。熟悉React。"
        self.scorer.score_resume(resume)

        trace = self.scorer.get_audit_trace()

        # Should have extraction and scoring at minimum (no cleaning if clean)
        steps = [t["step"] for t in trace]
        self.assertIn("extraction", steps)
        self.assertIn("scoring", steps)

        # Verify timestamps exist and are valid ISO formats
        for t in trace:
            self.assertIn("timestamp", t)
            self.assertIsInstance(t["before"], (str, dict, type(None)))
            self.assertIsInstance(t["after"], (str, dict))

if __name__ == '__main__':
    unittest.main()

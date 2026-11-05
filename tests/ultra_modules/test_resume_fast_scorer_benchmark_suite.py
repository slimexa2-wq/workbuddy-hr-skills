import unittest
import datetime
from ultra_modules.resume_fast_scorer_benchmark_suite import ResumeFastScorer, BenchmarkSuite

class TestResumeFastScorerBenchmarkSuite(unittest.TestCase):
    def setUp(self):
        self.scorer = ResumeFastScorer()

    def test_normal_case(self):
        # Normal inputs
        text = "后端开发工程师，出生日期：1992年，工作经验：5年。熟练掌握Python, Java, Docker。"
        reqs = {"skills": ["Python", "Docker", "Kubernetes"], "min_experience": 3, "max_age": 35}
        result = self.scorer.score(text, reqs)

        self.assertEqual(result["extracted_age"], datetime.datetime.now().year - 1992)
        self.assertEqual(result["extracted_experience"], 5)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("Docker", result["matched_skills"])
        self.assertNotIn("Kubernetes", result["matched_skills"])
        self.assertGreater(result["score"], 0)

    def test_dirty_data_self_healing(self):
        # Null values, garbled text, non-strings
        reqs = {"skills": ["Java"], "min_experience": 1}

        result_none = self.scorer.score(None, reqs)
        self.assertEqual(result_none["score"], 0)
        self.assertEqual(result_none["error"], "Text too short or empty")

        result_num = self.scorer.score(12345, reqs)
        self.assertEqual(result_num["extracted_age"], None)

        result_garbled = self.scorer.score("@@##$$%%^^&&**(\x00\x01)", reqs)
        self.assertEqual(result_garbled["extracted_age"], None)

    def test_missing_parameters(self):
        # Missing job requirement config gracefully defaults
        text = "出生年月: 1995-12 工龄: 2 技能: Vue"
        result_none_reqs = self.scorer.score(text, None)

        self.assertEqual(result_none_reqs["extracted_experience"], 2)
        self.assertEqual(result_none_reqs["extracted_age"], datetime.datetime.now().year - 1995)
        self.assertEqual(result_none_reqs["matched_skills"], [])
        self.assertEqual(result_none_reqs["score"], 100) # (50 skills default + 30 exp default + 20 age max)

    def test_extreme_boundaries(self):
        # Extremely long string, cross-year boundaries
        current_year = datetime.datetime.now().year
        long_text = "前端 " * 5000 + f"年龄：{current_year - 1990} 工作经验：10年 技能：React"
        reqs = {"skills": ["React"], "min_experience": 5, "max_age": 30}

        result = self.scorer.score(long_text, reqs)
        self.assertEqual(result["extracted_age"], current_year - 1990)
        self.assertEqual(result["extracted_experience"], 10)
        self.assertIn("React", result["matched_skills"])

    def test_benchmark_concurrency(self):
        # Run synthetic fixture processing at scale
        stats = BenchmarkSuite.run_benchmark(concurrency=20, total_tasks=500)
        self.assertEqual(stats["total_tasks"], 500)
        self.assertEqual(stats["success_count"], 500)
        self.assertGreater(stats["throughput_req_per_sec"], 0)

if __name__ == "__main__":
    unittest.main()

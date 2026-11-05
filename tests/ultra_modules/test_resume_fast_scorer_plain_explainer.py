import unittest
import json
from ultra_modules.resume_fast_scorer_plain_explainer import ResumeFastScorer, analyze_resume

class TestResumeFastScorerPlainExplainer(unittest.TestCase):

    def setUp(self):
        self.scorer = ResumeFastScorer()

    def test_normal_data_perfect_match(self):
        resume = "候选人张三，年龄28岁，具备5年工作经验。熟练掌握 Python 和 Java，会使用 MySQL。"
        reqs = {
            "min_age": 25,
            "max_age": 35,
            "min_experience_years": 3,
            "required_skills": ["Python", "Java", "MySQL"]
        }
        explainer = analyze_resume(resume, reqs)
        data = explainer.data

        self.assertEqual(data["score"], 100)
        self.assertEqual(data["extracted"]["age"], 28)
        self.assertEqual(data["extracted"]["experience_years"], 5)
        self.assertCountEqual(data["extracted"]["skills"], ["Python", "Java", "MySQL"])
        self.assertEqual(len(data["deductions"]), 0)
        self.assertIn("极度匹配", data["verdict"])

        # Test exports
        self.assertIn("28 岁", explainer.to_markdown())
        self.assertIn("5 年", explainer.to_html())
        self.assertIn("满分匹配", explainer.to_markdown())
        self.assertIn("满分匹配", explainer.to_html())

        json_data = json.loads(explainer.to_json())
        self.assertEqual(json_data["score"], 100)

    def test_dirty_data_healing_and_partial_match(self):
        # 换行、奇怪空格、不同表达方式、大小写混杂
        resume = "张三\r\n 年龄: 38\n\n拥有 12 年的经验。技能包含 PytHoN 以及 docKer。没有其他内容了。"
        reqs = {
            "min_age": 25,
            "max_age": 35, # 超出上限
            "min_experience_years": 5,
            "required_skills": ["python", "docker", "k8s"] # 缺少 k8s
        }

        explainer = analyze_resume(resume, reqs)
        data = explainer.data

        self.assertEqual(data["extracted"]["age"], 38)
        self.assertEqual(data["extracted"]["experience_years"], 12)
        # 应该通过非破坏性的 re.IGNORECASE 匹配到 PytHoN 和 docKer
        self.assertCountEqual([s.lower() for s in data["extracted"]["skills"]], ["python", "docker"])

        self.assertTrue(any("偏大" in d for d in data["deductions"]))
        self.assertTrue(any("k8s" in d for d in data["deductions"]))

    def test_missing_parameters_default_fallback(self):
        # 不传 reqs，或 reqs 为空，缺省兜底
        resume = "实习生李四，21岁，应届毕业生。"
        # 默认情况下，无技能要求，不扣技能分，但会测试基础默认年龄和经验要求
        explainer = analyze_resume(resume, None)
        data = explainer.data

        self.assertEqual(data["extracted"]["age"], 21)
        self.assertEqual(data["extracted"]["experience_years"], 0)

        # 默认下限经验为0，因此应届生不会被扣经验分
        self.assertTrue(all("不足" not in d for d in data["deductions"]))

    def test_extreme_edge_cases(self):
        # 传入 None
        explainer = analyze_resume(None)
        data = explainer.data
        self.assertEqual(data["extracted"]["age"], None)
        self.assertEqual(data["extracted"]["experience_years"], None)
        self.assertEqual(data["extracted"]["skills"], [])
        self.assertEqual(len(data["deductions"]), 2) # 未提取到年龄、未提取到经验
        self.assertTrue(data["score"] < 100)

        # 传入非字符串
        explainer2 = analyze_resume(12345)
        data2 = explainer2.data
        self.assertEqual(data2["extracted"]["age"], None)

        md = explainer.to_markdown()
        self.assertIn("未知", md)

    def test_birth_year_extraction(self):
        resume = "王五，1995年出生，工作经验：4年。熟练 C++。"
        explainer = analyze_resume(resume, {"required_skills": ["c++"]})
        data = explainer.data

        # 年龄提取自 1995
        import datetime
        current_year = datetime.datetime.now().year
        expected_age = current_year - 1995
        self.assertEqual(data["extracted"]["age"], expected_age)
        self.assertEqual(data["extracted"]["experience_years"], 4)

        # 技能匹配包含标点符号，如 C++
        self.assertIn("c++", data["extracted"]["skills"])

if __name__ == '__main__':
    unittest.main()

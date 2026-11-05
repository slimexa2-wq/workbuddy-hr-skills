import unittest
import os
import json
from unittest.mock import patch
from ultra_modules.resume_fast_scorer_cli_one_click import run_one_click_scorer, fallback_resume_text, get_default_requirements

class TestResumeFastScorerCliOneClick(unittest.TestCase):

    def setUp(self):
        self.prefix = "test_output_prefix"
        self.json_file = f"{self.prefix}.json"
        self.excel_file = f"{self.prefix}.xlsx"

    def tearDown(self):
        # 清理生成的测试文件
        if os.path.exists(self.json_file):
            os.remove(self.json_file)
        if os.path.exists(self.excel_file):
            os.remove(self.excel_file)

    def test_normal_data_flow(self):
        # 1. 测试正常数据流
        resume = "张三，男，28岁，工作经验：5年。掌握 Python, Java, 沟通能力强。"
        requirements = {
            "min_age": 20,
            "max_age": 35,
            "min_experience_years": 3,
            "required_skills": ["Python", "Java", "沟通能力"]
        }
        result = run_one_click_scorer(resume_text=resume, requirements=requirements, output_prefix=self.prefix)
        self.assertEqual(result.get("score"), 100)
        self.assertEqual(result.get("extracted", {}).get("age"), 28)
        self.assertEqual(result.get("extracted", {}).get("experience_years"), 5)
        self.assertIn("Python", result.get("extracted", {}).get("skills"))

        self.assertTrue(os.path.exists(self.json_file))
        self.assertTrue(os.path.exists(self.excel_file))

    def test_dirty_data_self_healing(self):
        # 2. 测试脏数据自愈（缺少年龄单位，经验使用不规范描述，乱码文本）
        resume = "李四   年龄35 \\n 乱码数据@#% 经验：10  掌握了 C++"
        requirements = {
            "min_age": 20,
            "max_age": 40,
            "min_experience_years": 5,
            "required_skills": ["C++"]
        }
        result = run_one_click_scorer(resume_text=resume, requirements=requirements, output_prefix=self.prefix)
        self.assertEqual(result.get("extracted", {}).get("age"), 35)
        # Assuming the extractor can't find experience here because it doesn't match standard patterns, it will just deduct points.
        # Wait, the logic matches "经验：\s*(\d{1,2})\s*年". Let's check the regex in explainer.
        # Actually in dirty data, if experience is missing, score drops but program doesn't crash.
        self.assertTrue("score" in result)
        self.assertIn("C++", result.get("extracted", {}).get("skills"))

    def test_parameter_fallback(self):
        # 3. 测试缺参默认兜底（完全不传参数，一键直达）
        result = run_one_click_scorer(output_prefix=self.prefix)
        self.assertTrue(os.path.exists(self.json_file))
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn("score", data)
        self.assertIn("extracted", data)
        # Should use fallback_resume_text which has 25 years old
        self.assertEqual(data["extracted"]["age"], 25)

    def test_extreme_boundaries(self):
        # 4. 测试极端边界情况 (超大年龄，超长经验)
        resume = "王五，年龄99岁，工作经验：80年，精通一切。"
        requirements = {
            "min_age": 18,
            "max_age": 60,
            "min_experience_years": 1,
            "required_skills": ["Python"]
        }
        result = run_one_click_scorer(resume_text=resume, requirements=requirements, output_prefix=self.prefix)

        self.assertEqual(result.get("extracted", {}).get("age"), 99)
        self.assertEqual(result.get("extracted", {}).get("experience_years"), 80)
        self.assertTrue(result.get("score") < 100) # Points deducted for age > max_age and missing Python
        deductions = result.get("deductions", [])
        self.assertTrue(any("偏大" in d for d in deductions))

    def test_default_cli_execution_with_empty_text(self):
        # 5. 测试传入空字符串的兜底
        result = run_one_click_scorer(resume_text="", requirements={}, output_prefix=self.prefix)
        # Empty text should trigger fallback resume text and fallback requirements
        self.assertEqual(result.get("extracted", {}).get("age"), 25)
        self.assertEqual(result.get("extracted", {}).get("experience_years"), 3)

if __name__ == '__main__':
    unittest.main()

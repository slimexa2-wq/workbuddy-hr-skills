import unittest
import math
from ultra_modules.resume_fast_scorer_export_formatter import ResumeFastScorerExportFormatter

class TestResumeFastScorerExportFormatter(unittest.TestCase):
    def test_normal_execution(self):
        """1. 测试正常数据提取与生成（正常）"""
        resume_text = "姓名: 张三 年龄: 28岁 工龄: 5年 技能: Python, Java, SQL"
        req = {"max_age": 30, "min_exp": 3, "required_skills": ["Python", "Java"]}

        result = ResumeFastScorerExportFormatter.format_export(resume_text, req)

        export_data = result["export_data"]
        report = result["report"]

        self.assertEqual(export_data["age"], 28)
        self.assertEqual(export_data["experience"], 5)
        self.assertEqual(export_data["skills"], "Python、Java、SQL")
        self.assertEqual(export_data["match_score"], 100)
        self.assertEqual(export_data["comments"], 0)

        expected_report = (
            "【匹配度】综合打分：100分\n"
            "【画像】年龄28岁 | 工龄5年\n"
            "【技能】Python、Java、SQL"
        )
        self.assertEqual(report, expected_report)

    def test_dirty_data_self_healing(self):
        """2. 测试脏数据自愈（非字符串输入，换行混杂）"""
        resume_text = 123456789  # int instead of str
        req = {}

        result = ResumeFastScorerExportFormatter.format_export(resume_text, req)

        self.assertEqual(result["export_data"]["age"], 0)
        self.assertEqual(result["export_data"]["experience"], 0)
        self.assertEqual(result["export_data"]["skills"], "无明确技能")
        self.assertEqual(result["export_data"]["comments"], 0)
        self.assertIn("【画像】年龄0岁 | 工龄0年", result["report"])

    def test_missing_parameters_fallback(self):
        """3. 测试缺参默认兜底（无简历文本，无要求字典）"""
        result = ResumeFastScorerExportFormatter.format_export(None, None)

        self.assertEqual(result["export_data"]["age"], 0)
        self.assertEqual(result["export_data"]["experience"], 0)
        self.assertEqual(result["export_data"]["match_score"], 100) # baseline score
        self.assertEqual(result["export_data"]["comments"], 0)

    def test_extreme_edge_cases_nan(self):
        """4. 测试极端边界情况 (传入 NaN float 格式)"""
        result = ResumeFastScorerExportFormatter.format_export(float('nan'), None)

        self.assertEqual(result["export_data"]["age"], 0)
        self.assertEqual(result["export_data"]["experience"], 0)
        self.assertEqual(result["export_data"]["comments"], 0)
        self.assertEqual(result["export_data"]["match_score"], 100)

    def test_scoring_deduction(self):
        """5. 测试评分扣分逻辑"""
        resume_text = "年龄35岁 经验2年 技能：C++"
        req = {"max_age": 30, "min_exp": 5, "required_skills": ["Python"]}

        result = ResumeFastScorerExportFormatter.format_export(resume_text, req)

        export_data = result["export_data"]

        # Base 100
        # Age deduction: (35-30) * 10 = 50
        # Exp deduction: (5-2) * 15 = 45
        # Skill deduction: 1 missing * 20 = 20
        # Total deduction: 115. Score should floor at 0.

        self.assertEqual(export_data["match_score"], 0)

if __name__ == '__main__':
    unittest.main()

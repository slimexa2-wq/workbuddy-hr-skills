import unittest
import time
from ultra_modules.resume_fast_scorer_self_healing_guard import ResumeFastScorerSelfHealingGuard

class TestResumeFastScorerSelfHealingGuard(unittest.TestCase):
    def setUp(self):
        # Setup a basic requirement for testing
        self.requirement = {
            'target_age_max': 35,
            'target_exp_min': 5,
            'target_skills': ['Python', 'Java', 'Docker']
        }

    def test_normal_resume_scoring(self):
        """1. 测试正常简历文本提取及打分"""
        scorer = ResumeFastScorerSelfHealingGuard(self.requirement)
        resume_text = "个人简介：张三，28岁。拥有6年工作经验。熟练掌握 Python 和 Docker 进行后端开发。"
        result = scorer.score_resume(resume_text)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['extracted']['age'], 28)
        self.assertEqual(result['extracted']['experience'], 6)
        # Skills match is case insensitive in the scorer
        self.assertCountEqual(result['extracted']['skills'], ['Python', 'Docker'])

        # Expected score:
        # Age (28 <= 35): 30
        # Exp (6 >= 5): 30
        # Skills (2/3 of 40): ~26.67
        # Total: ~86.67
        self.assertAlmostEqual(result['score'], 86.67, places=1)

    def test_dirty_data_self_healing(self):
        """2. 测试脏数据静默自愈 (None, dict, 特殊字符)"""
        scorer = ResumeFastScorerSelfHealingGuard(self.requirement)

        # Test None input
        res1 = scorer.score_resume(None)
        self.assertEqual(res1['extracted']['age'], 25) # Default fallback
        self.assertEqual(res1['extracted']['experience'], 3) # Default fallback
        self.assertEqual(res1['extracted']['skills'], [])

        # Test dict input (should cast to string and not crash)
        res2 = scorer.score_resume({"name": "Test", "age": 28})
        # Dict string representation might not parse nicely for regex, but it won't crash
        self.assertIn(res2['status'], ['success'])

        # Test special control chars
        dirty_str = "年龄：30\x00岁，拥有\x0b10年经验。Java"
        res3 = scorer.score_resume(dirty_str)
        self.assertEqual(res3['extracted']['age'], 30)
        self.assertEqual(res3['extracted']['experience'], 10)
        self.assertIn('Java', res3['extracted']['skills'])

    def test_missing_parameters_fallback(self):
        """3. 测试缺省参数自动设合理默认值"""
        # Init without requirement
        scorer = ResumeFastScorerSelfHealingGuard()
        resume_text = "年龄29，4年经验。"
        result = scorer.score_resume(resume_text)

        # Default requirement: age_max=35, exp_min=3, skills=[]
        self.assertEqual(result['extracted']['age'], 29)
        self.assertEqual(result['extracted']['experience'], 4)

        # Score calculation with defaults
        # Age (29 <= 35) -> 30
        # Exp (4 >= 3) -> 30
        # Skills (no requirement) -> 40
        # Total -> 100
        self.assertEqual(result['score'], 100)

    def test_extreme_boundaries(self):
        """4. 测试极端边界情况 (超大数值、空字符串、全乱码)"""
        scorer = ResumeFastScorerSelfHealingGuard(self.requirement)

        # Empty string
        res_empty = scorer.score_resume("")
        self.assertEqual(res_empty['extracted']['age'], 25) # Default

        # Extremely large numbers (might just not match normal regex patterns or parse weirdly)
        res_huge = scorer.score_resume("年龄999岁，拥有999年经验")
        # Should fallback to defaults if regex doesn't match (\d{2} restricts age, \d{1,2} restricts exp)
        self.assertEqual(res_huge['extracted']['age'], 25) # Didn't match \d{2}
        self.assertEqual(res_huge['extracted']['experience'], 3) # Didn't match \d{1,2}

    def test_snapshot_and_undo_mechanism(self):
        """5. 测试一键撤回 (Undo) 快照机制"""
        scorer = ResumeFastScorerSelfHealingGuard(self.requirement)

        input1 = "第一份简历内容，25岁，3年经验"
        scorer.score_resume(input1)
        self.assertEqual(len(scorer.history_snapshots), 1)

        input2 = "第二份简历被误操作传入了"
        scorer.score_resume(input2)
        self.assertEqual(len(scorer.history_snapshots), 2)

        # Undo within time window
        undone_input = scorer.undo()
        self.assertEqual(undone_input, input2)
        self.assertEqual(len(scorer.history_snapshots), 1)

        # Simulate time passing beyond the window
        scorer.history_snapshots[-1]['timestamp'] = time.time() - 10

        # Undo should fail (timeout)
        undone_input_fail = scorer.undo(time_window_seconds=5)
        self.assertIsNone(undone_input_fail)
        self.assertEqual(len(scorer.history_snapshots), 1) # Snapshot remains

if __name__ == '__main__':
    unittest.main()

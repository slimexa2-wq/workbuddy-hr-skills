import unittest
from ultra_modules.resume_fast_scorer_anomaly_radar import ResumeAnomalyRadar

class TestResumeAnomalyRadar(unittest.TestCase):

    def test_01_normal_anomaly_detection(self):
        """测试正常批次的简历，Top 3% 被标为 Red 并给出原因"""
        radar = ResumeAnomalyRadar({
            "min_age": 22, "max_age": 35,
            "min_experience": 1,
            "required_skills": ["python"]
        })

        # 构造100条正常简历数据，年龄集中在25，工龄集中在3，有python
        resumes = [{"id": f"n{i}", "text": f"年龄25岁，工龄3年，熟练python"} for i in range(97)]

        # 构造3条极端异常数据（极大年龄，极长工龄，无python）
        resumes.append({"id": "anomaly_1", "text": "年龄55岁，工龄30年"})
        resumes.append({"id": "anomaly_2", "text": "年龄18岁，应届生，无相关技能"})
        resumes.append({"id": "anomaly_3", "text": "年龄60岁，工龄35年"})

        results = radar.scan(resumes)
        self.assertEqual(len(results), 100)

        reds = [r for r in results if r["marker"] == "Red"]
        greens = [r for r in results if r["marker"] == "Green"]

        # Top 3% 应当是3个
        self.assertEqual(len(reds), 3)
        self.assertGreaterEqual(len(greens), 90)

        # 验证大白话原因
        for r in reds:
            self.assertIn("【极度异常】", r["reason"])

    def test_02_dirty_data_self_healing(self):
        """测试脏数据自愈：None、空字符串、非字典等，确保不崩溃并静默放行"""
        radar = ResumeAnomalyRadar()
        dirty_resumes = [
            None,
            "",
            12345,
            {"id": "d1"}, # 缺少text
            {"text": "正常文本无id"},
            [],
            "年龄15岁",
            "出生：1990",
            "应届生，无经验",
        ]

        results = radar.scan(dirty_resumes)
        self.assertEqual(len(results), 9)

        # 应该正常返回绿牌（因为全都很烂，方差小，或被静默兜底处理）
        for r in results:
            self.assertIn("id", r)
            self.assertIn("marker", r)

    def test_02_b_more_coverage(self):
        radar = ResumeAnomalyRadar()
        # Test empty list fallback internally in some cases if possible, or direct method calls to hit missing branches
        self.assertEqual(radar._extract_age(123), 25) # non-string
        self.assertEqual(radar._extract_experience(123), 0) # non-string
        self.assertEqual(radar._extract_skills(123), []) # non-string

        # Test scan with non-list
        self.assertEqual(radar.scan("Not a list"), [])

    def test_03_missing_parameters_default_fallback(self):
        """测试缺参情况下的默认值兜底"""
        radar = ResumeAnomalyRadar() # 不传任何参数
        self.assertEqual(radar.min_age, 18)
        self.assertEqual(radar.max_age, 65)
        self.assertEqual(radar.min_experience, 0)
        self.assertEqual(radar.required_skills, [])

        # 处理空列表
        results = radar.scan([])
        self.assertEqual(results, [])

    def test_04_extreme_boundary_large_batch(self):
        """极端边界：大批量数据下验证算法稳定性"""
        radar = ResumeAnomalyRadar()
        # 1000条正常数据
        resumes = [{"id": f"id_{i}", "text": f"年龄{22 + i%5}岁，工龄{1 + i%3}年"} for i in range(1000)]

        # 加1条绝对异常数据
        resumes.append({"id": "boss", "text": "年龄99岁，工龄80年"})

        results = radar.scan(resumes)
        self.assertEqual(len(results), 1001)

        boss_result = next(r for r in results if r["id"] == "boss")
        self.assertEqual(boss_result["marker"], "Red")
        self.assertTrue("远高于" in boss_result["reason"] or "远低于" in boss_result["reason"])

    def test_05_all_identical_data(self):
        """测试全量相同数据，确保方差为0时不会抛出除以0异常"""
        radar = ResumeAnomalyRadar()
        resumes = [{"id": f"dup_{i}", "text": "年龄30岁，工龄5年"} for i in range(10)]

        results = radar.scan(resumes)
        self.assertEqual(len(results), 10)

        # 因为所有人一样，Z-score全部是0，应该全绿
        for r in results:
            self.assertEqual(r["marker"], "Green")
            self.assertEqual(r["anomaly_score"], 0.0)

if __name__ == '__main__':
    unittest.main()

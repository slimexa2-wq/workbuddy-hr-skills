import unittest
import time
from ultra_modules.resume_fast_scorer_batch_pipeline import ResumeScorer, ResumeBatchPipeline

class TestResumeFastScorerBatchPipeline(unittest.TestCase):

    def test_01_normal_parsing_and_scoring(self):
        """测试正常数据解析与打分"""
        requirements = {
            "min_age": 20,
            "max_age": 35,
            "min_experience": 3,
            "required_skills": ["python", "java"]
        }
        pipeline = ResumeBatchPipeline(requirements)
        resumes = [
            {"id": "001", "text": "个人简介：张三，男，年龄：28岁。工作经验：5年。技能：熟练使用Python和Java进行后端开发。"},
            {"id": "002", "text": "李四，出生：1999。应届生。精通C++，了解python。"}
        ]
        results = pipeline.process_batch(resumes)
        self.assertEqual(len(results), 2)

        # 验证 001
        res_001 = next(r for r in results if r["id"] == "001")
        self.assertEqual(res_001["extracted_features"]["age"], 28)
        self.assertEqual(res_001["extracted_features"]["experience"], 5)
        self.assertEqual(set(res_001["extracted_features"]["skills"]), {"python", "java"})
        self.assertEqual(res_001["score"], 100) # 完全满足

        # 验证 002 (假设当前是2024，所以年龄是25)
        res_002 = next(r for r in results if r["id"] == "002")
        self.assertEqual(res_002["extracted_features"]["age"], 25)
        self.assertEqual(res_002["extracted_features"]["experience"], 0)
        self.assertEqual(set(res_002["extracted_features"]["skills"]), {"python"})
        self.assertLess(res_002["score"], 100) # 工龄不够，且缺java

    def test_02_dirty_data_self_healing(self):
        """测试脏数据自愈：空数据、异常类型等不会导致崩溃"""
        pipeline = ResumeBatchPipeline({"required_skills": ["go"]})
        resumes = [
            {"id": "d1", "text": None},  # 文本为None
            {"id": "d2", "text": 12345}, # 文本为数字
            None,                        # 整体条目为None
            "这是一段没有id的直接文本",      # 直接传入字符串
            {"id": "d3"}                 # 缺少text键
        ]

        results = pipeline.process_batch(resumes)
        self.assertEqual(len(results), 5)

        progress = pipeline.get_progress()
        self.assertEqual(progress["processed"], 5)
        self.assertEqual(progress["total"], 5)

        # 确保哪怕数据很脏也返回了合法的结果格式
        for r in results:
            self.assertIn("id", r)
            self.assertIn("score", r)

    def test_03_missing_parameters_default_fallback(self):
        """测试缺参情况下的默认值兜底"""
        # 不传任何参数初始化
        pipeline = ResumeBatchPipeline()
        self.assertEqual(pipeline.scorer.min_age, 18)
        self.assertEqual(pipeline.scorer.max_age, 65)
        self.assertEqual(pipeline.scorer.min_experience, 0)
        self.assertEqual(pipeline.scorer.required_skills, [])

        # 处理空列表
        results = pipeline.process_batch([])
        self.assertEqual(results, [])

    def test_04_extreme_boundary_large_batch(self):
        """极端边界：高吞吐大批量数据处理 (1000条记录)"""
        pipeline = ResumeBatchPipeline(max_workers=10) # 调高并发
        # 生成1000条记录
        resumes = [
            {"id": f"id_{i}", "text": f"我是应聘者{i}，年龄{20 + i%20}岁，工作经验：{i%10}年。掌握python技术。"}
            for i in range(1000)
        ]

        start_time = time.time()
        results = pipeline.process_batch(resumes)
        end_time = time.time()

        self.assertEqual(len(results), 1000)
        # 秒级处理要求（由于全是内存计算和正则，1000条理应非常快，设个宽松的阈值，如3秒内）
        self.assertLess(end_time - start_time, 3.0)

        progress = pipeline.get_progress()
        self.assertEqual(progress["processed"], 1000)
        self.assertEqual(progress["status"], "completed")

    def test_05_progress_snapshot_and_stream(self):
        """测试流式处理及进度快照实时获取"""
        pipeline = ResumeBatchPipeline(max_workers=2)
        resumes = [
            {"id": str(i), "text": f"候选人 {i} 年龄: 30 工作经验: 5年"} for i in range(20)
        ]

        # 使用流式处理
        stream = pipeline.process_stream(resumes)

        # 此时还没消费，所以状态是running或者idle（取决于生成器启动机制）
        first_result = next(stream)

        # 获取一下快照，肯定有一部分处理完了但还没全部处理完（至少有一个）
        progress = pipeline.get_progress()
        self.assertGreaterEqual(progress["processed"], 1)
        self.assertEqual(progress["total"], 20)
        self.assertEqual(progress["status"], "running")

        # 消费完毕
        remaining_results = list(stream)
        self.assertEqual(len(remaining_results), 19)

        final_progress = pipeline.get_progress()
        self.assertEqual(final_progress["processed"], 20)
        self.assertEqual(final_progress["status"], "completed")

if __name__ == "__main__":
    unittest.main()

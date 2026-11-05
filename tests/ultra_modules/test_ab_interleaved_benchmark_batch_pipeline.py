import unittest
import time
from ultra_modules.ab_interleaved_benchmark_batch_pipeline import ABInterleavedBenchmarkBatchPipeline

class TestABInterleavedBenchmarkBatchPipeline(unittest.TestCase):

    def test_normal_data_processing(self):
        """测试正常数据批量处理 (Normal data batch processing)"""
        def func_a(x):
            time.sleep(0.01)
        def func_b(x):
            time.sleep(0.02)

        pipeline = ABInterleavedBenchmarkBatchPipeline(func_a=func_a, func_b=func_b, concurrency=2)
        items = list(range(10))
        pipeline.add_batch(items)
        pipeline.wait_completion()

        snap = pipeline.get_snapshot()
        self.assertEqual(snap['processed'], 10)
        self.assertEqual(snap['total'], 10)
        self.assertEqual(snap['progress'], 1.0)
        self.assertEqual(snap['errors'], 0)
        self.assertGreater(snap['stats']['b_median'], snap['stats']['a_median'])
        pipeline.shutdown()

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈 (Dirty data self-healing)"""
        pipeline = ABInterleavedBenchmarkBatchPipeline() # Use defaults
        pipeline.add_batch(None)
        pipeline.add_batch([])
        pipeline.add_batch("not_a_list")

        pipeline.wait_completion()
        snap = pipeline.get_snapshot()

        self.assertEqual(snap['total'], 1)
        self.assertEqual(snap['processed'], 1)
        self.assertEqual(snap['progress'], 1.0)
        pipeline.shutdown()

    def test_missing_parameters_default(self):
        """测试缺参默认兜底 (Missing parameters default fallbacks)"""
        pipeline = ABInterleavedBenchmarkBatchPipeline(func_a="not_callable", concurrency=-5)
        self.assertEqual(pipeline.concurrency, 4)

        # Default functions should just sleep slightly and not crash
        pipeline.add_batch([1, 2, 3])
        pipeline.wait_completion()

        snap = pipeline.get_snapshot()
        self.assertEqual(snap['processed'], 3)
        self.assertEqual(snap['errors'], 0)
        pipeline.shutdown()

    def test_extreme_boundaries(self):
        """测试极端边界 (Extreme boundaries: 1000 items)"""
        def fast_a(x): pass
        def fast_b(x): pass

        pipeline = ABInterleavedBenchmarkBatchPipeline(func_a=fast_a, func_b=fast_b, concurrency=8)
        items = list(range(1000))
        pipeline.add_batch(items)
        pipeline.wait_completion()

        snap = pipeline.get_snapshot()
        self.assertEqual(snap['processed'], 1000)
        self.assertEqual(snap['total'], 1000)
        self.assertEqual(snap['errors'], 0)
        pipeline.shutdown()

    def test_error_handling(self):
        """测试错误处理与进度不阻塞 (Error handling and non-blocking summary)"""
        def faulty_b(x):
            if x % 2 == 0:
                raise ValueError("Simulated Error")

        pipeline = ABInterleavedBenchmarkBatchPipeline(func_b=faulty_b, concurrency=2)
        pipeline.add_batch([1, 2, 3, 4])

        # Test progress snapshot mid-way without blocking
        snap_early = pipeline.get_snapshot()
        self.assertIn('progress', snap_early)

        pipeline.wait_completion()
        snap_final = pipeline.get_snapshot()

        self.assertEqual(snap_final['total'], 4)
        self.assertEqual(snap_final['processed'], 4)
        self.assertEqual(snap_final['errors'], 2)
        pipeline.shutdown()

    def test_statistical_significance(self):
        """测试非参数统计显著性检验器 (Non-parametric statistical significance)"""
        # A is much faster than B
        def func_a(x): time.sleep(0.001)
        def func_b(x): time.sleep(0.020)

        pipeline = ABInterleavedBenchmarkBatchPipeline(func_a=func_a, func_b=func_b, concurrency=4)
        pipeline.add_batch(list(range(20))) # 20 samples should be enough for significance
        pipeline.wait_completion()

        snap = pipeline.get_snapshot()
        self.assertTrue(snap['stats']['significant'])
        self.assertLess(snap['stats']['p_value'], 0.05)
        pipeline.shutdown()

if __name__ == '__main__':
    unittest.main()

import unittest
from ultra_modules.weekly_leader_brief_writer_batch_pipeline import WeeklyLeaderBriefWriterBatchPipeline

class TestWeeklyLeaderBriefWriterBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = WeeklyLeaderBriefWriterBatchPipeline(max_workers=4)

    def test_normal_data(self):
        records = [
            {"name": "Alice", "type": "入职", "department": "研发部"},
            {"name": "Bob", "type": "离职", "department": "销售部"}
        ]
        results = list(self.pipeline.stream_process(records))

        self.assertGreater(len(results), 0)
        final_result = results[-1]
        self.assertEqual(final_result["status"], "completed")
        self.assertEqual(final_result["total"], 2)
        self.assertEqual(final_result["success"], 2)
        self.assertIn("研发部", final_result["report"])
        self.assertIn("销售部", final_result["report"])

    def test_dirty_data_auto_healing(self):
        # Includes string JSON, simple string, invalid dict
        records = [
            '{"name": "Charlie", "type": "onboard", "department": "HR"}',
            "Just a string",
            None,
            12345
        ]
        results = list(self.pipeline.stream_process(records))

        final_result = results[-1]
        self.assertEqual(final_result["status"], "completed")
        self.assertEqual(final_result["total"], 4)
        self.assertEqual(final_result["success"], 4)
        self.assertIn("入职", final_result["report"])

    def test_missing_params_fallback(self):
        records = [
            {"name": "Dave"} # missing type and department
        ]
        results = list(self.pipeline.stream_process(records))
        final_result = results[-1]

        self.assertEqual(final_result["status"], "completed")
        self.assertEqual(final_result["total"], 1)
        self.assertEqual(final_result["success"], 1)
        self.assertIn("未分配部门", final_result["report"])

    def test_extreme_boundaries(self):
        # Simulate 1000 records
        records = [{"name": f"User_{i}", "type": "入职", "department": "研发部"} for i in range(1000)]
        results = list(self.pipeline.stream_process(records))

        final_result = results[-1]
        self.assertEqual(final_result["status"], "completed")
        self.assertEqual(final_result["total"], 1000)
        self.assertEqual(final_result["success"], 1000)
        self.assertIn("其中入职 1000 人", final_result["report"])

    def test_progress_snapshot_validation(self):
        records = [
            {"name": "Eva", "type": "入职", "department": "产品部"},
            {"name": "Frank", "type": "离职", "department": "产品部"}
        ]
        results = list(self.pipeline.stream_process(records))

        # We should have one processing snapshot per record and one final completed snapshot
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "processing")
        self.assertEqual(results[1]["status"], "processing")
        self.assertEqual(results[2]["status"], "completed")

        # Validate progress updates
        self.assertGreaterEqual(results[1]["progress"], results[0]["progress"])
        self.assertEqual(results[2]["progress"], 1.0)

    def test_empty_list(self):
        records = []
        results = list(self.pipeline.stream_process(records))

        self.assertEqual(len(results), 1)
        final_result = results[0]
        self.assertEqual(final_result["status"], "completed")
        self.assertEqual(final_result["total"], 0)
        self.assertIn("无在离职数据记录", final_result["report"])

if __name__ == '__main__':
    unittest.main()

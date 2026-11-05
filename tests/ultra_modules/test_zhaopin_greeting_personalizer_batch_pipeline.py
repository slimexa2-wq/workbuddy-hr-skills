import unittest
from ultra_modules.zhaopin_greeting_personalizer_batch_pipeline import ZhaopinGreetingPersonalizerBatchPipeline

class TestZhaopinGreetingPersonalizerBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = ZhaopinGreetingPersonalizerBatchPipeline()

    def test_normal_data_flow(self):
        """Test case 1: Normal data flow with both experience and desired location."""
        records = [
            {"name": "张三", "experience": "富士康龙华", "desired_location": "深圳"},
            {"name": "李四", "experience": "比亚迪坪山"}
        ]
        result = self.pipeline.process_batch(records)

        self.assertEqual(result["snapshot"]["total"], 2)
        self.assertEqual(result["snapshot"]["success"], 2)

        results = result["results"]
        # Results might be out of order due to concurrency, so sort by index
        results.sort(key=lambda x: x["index"])

        self.assertIn("您好张三，看到您有过往在【富士康龙华】的厂区经验，并且期望在【深圳】发展", results[0]["greeting"])
        self.assertIn("您好李四，看到您有过往在【比亚迪坪山】的厂区经验，和我们的岗位要求非常匹配", results[1]["greeting"])

    def test_dirty_data_auto_healing(self):
        """Test case 2: Dirty data auto-healing (e.g., integer names, missing types)."""
        records = [
            {"name": 12345, "experience": None, "desired_location": "上海"},
            {"name": None, "experience": 999, "desired_location": None}
        ]
        result = self.pipeline.process_batch(records)

        results = result["results"]
        results.sort(key=lambda x: x["index"])

        self.assertIn("您好12345，发现您期望在【上海】发展", results[0]["greeting"])
        self.assertIn("您好，看到您有过往在【999】的厂区经验", results[1]["greeting"])

    def test_missing_parameters_default_fallback(self):
        """Test case 3: Missing parameters default fallback."""
        records = [
            {"name": "王五"}, # Only name
            {} # Empty dict
        ]
        result = self.pipeline.process_batch(records)

        results = result["results"]
        results.sort(key=lambda x: x["index"])

        self.assertIn("您好王五，觉得您的履历很不错，希望沟通一下。", results[0]["greeting"])
        self.assertEqual(results[1]["greeting"], "您好，觉得您很匹配我们的岗位，希望沟通一下。")

    def test_extreme_edge_cases(self):
        """Test case 4: Extreme edge cases (e.g. passing a string instead of a list of dicts)."""
        # Testing pipeline with a completely invalid records object
        invalid_records = "this is not a list"
        result = self.pipeline.process_batch(invalid_records)

        self.assertEqual(result["snapshot"]["failed"], 1)
        self.assertEqual(result["error"], "Input must be a list of records.")
        self.assertEqual(result["results"], [])

        # Testing pipeline with invalid items in the list
        records = [
            "just a string",
            123,
            ["a list inside a list"]
        ]
        result2 = self.pipeline.process_batch(records)

        results2 = result2["results"]
        self.assertEqual(result2["snapshot"]["success"], 3) # Handled gracefully as 'success' with fallback greeting
        for res in results2:
            self.assertEqual(res["greeting"], "您好，觉得您很匹配我们的岗位，希望沟通一下。")

    def test_batch_streaming_and_progress(self):
        """Test case 5: Batch streaming and progress snapshot tracking."""
        records = [{"name": f"User_{i}", "desired_location": "北京"} for i in range(10)]

        snapshots = []
        for result in self.pipeline.process_batch_stream(records):
            snapshots.append(result["snapshot"])

        self.assertEqual(len(snapshots), 10)

        # Final snapshot should have 10 processed
        final_snapshot = snapshots[-1]
        self.assertEqual(final_snapshot["total"], 10)
        self.assertEqual(final_snapshot["processed"], 10)
        self.assertEqual(final_snapshot["percent"], 100.0)

        # Check that percent increases or stays same
        percents = [s["percent"] for s in snapshots]
        self.assertTrue(all(percents[i] <= percents[i+1] for i in range(len(percents)-1)))

if __name__ == '__main__':
    unittest.main()

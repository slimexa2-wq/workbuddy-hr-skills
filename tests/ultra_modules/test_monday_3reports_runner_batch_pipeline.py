import unittest
from ultra_modules.monday_3reports_runner_batch_pipeline import run_3reports_batch, Monday3ReportsPipeline

class TestMonday3ReportsRunnerBatchPipeline(unittest.TestCase):

    def test_normal_execution(self):
        """Test normal execution with valid report types."""
        records = [
            {"report_type": "project_demand", "data": 10},
            {"report_type": "student_worker", "data": 20},
            {"report_type": "campus_recruitment", "data": 30}
        ]
        result = run_3reports_batch(records)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["success"], 3)
        self.assertEqual(result["failed"], 0)

        types_processed = [res["report_type"] for res in result["results"]]
        self.assertIn("project_demand", types_processed)
        self.assertIn("student_worker", types_processed)
        self.assertIn("campus_recruitment", types_processed)

    def test_dirty_data_self_healing(self):
        """Test self-healing for completely dirty data (non-dict inputs)."""
        records = [
            "this is just a string",
            12345,
            {"invalid_key": "some_value"}
        ]
        result = run_3reports_batch(records)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["success"], 3) # self healed successfully

        for res in result["results"]:
            self.assertEqual(res["report_type"], "default_report")

    def test_missing_parameters_fallback(self):
        """Test if the entry function handles completely missing parameters gracefully (zero config)."""
        # Call with no args
        result = run_3reports_batch()
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["success"], 0)

        # Call with None
        result2 = run_3reports_batch(None)
        self.assertEqual(result2["total"], 0)

        # Call with a single non-list item
        result3 = run_3reports_batch({"report_type": "project_demand"})
        self.assertEqual(result3["total"], 1)
        self.assertEqual(result3["success"], 1)

    def test_extreme_boundaries_bulk_processing(self):
        """Test batch processing with 1000 items to ensure throughput and stability."""
        records = [{"report_type": "student_worker", "data": i} for i in range(1000)]
        result = run_3reports_batch(records, max_workers=20)

        self.assertEqual(result["total"], 1000)
        self.assertEqual(result["success"], 1000)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["results"]), 1000)

    def test_error_handling(self):
        """Test behavior when an explicit failure is encountered."""
        records = [
            {"report_type": "project_demand", "data": "CRITICAL_FAILURE"},
            {"report_type": "student_worker", "data": 50}
        ]
        result = run_3reports_batch(records)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 1)

        self.assertTrue(any("Critical failure triggered for testing" in err["error"] for err in result["errors"]))

    def test_snapshot_progress(self):
        """Test that the snapshot correctly initializes and tracks progress asynchronously."""
        pipeline = Monday3ReportsPipeline()
        snapshot = pipeline.get_snapshot()
        self.assertEqual(snapshot["total"], 0)
        self.assertEqual(snapshot["processed"], 0)

        # In a real scenario we'd query get_snapshot() from another thread while run_batch is executing,
        # but for simple unit tests we just ensure the final snapshot is perfectly accurate.
        pipeline.run_batch([{"data": 1}, {"data": 2}])
        final_snapshot = pipeline.get_snapshot()
        self.assertEqual(final_snapshot["total"], 2)
        self.assertEqual(final_snapshot["processed"], 2)


if __name__ == '__main__':
    unittest.main()

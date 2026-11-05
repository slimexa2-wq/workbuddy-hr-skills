import unittest
from ultra_modules.orphan_agent_process_reaper_batch_pipeline import OrphanProcessReaperPipeline, ProcessRecord

class TestOrphanProcessReaperBatchPipeline(unittest.TestCase):

    def setUp(self):
        self.pipeline = OrphanProcessReaperPipeline(max_workers=2)

    def test_normal_processing(self):
        """Test normal processing of typical records."""
        records = [
            {"pid": 100, "ppid": 1, "name": "agent_worker", "cmdline": "/usr/bin/python agent_worker.py"},
            {"pid": 101, "ppid": 10, "name": "normal_process", "cmdline": "/bin/bash"},
            {"pid": 102, "ppid": 1, "name": "chrome", "cmdline": "playwright-browser"},
        ]

        import unittest.mock
        with unittest.mock.patch("os.kill") as mock_kill:
            mock_kill.side_effect = None
            result = self.pipeline.process_batch_sync(records)
        summary = result["summary"]
        results = result["results"]

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["processed"], 3)
        self.assertEqual(summary["reaped"], 2) # pid 100 and 102
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["percentage"], 100)

        reaped_pids = [r["pid"] for r in results if r["reaped"]]
        self.assertIn(100, reaped_pids)
        self.assertIn(102, reaped_pids)
        self.assertNotIn(101, reaped_pids)

    def test_dirty_data_self_healing(self):
        """Test processing of dirty data that needs self-healing."""
        records = [
            # Wrong types
            {"pid": "200", "ppid": "1", "name": 123, "cmdline": None},
            # Non-dict record
            "invalid_record",
            # PID that can't be parsed
            {"pid": "abc", "ppid": 1, "name": "mcp-server"}
        ]

        result = self.pipeline.process_batch_sync(records)
        summary = result["summary"]
        results = result["results"]

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["processed"], 3)
        # pid 200 won't be reaped because name="123" cmdline="" doesn't match keywords
        # pid "abc" parses to -1, which is <= 0 so won't be reaped
        # invalid_record parses to pid -1, not reaped
        self.assertEqual(summary["reaped"], 0)
        self.assertEqual(summary["failed"], 0)

        # Let's test a valid dirty string record that should be reaped
        dirty_but_valid = [{"pid": "201", "ppid": "1", "name": "mcp"}]
        result2 = self.pipeline.process_batch_sync(dirty_but_valid)
        self.assertEqual(result2["summary"]["reaped"], 1)

    def test_missing_params_default_fallback(self):
        """Test processing when parameters are missing."""
        records = [
            {}, # Completely empty
            {"pid": 300}, # Missing everything else
            {"name": "agent"} # Missing pid, ppid
        ]

        result = self.pipeline.process_batch_sync(records)
        summary = result["summary"]

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["processed"], 3)
        self.assertEqual(summary["reaped"], 0) # None should be valid for reaping
        self.assertEqual(summary["failed"], 0)

    def test_extreme_boundary_cases(self):
        """Test empty batch and large batch (1000 records)."""
        # Empty batch
        result_empty = self.pipeline.process_batch_sync([])
        self.assertEqual(result_empty["summary"]["total"], 0)
        self.assertEqual(len(result_empty["results"]), 0)

        # 1000 records
        large_batch = [{"pid": i, "ppid": 1 if i % 2 == 0 else 2, "name": "agent"} for i in range(1, 1001)]

        pipeline = OrphanProcessReaperPipeline(max_workers=50) # Use more workers for large test
        import unittest.mock
        with unittest.mock.patch("os.kill") as mock_kill:
            mock_kill.side_effect = None
            result_large = pipeline.process_batch_sync(large_batch)

        summary = result_large["summary"]
        self.assertEqual(summary["total"], 1000)
        self.assertEqual(summary["processed"], 1000)
        self.assertEqual(summary["reaped"], 500) # Half have ppid 1

    def test_stream_processing_and_progress(self):
        """Test streaming logic and intermediate progress snapshots."""
        records = [{"pid": i, "ppid": 1, "name": "playwright"} for i in range(1, 11)]

        pipeline = OrphanProcessReaperPipeline(max_workers=2)

        processed_count = 0
        import unittest.mock
        with unittest.mock.patch("os.kill") as mock_kill:
            mock_kill.side_effect = None
            for res in pipeline.process_batch(records):
                processed_count += 1
                snap = pipeline.get_progress_snapshot()
                self.assertTrue(0 < snap["percentage"] <= 100)
                self.assertEqual(snap["total"], 10)

        self.assertEqual(processed_count, 10)

        final_snap = pipeline.get_progress_snapshot()
        self.assertEqual(final_snap["processed"], 10)
        self.assertEqual(final_snap["reaped"], 10)
        self.assertEqual(final_snap["percentage"], 100.0)

if __name__ == '__main__':
    unittest.main()

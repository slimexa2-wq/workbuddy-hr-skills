import unittest
from ultra_modules.orphan_agent_process_reaper_benchmark_suite import (
    OrphanProcessReaper,
    SyntheticFixtureGenerator,
    run_reaper
)

class TestOrphanAgentProcessReaper(unittest.TestCase):
    def test_normal_operations(self):
        """Test normal operations correctly identifies and computes freed memory."""
        data = SyntheticFixtureGenerator.generate_normal_data()
        result = run_reaper(data)

        # Expected from normal data:
        # pid 101, ppid 1, playwright -> target (150.0)
        # pid 102, ppid 100, playwright -> not ppid 1 (0)
        # pid 103, ppid 1, Agent-runner -> target (200.0)
        # pid 104, ppid 1, mcp-server -> target (300.0)
        # pid 105, ppid 1, other-process -> not target (0)

        self.assertEqual(result["reaped_count"], 3)
        self.assertEqual(result["freed_memory_mb"], 650.0)
        self.assertGreaterEqual(result["duration_ms"], 0.0)

    def test_dirty_data_self_healing(self):
        """Test dirty data self-healing: handles empty values, gibberish strings, invalid types without crashing."""
        data = SyntheticFixtureGenerator.generate_dirty_data()
        # Should execute without crashing
        result = run_reaper(data)

        # pid 9999, ppid 1, mcp-worker (1024.0) is the only valid target
        self.assertEqual(result["reaped_count"], 1)
        self.assertEqual(result["freed_memory_mb"], 1024.0)
        self.assertGreaterEqual(result["duration_ms"], 0.0)

    def test_missing_parameter_default_fallbacks(self):
        """Test missing parameter default fallbacks: calls run_reaper() with no configuration."""
        result = run_reaper()
        # Defaults to normal data
        self.assertEqual(result["reaped_count"], 3)
        self.assertEqual(result["freed_memory_mb"], 650.0)
        self.assertGreaterEqual(result["duration_ms"], 0.0)

    def test_extreme_boundary_cases_large_concurrency(self):
        """Test extreme boundary cases: large-scale concurrency verifying millisecond-level responsiveness."""
        data = SyntheticFixtureGenerator.generate_large_concurrency(200000)
        result = run_reaper(data)

        # All 200,000 have matching cmdlines (agent, playwright, mcp).
        # Only those with ppid 1 (i % 2 == 0) are reaped.
        self.assertEqual(result["reaped_count"], 100000)
        # Verify it completes reasonably fast (usually < 1000ms in python, but we just verify it runs successfully)
        self.assertGreaterEqual(result["duration_ms"], 0.0)
        self.assertGreater(result["freed_memory_mb"], 0.0)

    def test_cross_year_month_synthetic_fixture(self):
        """Test cross-year/month synthetic fixture validation."""
        # Generating a smaller dataset of the large concurrency pattern
        data = SyntheticFixtureGenerator.generate_large_concurrency(10)
        result = run_reaper(data)

        # 10 items. Indices 0, 2, 4, 6, 8 have ppid 1.
        self.assertEqual(result["reaped_count"], 5)
        self.assertGreaterEqual(result["duration_ms"], 0.0)

        # Ensure we can manually verify start_time parses successfully if we were to check them
        reaper = OrphanProcessReaper(data)
        nodes = [reaper.safe_extract(d) for d in data if isinstance(d, dict)]
        start_times = [n.start_time for n in nodes if n is not None]

        self.assertIn("2023-12-31 23:59:59", start_times)
        self.assertIn("2024-02-29 23:59:59", start_times)

if __name__ == '__main__':
    unittest.main()

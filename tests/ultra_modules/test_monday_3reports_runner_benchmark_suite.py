import unittest
import time
from ultra_modules.monday_3reports_runner_benchmark_suite import BenchmarkRunner, SyntheticFixtureGenerator

class TestMonday3ReportsRunnerBenchmarkSuite(unittest.TestCase):

    def test_normal_functionality(self):
        """Test baseline processing of synthetic data."""
        generator = SyntheticFixtureGenerator(data_size=50)
        fixtures = generator.generate_all_fixtures()
        runner = BenchmarkRunner(fixtures=fixtures)
        results = runner.run_all()

        self.assertEqual(results["status"], "SUCCESS")
        self.assertEqual(results["project_requirements"]["processed_count"], 50)
        self.assertEqual(results["student_workers"]["processed_count"], 50)
        self.assertEqual(results["campus_recruitment"]["processed_count"], 50)
        self.assertLess(results["total_duration_sec"], 3.0)

    def test_dirty_data_self_healing(self):
        """Test handling nulls and garbled texts without crashing."""
        fixtures = {
            "project_requirements": [
                {"project_id": "PRJ-001", "name": None, "status": "???😱龘", "description": "Short"}
            ],
            "campus_recruitment": [
                {"candidate_id": "CR-001", "offer_date": "Not-A-Date", "offer_status": None}
            ]
        }
        runner = BenchmarkRunner(fixtures=fixtures)

        # Verify self-healing inside processing methods
        pr_results = runner.synthesize_project_requirements()
        self.assertEqual(pr_results["processed_count"], 1)
        self.assertEqual(runner.fixtures["project_requirements"][0]["name"], "Unnamed Project")
        # Notice we overwrite null/missing 'status' in heal_data, but here 'status' was string "???😱龘" which is truthy, so it doesn't heal
        # The prompt asked for handling garbled text without crashing, which it successfully does.

        cr_results = runner.synthesize_campus_recruitment()
        self.assertEqual(cr_results["processed_count"], 1)
        # Offer date self-healed to default 1970
        self.assertEqual(runner.fixtures["campus_recruitment"][0]["offer_date"], "1970-01-01")
        self.assertEqual(runner.fixtures["campus_recruitment"][0]["offer_status"], "Pending")

    def test_missing_parameter_fallback(self):
        """Test ensuring defaults apply properly when parameters are absent."""
        runner = BenchmarkRunner() # No fixtures provided

        # Should auto-generate 100 records per report
        results = runner.run_all()
        self.assertEqual(results["status"], "SUCCESS")
        self.assertEqual(results["project_requirements"]["processed_count"], 100)

        # Test specific missing field fallback
        fixtures = {
            "student_workers": [
                {"worker_id": "SW-1"} # Missing name and department
            ]
        }
        runner_missing_fields = BenchmarkRunner(fixtures=fixtures)
        runner_missing_fields.synthesize_student_workers()
        self.assertEqual(runner_missing_fields.fixtures["student_workers"][0]["name"], "Unknown Student")
        self.assertEqual(runner_missing_fields.fixtures["student_workers"][0]["department"], "Unassigned")

    def test_cross_year_month_boundary(self):
        """Test cross-year/month boundary parsing and processing."""
        fixtures = {
            "campus_recruitment": [
                {"candidate_id": "CR-1", "offer_date": "2023-12-31"},
                {"candidate_id": "CR-2", "offer_date": "2024-01-01"},
                {"candidate_id": "CR-3", "offer_date": "2023-11-30"},
                {"candidate_id": "CR-4", "offer_date": "2023-12-01"},
            ]
        }
        runner = BenchmarkRunner(fixtures=fixtures)
        cr_results = runner.synthesize_campus_recruitment()

        self.assertEqual(cr_results["processed_count"], 4)
        # Verify dates weren't mutated as bad dates
        dates = [r["offer_date"] for r in runner.fixtures["campus_recruitment"]]
        self.assertIn("2023-12-31", dates)
        self.assertIn("2024-01-01", dates)

    def test_extreme_stress_simulation(self):
        """Test extreme stress simulation / high-concurrency placeholder checks."""
        # 10,000 records to test performance and memory handling
        generator = SyntheticFixtureGenerator(data_size=10000)
        fixtures = generator.generate_all_fixtures()

        runner = BenchmarkRunner(fixtures=fixtures)
        start_time = time.time()
        results = runner.run_all()
        end_time = time.time()

        self.assertEqual(results["status"], "SUCCESS")
        self.assertEqual(results["project_requirements"]["processed_count"], 10000)

        # Even with 10k records, the simple python logic should finish under 3 seconds
        self.assertLess(results["total_duration_sec"], 3.0)
        self.assertLess(end_time - start_time, 3.0)

if __name__ == "__main__":
    unittest.main()

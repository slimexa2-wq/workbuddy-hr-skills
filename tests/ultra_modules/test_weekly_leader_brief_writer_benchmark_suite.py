import unittest
import math
from datetime import datetime, timedelta
from ultra_modules.weekly_leader_brief_writer_benchmark_suite import (
    generate_weekly_leader_brief,
    generate_synthetic_fixtures,
    run_benchmark,
    _parse_date,
    _parse_int,
    _clean_department_breakdown
)

class TestWeeklyLeaderBriefWriter(unittest.TestCase):

    def test_normal_operations(self):
        """Test with clean, complete data to ensure proper formatting and calculation."""
        data = {
            "start_date": "2023-10-01",
            "end_date": "2023-10-07",
            "total_employees": 100,
            "new_hires": 5,
            "departures": 2,
            "department_breakdown": [
                {"name": "HR", "total": 10, "hires": 1, "deps": 0}
            ]
        }
        res = generate_weekly_leader_brief(data)

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["metrics"]["net_change"], 3)
        self.assertEqual(res["metrics"]["total_employees"], 100)
        self.assertTrue("HR" in res["report_text"])
        self.assertTrue("新入职 5 人" in res["report_text"])
        self.assertTrue("+3" in res["report_text"])

    def test_dirty_data_self_healing(self):
        """Test with various invalid types, garbage string, and incorrect formats."""
        data = {
            "start_date": "Garbage Date",
            "end_date": 12345,
            "total_employees": "150 人", # Should parse to 150
            "new_hires": "++__10", # Should parse to 10
            "departures": [1, 2], # Should default to 0
            "department_breakdown": [
                "Not a dict",
                {"name": None, "total": "abc", "hires": -5, "deps": float('nan')}
            ]
        }
        res = generate_weekly_leader_brief(data)

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["metrics"]["total_employees"], 150)
        self.assertEqual(res["metrics"]["new_hires"], 10)
        self.assertEqual(res["metrics"]["departures"], 0)
        self.assertEqual(res["metrics"]["net_change"], 10)

        # Check department breakdown
        depts = res["department_breakdown"]
        self.assertEqual(len(depts), 1)
        self.assertEqual(depts[0]["name"], "未知部门")
        self.assertEqual(depts[0]["total"], 0) # "abc" -> 0
        self.assertEqual(depts[0]["hires"], 0) # -5 -> 0
        self.assertEqual(depts[0]["deps"], 0) # NaN -> 0

    def test_missing_parameters_default_fallbacks(self):
        """Test with missing parameters (None or empty dict) to ensure sensible defaults."""
        res1 = generate_weekly_leader_brief(None)
        res2 = generate_weekly_leader_brief({})

        for res in [res1, res2]:
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["metrics"]["new_hires"], 0)
            self.assertEqual(res["metrics"]["departures"], 0)
            self.assertEqual(res["metrics"]["net_change"], 0)
            self.assertEqual(res["metrics"]["total_employees"], 0)

            # Default dates should be a 7-day period ending today
            end_date = datetime.strptime(res["metrics"]["end_date"], "%Y-%m-%d").date()
            start_date = datetime.strptime(res["metrics"]["start_date"], "%Y-%m-%d").date()
            self.assertEqual((end_date - start_date).days, 7)

        # Test with only end_date
        res3 = generate_weekly_leader_brief({"end_date": "2024-01-10"})
        start_date3 = datetime.strptime(res3["metrics"]["start_date"], "%Y-%m-%d").date()
        self.assertEqual(start_date3.strftime("%Y-%m-%d"), "2024-01-03")

        # Test with only start_date
        res4 = generate_weekly_leader_brief({"start_date": "2024-01-03"})
        end_date4 = datetime.strptime(res4["metrics"]["end_date"], "%Y-%m-%d").date()
        self.assertEqual(end_date4.strftime("%Y-%m-%d"), "2024-01-10")

    def test_extreme_boundary_conditions(self):
        """Test with extreme boundaries like inverse dates, negative counts, cross-year, cross-month."""
        # 1. Inverse dates
        res_inv = generate_weekly_leader_brief({
            "start_date": "2024-05-10",
            "end_date": "2024-05-01"
        })
        self.assertEqual(res_inv["metrics"]["start_date"], "2024-05-01")
        self.assertEqual(res_inv["metrics"]["end_date"], "2024-05-10")

        # 2. Negative counts (should floor to 0)
        res_neg = generate_weekly_leader_brief({
            "total_employees": -100,
            "new_hires": -10,
            "departures": -5
        })
        self.assertEqual(res_neg["metrics"]["total_employees"], 0)
        self.assertEqual(res_neg["metrics"]["new_hires"], 0)
        self.assertEqual(res_neg["metrics"]["departures"], 0)

        # 3. Cross-year and cross-month
        res_cross = generate_weekly_leader_brief({
            "start_date": "2023-12-28",
            "end_date": "2024-01-03"
        })
        self.assertEqual(res_cross["metrics"]["start_date"], "2023-12-28")
        self.assertEqual(res_cross["metrics"]["end_date"], "2024-01-03")

    def test_benchmark_and_fixtures(self):
        """Test the synthetic fixtures generation and the benchmark execution itself."""
        # Verify fixtures length
        fixtures = generate_synthetic_fixtures(10)
        self.assertEqual(len(fixtures), 10)

        # Generate enough records to loop over the templates array multiple times
        # and ensure every branch in the generation loop is hit.
        fixtures_10 = generate_synthetic_fixtures(10)
        self.assertEqual(len(fixtures_10), 10)

        # Test with a dict that has total_employees but not as an int to hit branch 231->233
        # Since fixtures[3] has total_employees = float('inf'), that handles it.

        fixtures_empty = generate_synthetic_fixtures(0)
        self.assertEqual(len(fixtures_empty), 0)

        # Verify benchmark output structure and zero crash guarantee
        bench_res = run_benchmark(50)
        self.assertEqual(bench_res["records_processed"], 50)
        self.assertEqual(bench_res["success_count"], 50)
        self.assertEqual(bench_res["failed_count"], 0)
        self.assertTrue(bench_res["is_zero_crash"])
        self.assertTrue(bench_res["total_time_seconds"] >= 0)
        self.assertTrue(bench_res["avg_time_per_record_ms"] >= 0)

        # 0 records test
        bench_res_0 = run_benchmark(0)
        self.assertEqual(bench_res_0["records_processed"], 0)
        self.assertEqual(bench_res_0["success_count"], 0)

        # Force a failure during run_benchmark to trigger the Exception handler
        from unittest.mock import patch
        with patch('ultra_modules.weekly_leader_brief_writer_benchmark_suite.generate_weekly_leader_brief') as mock_gen:
            mock_gen.side_effect = Exception("Crash")
            bench_res_err = run_benchmark(2)
            self.assertEqual(bench_res_err["success_count"], 0)
            self.assertEqual(bench_res_err["failed_count"], 2)

        # Force a failure in generating success logic by returning non-dict
        with patch('ultra_modules.weekly_leader_brief_writer_benchmark_suite.generate_weekly_leader_brief') as mock_gen:
            mock_gen.return_value = None
            bench_res_err = run_benchmark(2)
            self.assertEqual(bench_res_err["success_count"], 0)

    def test_internal_helpers_coverage(self):
        """Specifically target 100% branch coverage on internal helpers."""
        # _parse_date
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date(""))
        self.assertEqual(_parse_date(datetime(2020, 1, 1)), datetime(2020, 1, 1).date())
        class MockDate:
            def date(self):
                return datetime(2021, 1, 1).date()
        self.assertEqual(_parse_date(MockDate()), datetime(2021, 1, 1).date())
        self.assertEqual(_parse_date("2022/12/31"), datetime(2022, 12, 31).date())
        self.assertEqual(_parse_date("31-12-2022"), datetime(2022, 12, 31).date())
        self.assertIsNone(_parse_date("bad-format-string"))

        # _parse_int
        self.assertEqual(_parse_int(None, default=1), 1)
        self.assertEqual(_parse_int(True), 1)
        self.assertEqual(_parse_int(False), 0)
        self.assertEqual(_parse_int(3.14), 3)
        self.assertEqual(_parse_int(float('inf'), default=-1), -1)
        self.assertEqual(_parse_int(float('nan'), default=-1), -1)
        self.assertEqual(_parse_int("abc", default=99), 99)
        self.assertEqual(_parse_int("-", default=55), 55)

        # Force Exception in _parse_int by passing an object that fails string conversion
        class BadStr:
            def __str__(self):
                raise ValueError("cannot convert to string")
        self.assertEqual(_parse_int(BadStr(), default=42), 42)

        # _clean_department_breakdown
        self.assertEqual(_clean_department_breakdown(None), [])
        self.assertEqual(_clean_department_breakdown("not-a-list"), [])
        self.assertEqual(_clean_department_breakdown([{"name": "null"}]), [{"name": "未知部门", "total": 0, "hires": 0, "deps": 0}])

if __name__ == '__main__':
    unittest.main()

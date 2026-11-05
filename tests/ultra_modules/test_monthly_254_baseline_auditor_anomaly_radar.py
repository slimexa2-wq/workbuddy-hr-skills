import unittest
import datetime
from unittest.mock import patch
from ultra_modules.monthly_254_baseline_auditor_anomaly_radar import AnomalyRadarEngine, run_anomaly_radar

class TestMonthly254BaselineAuditorAnomalyRadar(unittest.TestCase):
    def setUp(self):
        self.engine = AnomalyRadarEngine()

    def test_normal_distribution(self):
        """Validating Top 3% HIGHLIGHT and 97% GREEN."""
        # 100 records: 97 with ~10 days, 2 very high, 1 very low. Total 100 -> ceil(3) anomalies
        records = [{"id": f"emp{i}", "employment_days": 10} for i in range(97)]
        records.append({"id": "high1", "employment_days": 100})
        records.append({"id": "high2", "employment_days": 95})
        records.append({"id": "low1", "employment_days": 0})

        result = run_anomaly_radar(records, baseline_target=100)

        self.assertEqual(result["total_processed"], 100)

        top_anomalies = result["top_anomalies"]
        self.assertEqual(len(top_anomalies), 3) # math.ceil(100 * 0.03) = 3

        anomaly_ids = [r["id"] for r in top_anomalies]
        self.assertIn("high1", anomaly_ids)
        self.assertIn("high2", anomaly_ids)

        # Check colors
        for anomaly in top_anomalies:
            if anomaly["id"] in ["high1", "high2"]:
                self.assertEqual(anomaly["status_color"], "RED")
                self.assertIn("异常偏高", anomaly["reason"])
            else:
                self.assertEqual(anomaly["status_color"], "YELLOW")
                self.assertIn("异常偏低", anomaly["reason"])

        # Check normal records
        normal_records = [r for r in result["all_records"] if r["status_color"] == "GREEN"]
        self.assertEqual(len(normal_records), 97)
        for r in normal_records:
            self.assertEqual(r["reason"], "正常")

    def test_dirty_data_self_healing(self):
        """Verifying fallback defaults for missing ID, wrong types, missing fields."""
        # Fix the date used by datetime.datetime.now() to ensure hire_date calculation works deterministically
        class MockDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.datetime(2023, 10, 20)

        with patch('ultra_modules.monthly_254_baseline_auditor_anomaly_radar.datetime.datetime', MockDatetime):
            records = [
                {"id": "emp1", "employment_days": "invalid_string"}, # Should default to 0.0
                {"id": "emp2", "hire_date": "2023-10-10"}, # Should calculate to 10 days
                {"id": "emp3", "hire_date": "invalid_date_format"}, # Should default to 0.0
                {"id": "emp4", "employment_days": None}, # Should default to 0.0
                {"id": "emp5"}, # Missing both hire_date and employment_days, default to 0.0
                {"employment_days": 15}, # Missing ID, should auto-generate
            ]

            result = run_anomaly_radar(records, baseline_target=5)

            self.assertEqual(result["total_processed"], 6)
            self.assertEqual(result["valid_unique"], 6)

            # Find emp2
            emp2 = next(r for r in result["all_records"] if r["id"] == "emp2")
            self.assertEqual(emp2["employment_days"], 10.0)

            # Find emp1
            emp1 = next(r for r in result["all_records"] if r["id"] == "emp1")
            self.assertEqual(emp1["employment_days"], 0.0)

            # Verify 7-day calculation
            # emp2 and the one with missing ID (15 days) should qualify
            self.assertEqual(result["qualified_7_days"], 2)

    def test_missing_param_fallback(self):
        """Validating `None` fallback to empty list handling."""
        result = run_anomaly_radar(None)

        self.assertEqual(result["total_processed"], 0)
        self.assertEqual(result["valid_unique"], 0)
        self.assertEqual(result["qualified_7_days"], 0)
        self.assertFalse(result["is_target_met"])
        self.assertEqual(result["baseline_achievement_rate"], 0.0)
        self.assertEqual(len(result["top_anomalies"]), 0)
        self.assertEqual(len(result["all_records"]), 0)

    def test_extreme_boundaries(self):
        """Handling 0-variance records safely without Division-by-Zero errors."""
        # 10 records all with exactly 10 employment days, std_dev = 0
        records = [{"id": f"emp{i}", "employment_days": 10} for i in range(10)]
        result = run_anomaly_radar(records, baseline_target=10)

        self.assertEqual(result["total_processed"], 10)
        self.assertEqual(result["qualified_7_days"], 10)

        # All anomalies score should be 0, no division by zero error
        for r in result["all_records"]:
            self.assertEqual(r["_anomaly_score"], 0.0)

        # Top 3% of 10 is ceil(0.3) = 1.
        # Since all have 0 z-score, the first one gets YELLOW (not > 0)
        top_anomalies = result["top_anomalies"]
        self.assertEqual(len(top_anomalies), 1)
        self.assertEqual(top_anomalies[0]["status_color"], "YELLOW")

    def test_small_dataset_anomaly(self):
        """Checking Top 3% ceiling math when under 33 records."""
        # 10 records. 3% is 0.3. math.ceil(0.3) = 1.
        # Ensure exactly 1 is flagged.
        records = [{"id": f"emp{i}", "employment_days": i} for i in range(10)]
        result = run_anomaly_radar(records, baseline_target=5)

        top_anomalies = result["top_anomalies"]
        self.assertEqual(len(top_anomalies), 1)

        # 0 to 9. mean = 4.5. max anomaly is 0 (score 4.5) or 9 (score 4.5).
        # sort will pick one of them.
        self.assertIn(top_anomalies[0]["id"], ["emp0", "emp9"])

if __name__ == '__main__':
    unittest.main()

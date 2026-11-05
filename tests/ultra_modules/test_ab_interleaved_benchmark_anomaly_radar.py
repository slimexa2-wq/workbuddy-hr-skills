import unittest
import math
from ultra_modules.ab_interleaved_benchmark_anomaly_radar import ABInterleavedBenchmarkAnomalyRadar

class TestABInterleavedBenchmarkAnomalyRadar(unittest.TestCase):
    def setUp(self):
        self.radar = ABInterleavedBenchmarkAnomalyRadar()

    def test_normal_data_no_anomalies(self):
        # 100 items around normal range
        data = [10.0 for _ in range(100)]
        result = self.radar.analyze(data)
        self.assertEqual(result["status"], "Green")
        self.assertEqual(len(result["anomalies"]), 0)

    def test_missing_data_default_fallback(self):
        result = self.radar.analyze(None)
        self.assertEqual(result["status"], "Green")
        self.assertEqual(len(result["anomalies"]), 0)
        self.assertEqual(result["summary"], "No valid data provided. Everything looks fine by default.")

    def test_empty_list_default_fallback(self):
        result = self.radar.analyze([])
        self.assertEqual(result["status"], "Green")
        self.assertEqual(len(result["anomalies"]), 0)

    def test_insufficient_data(self):
        result = self.radar.analyze([100])
        self.assertEqual(result["status"], "Green")
        self.assertEqual(len(result["anomalies"]), 0)

    def test_dirty_data_self_healing(self):
        # Mixed types, strings, Nones, NaNs, Infs
        dirty_data = [10, "20", "invalid", None, float('nan'), float('inf'), -float('inf'), 15.5]
        result = self.radar.analyze(dirty_data)
        self.assertEqual(result["status"], "Green")
        self.assertEqual(len(result["anomalies"]), 0)

    def test_data_from_dict_and_single_value(self):
        result_dict = self.radar.analyze({"metrics": [10, 20, 30]})
        self.assertEqual(result_dict["status"], "Green")

        result_single = self.radar.analyze(42)
        self.assertEqual(result_single["status"], "Green")

        result_invalid_dict = self.radar.analyze({"unknown": [1, 2, 3]})
        self.assertEqual(result_invalid_dict["status"], "Green")

        result_unrecognized_type = self.radar.analyze(set([1, 2, 3]))
        self.assertEqual(result_unrecognized_type["status"], "Green")

    def test_top_3_percent_anomalies_red(self):
        # 97 normal items, 3 clear anomalies
        data = [10.0 + (i % 5) for i in range(97)]
        # Top 3% anomalies that are also outliers
        anomalies = [100.0, 105.0, 110.0]
        data.extend(anomalies)

        result = self.radar.analyze(data)
        self.assertEqual(result["status"], "Red")
        self.assertEqual(len(result["anomalies"]), 3)
        self.assertEqual(result["anomalies"][0]["value"], 110.0)

    def test_top_3_percent_anomalies_yellow(self):
        # 1 anomaly in 100 items (1%)
        data = [10.0 + (i % 5) for i in range(99)]
        data.append(100.0)

        result = self.radar.analyze(data)
        self.assertEqual(result["status"], "Yellow")
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["anomalies"][0]["value"], 100.0)

    def test_zero_iqr_extreme_boundary(self):
        # All items identical except for top ones
        data = [50.0 for _ in range(98)]
        data.extend([200.0, 300.0])

        result = self.radar.analyze(data)
        # Should flag anomalies, and handle IQR=0 division in reason formatting
        self.assertEqual(result["status"], "Red")
        self.assertEqual(len(result["anomalies"]), 2)
        self.assertTrue("显著高于常规水平" in result["anomalies"][0]["reason"])

    def test_percentile_boundary_conditions(self):
        # Test extreme percentiles boundary in the helper function directly to ensure 100% branch coverage
        # _percentile returns 0.0 if empty list
        self.assertEqual(self.radar._percentile([], 50), 0.0)

        # Test percentile logic for bounds
        sorted_data = [1.0, 2.0, 3.0]
        self.assertEqual(self.radar._percentile(sorted_data, 100), 3.0)

        # Test _clean_data returning empty for invalid type
        self.assertEqual(self.radar._clean_data(self.radar), [])

if __name__ == '__main__':
    unittest.main()

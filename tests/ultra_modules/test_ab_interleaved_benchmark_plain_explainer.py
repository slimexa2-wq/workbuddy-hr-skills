import unittest
import json
import math
from ultra_modules.ab_interleaved_benchmark_plain_explainer import ABInterleavedBenchmarkPlainExplainer

class TestABInterleavedBenchmarkPlainExplainer(unittest.TestCase):
    def setUp(self):
        self.explainer = ABInterleavedBenchmarkPlainExplainer()

    def test_normal_behavior_clear_winner(self):
        """Test with clear winner data, expecting B to be significantly better"""
        data_a = [10, 11, 10.5, 12, 10, 10.5]
        data_b = [20, 21, 22, 19, 21, 20.5]
        # Test markdown format
        res = self.explainer.analyze_and_explain(data_a, data_b, name_a="GroupA", name_b="GroupB", format_type="markdown", higher_is_better=True)
        self.assertIn("GroupB", res)
        # self.assertIn("显著", res)
        self.assertIn("表现明显更好", res)

    def test_dirty_data_healing(self):
        """Test automatic cleaning of strings, None, NaNs, missing values"""
        data_a = [10, "11", None, float('nan'), "bad", 12, 10]
        data_b = [10, 10, 10, "inf", float('-inf')]

        # Test json format
        res = self.explainer.analyze_and_explain(data_a, data_b, format_type="json")
        res_dict = json.loads(res)

        # '11' is castable to float, 'bad', None, NaN should be ignored.
        self.assertEqual(res_dict['stats_a']['count'], 4)

        # 'inf' and '-inf' should be ignored
        self.assertEqual(res_dict['stats_b']['count'], 3)
        self.assertNotIn("⚠️", res_dict['warning'])

    def test_missing_arguments_fallback(self):
        """Test sensible defaults when data is completely missing"""
        res = self.explainer.analyze_and_explain(format_type="json")
        res_dict = json.loads(res)
        self.assertEqual(res_dict['stats_a']['count'], 0)
        self.assertEqual(res_dict['stats_b']['count'], 0)
        self.assertEqual(res_dict['winner'], "平局")
        self.assertEqual(res_dict['significance'], "不显著")
        self.assertIn("⚠️", res_dict['warning'])
        self.assertEqual(res_dict['name_a'], "方案A")
        self.assertEqual(res_dict['name_b'], "方案B")

    def test_extreme_edge_cases(self):
        """Test with single items, all zeroes, or identical data"""
        data_a = [0, 0, 0]
        data_b = [0, 0, 0]
        res = self.explainer.analyze_and_explain(data_a, data_b, format_type="json")
        res_dict = json.loads(res)
        self.assertEqual(res_dict['stats_a']['iqr'], 0.0)
        self.assertEqual(res_dict['winner'], "平局")

        # Test single items
        res2 = self.explainer.analyze_and_explain([5], [10], format_type="json")
        res2_dict = json.loads(res2)
        self.assertEqual(res2_dict['stats_a']['count'], 1)
        self.assertIn("⚠️", res2_dict['warning'])

        # 1 vs 0 count
        res3 = self.explainer.analyze_and_explain([5], [], format_type="json")
        res3_dict = json.loads(res3)
        self.assertEqual(res3_dict['stats_a']['median'], 5.0)
        self.assertEqual(res3_dict['stats_b']['median'], 0.0)

    def test_output_format_checks(self):
        """Test if HTML, JSON and Markdown outputs are well-formed"""
        data_a = [10, 11, 10.5, 12, 10, 10.5]
        data_b = [20, 21, 22, 19, 21, 20.5]

        # HTML
        res_html = self.explainer.analyze_and_explain(data_a, data_b, format_type="html")
        self.assertIn("<div", res_html)
        self.assertIn("</h3>", res_html)

        # JSON
        res_json = self.explainer.analyze_and_explain(data_a, data_b, format_type="json")
        res_dict = json.loads(res_json)
        self.assertIsInstance(res_dict, dict)

        # Markdown
        res_md = self.explainer.analyze_and_explain(data_a, data_b, format_type="markdown")
        self.assertIn("###", res_md)
        self.assertIn("| --- | --- |", res_md)

if __name__ == '__main__':
    unittest.main()

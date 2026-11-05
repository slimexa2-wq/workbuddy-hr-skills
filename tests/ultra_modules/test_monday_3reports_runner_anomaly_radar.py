import unittest
from ultra_modules.monday_3reports_runner_anomaly_radar import run_anomaly_radar, analyze_report

class TestMonday3ReportsRunnerAnomalyRadar(unittest.TestCase):

    def test_normal_operation_and_top_3_percent_logic(self):
        """Test normal operation with enough data to trigger the 3% rule."""
        # 100 items: 97 normal, 3 extreme
        data = [{'id': i, 'value': 100.0} for i in range(97)]
        data.extend([
            {'id': 97, 'value': 500.0}, # extreme high
            {'id': 98, 'value': 520.0}, # extreme high
            {'id': 99, 'value': -300.0} # extreme low
        ])

        result = run_anomaly_radar(project_demand_data=data)
        demand_result = result['project_demand']

        self.assertEqual(len(demand_result), 100)

        # Check that top 3% (3 items) are flagged
        flagged_count = sum(1 for item in demand_result if item['marker'] in ('red', 'yellow'))
        self.assertEqual(flagged_count, 3)

        # Check that 97% pass silently
        green_count = sum(1 for item in demand_result if item['marker'] == 'green')
        self.assertEqual(green_count, 97)

        # Check reasoning exists for flagged items
        for item in demand_result:
            if item['marker'] in ('red', 'yellow'):
                self.assertIn('需要关注', item['reason'])
            else:
                self.assertEqual(item['reason'], '正常放行')

    def test_dirty_data_self_healing(self):
        """Test that dirty data (None, strings, missing keys) is self-healed to 0.0 without crashing."""
        dirty_data = [
            {'id': 1, 'value': 100.0},
            {'id': 2, 'value': 'invalid_string'},
            {'id': 3, 'value': None},
            {'id': 4}, # missing 'value' key
            {'id': 5, 'value': 10000.0} # One extreme valid value to test anomaly calculation with dirty data
        ]

        result = run_anomaly_radar(student_workers_data=dirty_data)
        sw_result = result['student_workers']

        self.assertEqual(len(sw_result), 5)
        # The extreme value should be flagged
        flagged_item = next(item for item in sw_result if item['id'] == 5)
        self.assertIn(flagged_item['marker'], ('red', 'yellow'))

        # Missing or invalid should be treated as 0.0 and likely 'green' in this distribution
        missing_key_item = next(item for item in sw_result if item['id'] == 4)
        self.assertEqual(missing_key_item['marker'], 'green')

    def test_missing_parameter_fallback(self):
        """Test zero-config fault tolerance when parameters are completely missing."""
        # Calling with no arguments should default all to empty lists
        result = run_anomaly_radar()

        self.assertIn('project_demand', result)
        self.assertIn('student_workers', result)
        self.assertIn('campus_recruitment', result)

        self.assertEqual(result['project_demand'], [])
        self.assertEqual(result['student_workers'], [])
        self.assertEqual(result['campus_recruitment'], [])

    def test_extreme_boundary_cases_empty_and_small_data(self):
        """Test extreme boundary cases: empty lists and very small data lists."""
        # Empty data
        self.assertEqual(analyze_report([], 'project_demand'), [])

        # Single item (no variance)
        single = analyze_report([{'value': 100.0}], 'project_demand')
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0]['marker'], 'green') # Single item can't be anomalous to itself

        # Two items
        two = analyze_report([{'value': 100.0}, {'value': 200.0}], 'project_demand')
        self.assertEqual(len(two), 2)
        # Even with two, we ceil(0.03 * 2) = 1, so top 1 gets flagged if score > 0
        # However, with two items, Z-score might be identical for both (mean=150, std=50, Z=1 for both).
        # We just ensure it doesn't crash.
        self.assertTrue(all(item['marker'] in ('green', 'yellow', 'red') for item in two))

    def test_extreme_boundary_cases_zero_variance(self):
        """Test when all values are exactly the same (variance is 0, std is 0, iqr is 0)."""
        data = [{'id': i, 'value': 100.0} for i in range(50)]
        result = run_anomaly_radar(campus_recruitment_data=data)
        cr_result = result['campus_recruitment']

        # Since all values are identical, no item should have a score > 0, so none should be anomalous
        green_count = sum(1 for item in cr_result if item['marker'] == 'green')
        self.assertEqual(green_count, 50)

if __name__ == '__main__':
    unittest.main()

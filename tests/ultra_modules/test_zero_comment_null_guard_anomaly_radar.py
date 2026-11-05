import unittest
import math
from ultra_modules.zero_comment_null_guard_anomaly_radar import ZeroCommentNullGuardAnomalyRadar, _to_float

class TestZeroCommentNullGuardAnomalyRadar(unittest.TestCase):

    def test_normal_data_processing(self):
        """Test case 1: Normal data processing (Green markers assigned)"""
        data = [
            {'id': 1, 'salary': 5000, 'age': 30, 'comments': 5},
            {'id': 2, 'salary': 5200, 'age': 32, 'comments': 1},
            {'id': 3, 'salary': 5100, 'age': 31, 'comments': 0},
            {'id': 4, 'salary': 4900, 'age': 29, 'comments': 2},
            {'id': 5, 'salary': 5050, 'age': 30, 'comments': 3}
        ]
        result = ZeroCommentNullGuardAnomalyRadar.scan(data, numeric_columns=['salary', 'age'])

        self.assertEqual(len(result), 5)
        for item in result:
            self.assertEqual(item['comments'], 0) # Comments should be forced to 0
            self.assertEqual(item['marker'], 'Green') # Should all be green
            self.assertEqual(item['anomaly_reason'], '') # No anomaly reasons

    def test_dirty_data_self_healing(self):
        """Test case 2: Dirty data self-healing"""
        data = [
            {'id': 1, 'salary': '5000', 'age': '30'}, # String numbers
            {'id': 2, 'salary': None, 'age': ''}, # None and empty string
            {'id': 3, 'salary': math.nan, 'age': float('inf')}, # NaN and Inf
            {'id': 4, 'salary': 'invalid', 'age': []}, # Invalid types
        ]
        result = ZeroCommentNullGuardAnomalyRadar.scan(data, numeric_columns=['salary', 'age'])

        # Check if they were converted properly
        salaries = [item['salary'] for item in result]
        ages = [item['age'] for item in result]

        self.assertEqual(salaries, [5000.0, 0.0, 0.0, 0.0])
        self.assertEqual(ages, [30.0, 0.0, 0.0, 0.0])

        for item in result:
            self.assertEqual(item['comments'], 0)

    def test_missing_parameter_fallbacks(self):
        """Test case 3: Missing parameter fallbacks"""
        # Test with completely missing data
        result1 = ZeroCommentNullGuardAnomalyRadar.scan()
        self.assertEqual(result1, [])

        # Test with None numeric_columns (should auto-detect)
        data = [{'id': 1, 'score': 100}, {'id': 2, 'score': 90}]
        result2 = ZeroCommentNullGuardAnomalyRadar.scan(data)

        self.assertEqual(len(result2), 2)
        self.assertIn('score', result2[0])
        self.assertEqual(result2[0]['comments'], 0)

    def test_top_3_percent_anomaly_flagging(self):
        """Test case 4: Top 3% anomaly flagging"""
        # Generate 100 items to test percentages easily
        data = [{'id': i, 'value': 100 + (i % 10)} for i in range(100)]

        # Add obvious anomalies
        data[0]['value'] = 1000000  # Extreme anomaly
        data[1]['value'] = 5000     # Significant anomaly
        data[2]['value'] = 2000     # Mild anomaly

        result = ZeroCommentNullGuardAnomalyRadar.scan(data, numeric_columns=['value'])

        # Find markers
        reds = [item for item in result if item['marker'] == 'Red']
        yellows = [item for item in result if item['marker'] == 'Yellow']
        greens = [item for item in result if item['marker'] == 'Green']

        self.assertGreater(len(reds), 0, "Should have at least one Red anomaly")
        self.assertTrue(any('严重异常' in r['anomaly_reason'] for r in reds))

        # Total anomalies should be max 3% -> 3 items
        self.assertLessEqual(len(reds) + len(yellows), 3)
        self.assertGreaterEqual(len(greens), 97)

    def test_extreme_boundaries(self):
        """Test case 5: Extreme boundaries"""
        # 1 element dataset
        data = [{'id': 1, 'val': 10}]
        result = ZeroCommentNullGuardAnomalyRadar.scan(data, numeric_columns=['val'])
        self.assertEqual(result[0]['marker'], 'Green')

        # 2 elements identical
        data2 = [{'id': 1, 'val': 10}, {'id': 2, 'val': 10}]
        result2 = ZeroCommentNullGuardAnomalyRadar.scan(data2, numeric_columns=['val'])
        for item in result2:
            self.assertEqual(item['marker'], 'Green')

        # 0 elements (empty list)
        result3 = ZeroCommentNullGuardAnomalyRadar.scan([], numeric_columns=['val'])
        self.assertEqual(result3, [])

if __name__ == '__main__':
    unittest.main()

import unittest
from ultra_modules.xlsx_formula_healer_anomaly_radar import scan_and_heal_report, _clean_value

class TestXlsxFormulaHealerAnomalyRadar(unittest.TestCase):
    def test_normal_values_distribution(self):
        """Test with normal values to ensure most are marked green."""
        # Create 100 normal values and 1 outlier
        data = [{'val': i} for i in range(1, 101)]
        data.append({'val': 10000}) # outlier

        result = scan_and_heal_report(data, column='val', threshold_percent=0.03)

        self.assertEqual(len(result), 101)

        reds = [r for r in result if r['status_color'] == 'Red']
        greens = [r for r in result if r['status_color'] == 'Green']

        self.assertGreaterEqual(len(reds), 1)
        self.assertGreater(len(greens), 90)

        # Check the outlier is marked Red
        outlier = next(r for r in result if (r['original'] == 10000 if 'original' in r else r['val'] == 10000))
        self.assertEqual(outlier['status_color'], 'Red')
        self.assertIn('异常偏高', outlier['status_reason'])

    def test_dirty_data_self_healing(self):
        """Test healing of #REF!, #DIV/0!, circular reference and text numbers."""
        dirty_data = [
            {'val': '#REF!'},
            {'val': '#DIV/0!'},
            {'val': 'circular reference'},
            {'val': '  42.5  '}, # text number with spaces
            {'val': 'invalid_text'},
            {'val': None}
        ]

        result = scan_and_heal_report(dirty_data, column='val')

        self.assertEqual(len(result), 6)

        # #REF! -> 0.0
        self.assertEqual(result[0]['cleaned_value'], 0.0)
        # #DIV/0! -> 0.0
        self.assertEqual(result[1]['cleaned_value'], 0.0)
        # circular reference -> 0.0
        self.assertEqual(result[2]['cleaned_value'], 0.0)
        # '  42.5  ' -> 42.5
        self.assertEqual(result[3]['cleaned_value'], 42.5)
        # 'invalid_text' -> 0.0
        self.assertEqual(result[4]['cleaned_value'], 0.0)
        # None -> 0.0
        self.assertEqual(result[5]['cleaned_value'], 0.0)

    def test_missing_parameter_fallback(self):
        """Test fallback when parameters are missing or default."""
        # Flat list instead of list of dicts
        data = [10, 20, 30, 40, 50, 1000]

        # Omit column parameter
        result = scan_and_heal_report(data)

        self.assertEqual(len(result), 6)
        self.assertEqual(result[0]['cleaned_value'], 10.0)
        self.assertEqual(result[5]['cleaned_value'], 1000.0)
        self.assertEqual(result[5]['status_color'], 'Red')

    def test_boundary_outliers(self):
        """Test extreme outliers using default 3% threshold."""
        # 100 items: 97 zeroes, 3 extreme values
        data = [0] * 97 + [1000, 2000, 3000]

        result = scan_and_heal_report(data)

        non_greens = [r for r in result if r['status_color'] in ('Red', 'Yellow')]
        # The top 3 items (3% of 100) should be marked (Red or Yellow)
        self.assertEqual(len(non_greens), 3)

    def test_small_dataset_fallback(self):
        """Test dataset too small for meaningful statistics."""
        data = [{'val': 10}, {'val': 1000}]
        result = scan_and_heal_report(data, column='val')

        # Should default to all green when n < 4
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['status_color'], 'Green')
        self.assertEqual(result[1]['status_color'], 'Green')
        self.assertEqual(result[0]['status_reason'], '数据量过少，默认正常')

    def test_clean_value_helper(self):
        """Unit test the _clean_value helper explicitly."""
        self.assertEqual(_clean_value('#ref!'), 0.0)
        self.assertEqual(_clean_value('#div/0!'), 0.0)
        self.assertEqual(_clean_value('#VALUE!'), 0.0)
        self.assertEqual(_clean_value(' Circular Reference '), 0.0)
        self.assertEqual(_clean_value(123), 123.0)
        self.assertEqual(_clean_value('456.78'), 456.78)
        self.assertEqual(_clean_value(None), 0.0)
        self.assertEqual(_clean_value('random string'), 0.0)

if __name__ == '__main__':
    unittest.main()

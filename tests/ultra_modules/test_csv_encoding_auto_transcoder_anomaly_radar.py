import unittest
import csv
import io
from ultra_modules.csv_encoding_auto_transcoder_anomaly_radar import process_payroll_csv, CSVTranscoderAnomalyRadar

class TestCSVTranscoderAnomalyRadar(unittest.TestCase):

    def test_normal_usage_utf8(self):
        """Test processing a normal UTF-8 CSV with some salary data."""
        csv_data = "姓名,基本工资,绩效工资\n张三,5000,2000\n李四,5500,2100\n王五,4800,1900\n赵六,5200,2050\n钱七,50000,5000\n"
        results = process_payroll_csv(csv_data.encode('utf-8'))
        self.assertEqual(len(results), 5)
        # Qian Qi should be marked as an anomaly due to extreme value
        anomaly_count = sum(1 for r in results if '异常' in r['status'])
        self.assertGreater(anomaly_count, 0)
        self.assertTrue(any('钱七' in r['original_data']['姓名'] and '异常' in r['status'] for r in results))

    def test_dirty_data_self_healing_gbk(self):
        """Test fallback decoding for GB18030 and silent cleaning of numeric fields (commas, currency symbols)."""
        # GB18030 encoded data with dirty numbers
        csv_data = '姓名,实发工资\n张三,"¥5,000.00"\n李四,"$5,500"\n王五, 4800 \n赵六,5200\n异常人,"999,999"\n'
        results = process_payroll_csv(csv_data.encode('gb18030'))
        self.assertEqual(len(results), 5)

        # Check if 999,999 was flagged as an anomaly
        anomaly = next((r for r in results if r['original_data']['姓名'] == '异常人'), None)
        self.assertIsNotNone(anomaly)
        self.assertIn('异常', anomaly['status'])
        self.assertIn('畸高', anomaly['anomaly_reason'])

    def test_missing_parameter_fallbacks(self):
        """Test default values for missing parameters (empty bytes)."""
        # Calling with no arguments should use default b'' and return empty list without crashing
        results = process_payroll_csv()
        self.assertEqual(results, [])

        # Calling with None should also be handled or type-enforced (though bytes is expected)
        # We test empty byte string
        results = process_payroll_csv(b'')
        self.assertEqual(results, [])

    def test_boundary_conditions_all_same_values(self):
        """Test when all numeric values are the same (IQR is 0)."""
        csv_data = "Name,Salary\nA,5000\nB,5000\nC,5000\nD,5000\nE,5000\n"
        results = process_payroll_csv(csv_data.encode('utf-8'))
        self.assertEqual(len(results), 5)
        # No anomalies should be found if all are the same
        for r in results:
            self.assertEqual(r['status'], '🟢正常')

    def test_boundary_conditions_extreme_small_dataset(self):
        """Test with very small dataset (< 3 rows) where IQR shouldn't be calculated."""
        csv_data = "Name,Salary\nA,5000\nB,999999\n"
        results = process_payroll_csv(csv_data.encode('utf-8'))
        self.assertEqual(len(results), 2)
        # Because we need at least 3 points for meaningful IQR in our logic, it skips anomaly detection
        for r in results:
            self.assertEqual(r['status'], '🟢正常')

    def test_bom_header_handling(self):
        """Test UTF-8-SIG (BOM) header handling."""
        csv_data = "\ufeff姓名,工资\nA,5000\nB,5200\nC,4900\nD,200000\n"
        results = process_payroll_csv(csv_data.encode('utf-8-sig'))
        self.assertEqual(len(results), 4)
        # The key should be '姓名', not '\ufeff姓名'
        for r in results:
            self.assertIn('姓名', r['original_data'])
            self.assertNotIn('\ufeff姓名', r['original_data'])

        anomaly = next(r for r in results if r['original_data']['姓名'] == 'D')
        self.assertIn('异常', anomaly['status'])

if __name__ == '__main__':
    unittest.main()

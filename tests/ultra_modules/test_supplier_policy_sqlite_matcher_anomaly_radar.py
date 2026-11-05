import unittest
import math
from ultra_modules.supplier_policy_sqlite_matcher_anomaly_radar import SupplierPolicyAnomalyRadar

class TestSupplierPolicyAnomalyRadar(unittest.TestCase):
    def setUp(self):
        self.radar = SupplierPolicyAnomalyRadar()
        # Define some basic policies for testing
        self.policies = [
            {
                'job_role': 'Frontend',
                'tier': 1,
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'standard_price': 100.0
            },
            {
                'job_role': 'Backend',
                'tier': 2,
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'standard_price': 150.0
            }
        ]
        self.radar.load_policies(self.policies)

    def tearDown(self):
        self.radar.close()

    def test_normal_execution(self):
        """Test with perfectly matching records. All should be green."""
        records = [
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 100.0},
            {'job_role': 'Backend', 'tier': 2, 'date': '2023-06-01', 'unit_price': 150.0},
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 100.5},
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 99.5},
        ]
        result = self.radar.process_records(records)

        self.assertEqual(len(result), 4)
        for r in result:
            self.assertEqual(r['status'], 'green')
            self.assertNotIn('reason', r)

    def test_anomaly_detection_top_3(self):
        """Test with 40 records, 1 extreme anomaly. Ensure the anomaly is red."""
        records = []
        # 39 normal records
        for i in range(39):
            records.append({'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 100.0 + (i * 0.1)})

        # 1 extreme anomaly
        records.append({'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 500.0}) # Deviation: 400

        result = self.radar.process_records(records)
        self.assertEqual(len(result), 40)

        red_count = 0
        green_count = 0
        for r in result:
            if r['unit_price'] == 500.0:
                self.assertEqual(r['status'], 'red')
                self.assertIn('严重偏离', r['reason'])
                red_count += 1
            else:
                self.assertEqual(r['status'], 'green')
                green_count += 1

        self.assertEqual(red_count, 1)
        self.assertEqual(green_count, 39)

    def test_dirty_data_self_healing(self):
        """Test with dirty unit_price data (strings, null, dicts). Should not crash and handle silently."""
        records = [
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 'invalid'},
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': None},
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': {}},
        ]

        result = self.radar.process_records(records)
        self.assertEqual(len(result), 3)
        # Unit price will default to 0.0, deviation will be 100.0, but all will be the same deviation, so no top 3% anomalies will be flagged as red/yellow
        for r in result:
            self.assertEqual(r['status'], 'green')

    def test_missing_parameter_fallback(self):
        """Test with missing job_role, tier, date. Should use reasonable defaults silently."""
        records = [
            {'unit_price': 100.0},
            {'job_role': None, 'tier': 'wrong', 'date': None, 'unit_price': 100.0}
        ]

        # Load a policy that matches the defaults ('通用工种', tier 1, open dates)
        self.radar.load_policies([{
            'job_role': '通用工种',
            'tier': 1,
            'start_date': '1970-01-01',
            'end_date': '2099-12-31',
            'standard_price': 100.0
        }])

        result = self.radar.process_records(records)
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r['status'], 'green')

    def test_extreme_boundary_cases(self):
        """Test with n=0, n=1, and all identical values."""
        # n = 0
        self.assertEqual(self.radar.process_records([]), [])

        # n = 1
        result1 = self.radar.process_records([
            {'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 500.0}
        ])
        self.assertEqual(len(result1), 1)
        self.assertEqual(result1[0]['status'], 'green') # n=1 cannot have standard deviation, so green

        # All identical values
        records = [{'job_role': 'Frontend', 'tier': 1, 'date': '2023-06-01', 'unit_price': 200.0} for _ in range(50)]
        result_identical = self.radar.process_records(records)
        self.assertEqual(len(result_identical), 50)
        for r in result_identical:
            self.assertEqual(r['status'], 'green')

if __name__ == '__main__':
    unittest.main()

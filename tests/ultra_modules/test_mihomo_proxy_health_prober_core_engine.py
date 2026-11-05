import unittest
import math
from ultra_modules.mihomo_proxy_health_prober_core_engine import (
    clean_latency,
    select_best_connection,
    calculate_average_latency,
    process_and_select
)

class TestMihomoProxyHealthProberCoreEngine(unittest.TestCase):

    def test_clean_latency(self):
        # Normal
        self.assertEqual(clean_latency(100.5), 100.5)
        self.assertEqual(clean_latency("200"), 200.0)
        self.assertEqual(clean_latency(0), 0.0)

        # Missing/None
        self.assertEqual(clean_latency(None), float('inf'))

        # Dirty/Invalid data
        self.assertEqual(clean_latency(-10), float('inf'))
        self.assertEqual(clean_latency("abc"), float('inf'))
        self.assertEqual(clean_latency([]), float('inf'))
        self.assertEqual(clean_latency(math.nan), float('inf'))

    def test_select_best_connection(self):
        # 1. Normal flow: Direct is faster, well within tolerance
        self.assertEqual(select_best_connection(100, 200, 300), 'direct')

        # 2. Normal flow: Proxy 7890 is faster, but Direct is within tolerance (150 <= 100 + 50)
        self.assertEqual(select_best_connection(150, 100, 300), 'direct')

        # 3. Normal flow: Proxy 7890 is much faster, Direct is outside tolerance (151 > 100 + 50)
        self.assertEqual(select_best_connection(151, 100, 300), 'proxy_7890')

        # 4. Normal flow: Proxy 26801 is the best and Direct outside tolerance
        self.assertEqual(select_best_connection(200, 300, 50, tolerance=20), 'proxy_26801')

        # 5. Missing params / Dirty data: Falls back appropriately
        self.assertEqual(select_best_connection(None, None, None), 'direct') # All unreachable
        self.assertEqual(select_best_connection("dirty", 100, 200), 'proxy_7890') # Direct unreachable
        self.assertEqual(select_best_connection(100, "dirty", -50), 'direct') # Proxies unreachable

        # 6. Dirty tolerance: falls back to 50.0
        self.assertEqual(select_best_connection(151, 100, 300, tolerance="invalid"), 'proxy_7890')
        self.assertEqual(select_best_connection(150, 100, 300, tolerance="invalid"), 'direct')

    def test_calculate_average_latency(self):
        # Normal
        self.assertEqual(calculate_average_latency([10, 20, 30]), 20.0)

        # With dirty data (ignores invalid)
        self.assertEqual(calculate_average_latency([10, "dirty", 30, None, -5]), 20.0)

        # All dirty or empty
        self.assertEqual(calculate_average_latency([]), float('inf'))
        self.assertEqual(calculate_average_latency(["dirty", None]), float('inf'))

        # Invalid input type
        self.assertEqual(calculate_average_latency(None), float('inf'))
        self.assertEqual(calculate_average_latency("not_a_list"), float('inf'))

    def test_process_and_select(self):
        # 1. Normal flow
        data1 = {
            'direct': [100, 100], # avg 100
            'proxy_7890': [200, 200], # avg 200
            'proxy_26801': [300, 300], # avg 300
            'tolerance': 50
        }
        self.assertEqual(process_and_select(data1), 'direct')

        # 2. Proxy is much faster
        data2 = {
            'direct': [200, 200], # avg 200
            'proxy_7890': [100, 100], # avg 100
            'proxy_26801': [300, 300], # avg 300
            'tolerance': 50
        }
        self.assertEqual(process_and_select(data2), 'proxy_7890')

        # 3. Missing params / None input
        self.assertEqual(process_and_select(None), 'direct')
        self.assertEqual(process_and_select({}), 'direct')

        # 4. Partial data with dirty entries
        data3 = {
            'direct': ["invalid", -10], # unreachable -> inf
            'proxy_26801': [100, 150, "dirty"] # avg 125
            # proxy_7890 missing
        }
        self.assertEqual(process_and_select(data3), 'proxy_26801')

        # 5. Tolerance fallback
        data4 = {
            'direct': [150],
            'proxy_7890': [100],
            'tolerance': "dirty" # Falls back to 50 -> 150 <= 100 + 50 -> direct
        }
        self.assertEqual(process_and_select(data4), 'direct')

        # 6. Proxy 26801 wins
        data5 = {
            'direct': [200],
            'proxy_7890': [150],
            'proxy_26801': [100],
            'tolerance': 20 # 200 > 100 + 20
        }
        self.assertEqual(process_and_select(data5), 'proxy_26801')

if __name__ == '__main__':
    unittest.main()

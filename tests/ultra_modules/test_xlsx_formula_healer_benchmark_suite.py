import unittest
import time
from ultra_modules.xlsx_formula_healer_benchmark_suite import XlsxFormulaHealer, SyntheticFixtures, BenchmarkSuite

class TestXlsxFormulaHealerBenchmarkSuite(unittest.TestCase):

    def setUp(self):
        self.healer = XlsxFormulaHealer(fallback_value=0.0)

    def test_normal_data_healing(self):
        """Test #1: Normal data processing."""
        # Valid numbers should be returned as float
        self.assertEqual(self.healer.heal_value(100), 100.0)
        self.assertEqual(self.healer.heal_value(3.14), 3.14)

        # Valid string numbers should be parsed
        self.assertEqual(self.healer.heal_value("42"), 42.0)
        self.assertEqual(self.healer.heal_value("-123.45"), -123.45)

    def test_dirty_data_auto_healing(self):
        """Test #2: Dirty data auto-healing (formula errors, text, etc)."""
        # Excel error constants
        self.assertEqual(self.healer.heal_value("#REF!"), 0.0)
        self.assertEqual(self.healer.heal_value("#DIV/0!"), 0.0)
        self.assertEqual(self.healer.heal_value("#VALUE!"), 0.0)
        self.assertEqual(self.healer.heal_value("#N/A"), 0.0)
        self.assertEqual(self.healer.heal_value("#NAME?"), 0.0)
        self.assertEqual(self.healer.heal_value("CIRCREF"), 0.0)

        # Case insensitive check
        self.assertEqual(self.healer.heal_value("#ref!"), 0.0)
        self.assertEqual(self.healer.heal_value("#div/0!"), 0.0)

        # Random gibberish string
        self.assertEqual(self.healer.heal_value("not a number"), 0.0)
        self.assertEqual(self.healer.heal_value("garbage 123"), 0.0)

    def test_missing_params_default_fallback(self):
        """Test #3: Missing parameters with sensible default fallback."""
        # None value defaults to init fallback
        self.assertEqual(self.healer.heal_value(None), 0.0)

        # None dataset defaults to empty list
        self.assertEqual(self.healer.heal_dataset(None), [])

        # Not a list defaults to empty list if not iterable
        self.assertEqual(self.healer.heal_dataset(123), [])

        # Missing fallback on heal_value uses self.fallback_value
        healer_custom = XlsxFormulaHealer(fallback_value=-99.9)
        self.assertEqual(healer_custom.heal_value("#REF!"), -99.9)

        # Explicit fallback override
        self.assertEqual(self.healer.heal_value("#REF!", fallback=1.1), 1.1)

    def test_extreme_boundary_cases(self):
        """Test #4: Extreme boundary cases (cross year/month, huge numbers, etc)."""
        dataset = SyntheticFixtures.generate_boundary_dataset()
        healed_data = self.healer.heal_dataset(dataset)

        self.assertEqual(len(dataset), len(healed_data))

        # Check specific boundaries
        self.assertEqual(healed_data[0], 0.0) # 2023-12-31 fallback
        self.assertEqual(healed_data[1], 0.0) # 2024-01-01 fallback
        self.assertEqual(healed_data[2], 1e308) # huge num OK
        self.assertEqual(healed_data[3], -1e308) # negative huge num OK
        self.assertEqual(healed_data[4], 0.0) # #ref! fallback
        self.assertEqual(healed_data[5], 0.0) # #DIV/0! fallback
        self.assertEqual(healed_data[6], 0.0) # None fallback
        self.assertEqual(healed_data[7], 0.0) # empty string fallback
        self.assertEqual(healed_data[8], 0.0) # whitespace string fallback
        self.assertEqual(healed_data[9], 0.0) # 0.0 is 0.0
        self.assertEqual(healed_data[10], 0.0) # -0.0 is 0.0

    def test_performance_benchmark(self):
        """Test #5: Performance benchmark validation on large datasets."""
        suite = BenchmarkSuite()
        # 10,000 items in <= 250ms (generous buffer for slow CI environments)
        result = suite.run_concurrency_benchmark(dataset_size=10000, max_time_ms=250)

        self.assertTrue(result["success"], f"Performance test failed! Took {result['duration_ms']} ms")
        self.assertEqual(result["dataset_size"], 10000)
        self.assertEqual(result["healed_count"], 10000)

if __name__ == '__main__':
    unittest.main()

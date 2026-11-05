import unittest
from ultra_modules.zhaopin_greeting_personalizer_benchmark_suite import (
    clean_string,
    generate_greeting,
    generate_synthetic_fixtures,
    benchmark_performance
)

class TestZhaopinGreetingPersonalizer(unittest.TestCase):

    def test_clean_string_normal(self):
        """Test clean_string with normal string."""
        self.assertEqual(clean_string("  hello  ", "default"), "hello")

    def test_clean_string_missing_values(self):
        """Test clean_string with None or empty values."""
        self.assertEqual(clean_string(None, "default"), "default")
        self.assertEqual(clean_string("   ", "default"), "default")
        self.assertEqual(clean_string("", "default"), "default")

    def test_clean_string_dirty_data(self):
        """Test clean_string with control characters and unprintable chars."""
        self.assertEqual(clean_string("\x00\x01\x02", "default"), "default")
        self.assertEqual(clean_string(" \x01 dirty \x02 ", "default"), "dirty")

    def test_clean_string_type_coercion(self):
        """Test clean_string with integers, floats, and non-string types."""
        self.assertEqual(clean_string(12345, "default"), "12345")
        self.assertEqual(clean_string(99.9, "default"), "99.9")
        self.assertEqual(clean_string({}, "default"), "default")
        self.assertEqual(clean_string([], "default"), "default")

    def test_generate_greeting_normal(self):
        """Test generate_greeting with standard expected data."""
        data = {"name": "张三", "experience": "富士康3年", "location": "深圳"}
        result = generate_greeting(data)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["metadata"]["name_used"], "张三")
        self.assertEqual(result["metadata"]["experience_used"], "富士康3年")
        self.assertEqual(result["metadata"]["location_used"], "深圳")
        self.assertIn("你好张三", result["greeting"])
        self.assertIn("富士康3年", result["greeting"])
        self.assertIn("深圳", result["greeting"])

    def test_generate_greeting_missing_parameters_fallback(self):
        """Test generate_greeting with empty dict and None, verifying fallback defaults."""
        expected_defaults = {"name_used": "同学", "experience_used": "丰富", "location_used": "本地"}

        result_empty = generate_greeting({})
        self.assertEqual(result_empty["metadata"], expected_defaults)

        result_none = generate_greeting(None)
        self.assertEqual(result_none["metadata"], expected_defaults)

        result_invalid_type = generate_greeting("invalid_string")
        self.assertEqual(result_invalid_type["metadata"], expected_defaults)

    def test_generate_greeting_dirty_data_self_healing(self):
        """Test generate_greeting with extreme dirty data and types."""
        dirty_data = {
            "name": "\x00 \t\n ",
            "experience": 99.5,
            "location": ["invalid_list"]
        }
        result = generate_greeting(dirty_data)
        self.assertEqual(result["metadata"]["name_used"], "同学")
        self.assertEqual(result["metadata"]["experience_used"], "99.5")
        self.assertEqual(result["metadata"]["location_used"], "本地")

    def test_generate_synthetic_fixtures(self):
        """Test synthetic fixtures generation covers extreme cases."""
        fixtures = generate_synthetic_fixtures(10)
        self.assertEqual(len(fixtures), 10)
        # Verify first few are specific deterministic cases
        self.assertEqual(fixtures[0]["name"], "张三")
        self.assertEqual(fixtures[1], {})
        self.assertIsNone(fixtures[2]["name"])
        self.assertIsNone(fixtures[7])

    def test_benchmark_performance_zero_crash(self):
        """Test benchmark performance handles mass concurrency without crashing."""
        concurrency = 1000
        result = benchmark_performance(concurrency)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_requests"], concurrency)
        self.assertTrue(result["average_ms_per_request"] >= 0)

    def test_benchmark_performance_zero_concurrency(self):
        """Test benchmark performance handles 0 concurrency without DivisionByZero."""
        result = benchmark_performance(0)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_requests"], 0)
        self.assertEqual(result["average_ms_per_request"], 0)

if __name__ == '__main__':
    unittest.main()

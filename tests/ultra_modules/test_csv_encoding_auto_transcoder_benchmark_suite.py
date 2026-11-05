import unittest
import time
from ultra_modules.csv_encoding_auto_transcoder_benchmark_suite import transcode_csv_to_utf8, generate_synthetic_fixture

class TestCSVEncodingAutoTranscoderBenchmarkSuite(unittest.TestCase):

    def test_normal_utf8_transcoding(self):
        """Test with clean UTF-8 encoded byte string."""
        original_str = "ID,Name,Salary\n1,张三,5000\n"
        input_bytes = original_str.encode('utf-8')
        result = transcode_csv_to_utf8(input_bytes)
        self.assertEqual(result, original_str)

    def test_gbk_gb18030_transcoding(self):
        """Test with GBK and GB18030 encoded byte strings."""
        original_str = "ID,Name,Remarks\n1,李四,测试备注\n"

        # Test GBK
        gbk_bytes = original_str.encode('gbk')
        result_gbk = transcode_csv_to_utf8(gbk_bytes)
        self.assertEqual(result_gbk, original_str)

        # Test GB18030
        gb18030_bytes = original_str.encode('gb18030')
        result_gb18030 = transcode_csv_to_utf8(gb18030_bytes)
        self.assertEqual(result_gb18030, original_str)

    def test_dirty_data_self_healing(self):
        """Test dirty data self-healing (e.g. invalid byte sequences)."""
        # Create bytes that are not valid in standard encodings
        invalid_bytes = b"ID,Name\n1,Test\n" + bytes([0xff, 0xfe, 0xfd])
        result = transcode_csv_to_utf8(invalid_bytes)
        # It should decode using the fallback encoding with replacement characters
        self.assertTrue("ID,Name\n1,Test\n" in result)
        self.assertTrue("\ufffd" in result) # Replacement character expected

    def test_missing_params_default(self):
        """Test default missing parameter fallback logic."""
        # When passed None
        self.assertEqual(transcode_csv_to_utf8(None), "")

        # When passed string, it should handle the type error internally
        original_str = "ID,Name\n1,王五\n"
        result = transcode_csv_to_utf8(original_str)
        self.assertEqual(result, original_str)

    def test_extreme_boundary_and_performance(self):
        """Test with large synthetic fixture for boundary conditions and performance."""
        # Use 100,000 rows to test performance and edge cases (cross year/month)
        size = 100000
        fixture_bytes = generate_synthetic_fixture(size=size, encoding='gb18030')

        start_time = time.perf_counter()
        result = transcode_csv_to_utf8(fixture_bytes)
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000

        # The result string must contain the expected content correctly decoded
        self.assertTrue("特殊边界测试：跨年，跨月" in result)

        # We expect a millisecond-level response. We'll set a generous upper bound for the CI environment,
        # e.g., 2000ms for 100k rows, though locally it might be under 100ms.
        self.assertLess(duration_ms, 2000.0, f"Performance issue: took {duration_ms} ms")

        # Test extreme boundaries: cross year/month exist in the fixture
        self.assertTrue("2023-12-31" in result)
        self.assertTrue("2024-01-01" in result)

if __name__ == '__main__':
    unittest.main()

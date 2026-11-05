import unittest
import io
import csv
from ultra_modules.csv_encoding_auto_transcoder_integration_bridge import transcode_and_clean_csv

class TestCSVEncodingAutoTranscoderIntegrationBridge(unittest.TestCase):

    def test_normal_gbk_encoding_and_schema_mapping(self):
        # Normal data with GBK encoding
        csv_content = "员工姓名,工号,底薪\n张三,1001,5000\n李四,1002,6000"
        gbk_bytes = csv_content.encode('gbk')
        result = transcode_and_clean_csv(gbk_bytes)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '张三')
        self.assertEqual(result[0]['employee_id'], '1001')
        self.assertEqual(result[0]['base_salary'], '5000')

    def test_utf8_sig_and_dirty_data(self):
        # UTF-8-SIG encoding with empty lines and extra columns
        csv_content = "\n\n姓名,工号,未知列\n王五,1003,test_val\n\n赵六,1004,test_val2,extra_val\n"
        utf8_sig_bytes = csv_content.encode('utf-8-sig')
        result = transcode_and_clean_csv(utf8_sig_bytes)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '王五')
        self.assertEqual(result[0]['未知列'], 'test_val')
        self.assertEqual(result[1]['name'], '赵六')
        # Extra columns should be truncated
        self.assertEqual(len(result[1].keys()), 3)

    def test_missing_parameters_default_fallback(self):
        # Missing or empty input
        self.assertEqual(transcode_and_clean_csv(), [])
        self.assertEqual(transcode_and_clean_csv(b""), [])
        self.assertEqual(transcode_and_clean_csv(""), [])
        self.assertEqual(transcode_and_clean_csv(None, "csv_bytes"), b"")
        self.assertEqual(transcode_and_clean_csv(b"   \n  \n"), [])

    def test_invalid_type_input(self):
        # Passing an integer or a list instead of str/bytes
        self.assertEqual(transcode_and_clean_csv(12345), [])
        self.assertEqual(transcode_and_clean_csv([1, 2, 3], output_format="csv_bytes"), b"")

    def test_extreme_boundary_and_undecodable_fallback(self):
        # Generating a byte sequence that might fail standard decoding, triggering errors='ignore'
        # Let's create an invalid byte sequence for UTF-8
        bad_bytes = b"name,id\nJohn,\xff\xfe\xfd"
        result = transcode_and_clean_csv(bad_bytes)

        # It should decode using errors='ignore' and still return structured data
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'John')
        # The invalid bytes should be ignored or partially decoded depending on python version,
        # but the program should not crash.

    def test_output_format_csv_bytes(self):
        csv_content = "name,employee id,attendance\nAlice,A01,20"
        result = transcode_and_clean_csv(csv_content, output_format="csv_bytes")

        self.assertIsInstance(result, bytes)
        decoded = result.decode('utf-8')
        f = io.StringIO(decoded)
        reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 1)
        self.assertEqual(reader[0]['name'], 'Alice')
        self.assertEqual(reader[0]['employee_id'], 'A01')
        self.assertEqual(reader[0]['attendance_days'], '20')

    def test_duplicate_columns(self):
        csv_content = "name,name,id\nTom,Jerry,T01"
        result = transcode_and_clean_csv(csv_content)

        self.assertEqual(len(result), 1)
        self.assertIn('name', result[0])
        self.assertIn('name_1', result[0])
        self.assertEqual(result[0]['name'], 'Tom')
        self.assertEqual(result[0]['name_1'], 'Jerry')

    def test_missing_data_columns(self):
        csv_content = "name,id,base salary\nTom,T01"
        result = transcode_and_clean_csv(csv_content)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Tom')
        self.assertEqual(result[0]['employee_id'], 'T01')
        self.assertEqual(result[0]['base_salary'], '') # padded with empty string

    def test_empty_headers_row(self):
        csv_content = "   ,   ,   \n"
        result = transcode_and_clean_csv(csv_content)
        self.assertEqual(result, [])

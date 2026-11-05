import os
import csv
import json
import tempfile
import unittest
from unittest.mock import patch

from ultra_modules.csv_encoding_auto_transcoder_cli_one_click import (
    detect_encoding_and_read,
    clean_for_excel,
    process_file,
    main
)

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class TestCSVEncodingAutoTranscoderCLI(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_normal_input_utf8(self):
        """Test reading a normal UTF-8 CSV file."""
        file_path = "normal_utf8.csv"
        with open(file_path, "wb") as f:
            f.write("姓名,年龄\n张三,30\n李四,25".encode("utf-8"))

        records, fieldnames, encoding = detect_encoding_and_read(file_path)

        self.assertEqual(encoding, "utf-8")
        self.assertEqual(fieldnames, ["姓名", "年龄"])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["姓名"], "张三")
        self.assertEqual(records[0]["年龄"], "30")

    def test_dirty_data_self_healing(self):
        """Test reading a CSV with mixed/dirty encoding data."""
        file_path = "dirty_data.csv"
        # First write GBK string, but purposely corrupt one byte
        gbk_bytes = "部门,姓名\n研发,王五".encode("gbk")
        corrupt_bytes = bytearray(gbk_bytes)
        corrupt_bytes[-1] = 0x20 # Corrupt the last byte to create dirty data

        with open(file_path, "wb") as f:
            f.write(corrupt_bytes)

        records, fieldnames, encoding = detect_encoding_and_read(file_path)

        self.assertEqual(fieldnames, ["部门", "姓名"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["部门"], "研发")
        # Self-healing should have replaced the bad byte
        self.assertTrue(records[0]["姓名"].startswith("王"))

    def test_missing_parameter_default_fallback(self):
        """Test CLI defaults to current directory CSVs when no params provided."""
        # Create a test CSV in the temp directory
        file_path = "test_default.csv"
        with open(file_path, "wb") as f:
            f.write("id,value\n1,test".encode("utf-8"))

        # Mock sys.argv to simulate running script with no arguments
        with patch('sys.argv', ['csv_encoding_auto_transcoder_cli_one_click.py']):
            main()

        # Check if the default output files were created
        self.assertTrue(os.path.exists("test_default_cleaned.csv"))
        self.assertTrue(os.path.exists("test_default_cleaned.json"))
        if HAS_OPENPYXL:
            self.assertTrue(os.path.exists("test_default_cleaned.xlsx"))

        with open("test_default_cleaned.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["id"], "1")
            self.assertEqual(data[0]["value"], "test")

    def test_extreme_boundary_empty_file(self):
        """Test extreme boundary case: completely empty file."""
        file_path = "empty.csv"
        with open(file_path, "wb") as f:
            pass # Empty

        records, fieldnames, encoding = detect_encoding_and_read(file_path)
        self.assertEqual(records, [])
        self.assertEqual(fieldnames, [])

    def test_extreme_boundary_control_chars_excel(self):
        """Test extreme boundary case: control characters in excel export."""
        file_path = "control_chars.csv"
        with open(file_path, "wb") as f:
            f.write("id,desc\n1,test\x00data\x01\n".encode("utf-8"))

        # Use explicit formats to only output excel
        process_file(file_path, formats=['excel'])

        if HAS_OPENPYXL:
            import openpyxl
            wb = openpyxl.load_workbook("control_chars_cleaned.xlsx")
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))

            # The control characters \x00 and \x01 should be removed
            self.assertEqual(rows[0], ("id", "desc"))
            self.assertEqual(rows[1], ("1", "testdata"))

if __name__ == '__main__':
    unittest.main()

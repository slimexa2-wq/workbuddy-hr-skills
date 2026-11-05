import unittest
import os
import json
import tempfile
from unittest.mock import patch
from ultra_modules.zhaopin_greeting_personalizer_cli_one_click import adapt_and_generate

try:
    import openpyxl
except ImportError:
    openpyxl = None

class TestZhaoPinGreetingPersonalizerCliOneClick(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_missing_parameters_defaults(self):
        """Test zero-config execution (no params), it should return the default greeting."""
        result = adapt_and_generate()
        self.assertIsInstance(result, str)
        self.assertIn("同学你好！", result)
        self.assertIn("核心岗位", result)

    def test_happy_path_json(self):
        """Test processing a valid JSON file."""
        input_path = os.path.join(self.test_dir.name, "input.json")
        output_path = os.path.join(self.test_dir.name, "output.json")

        data = [
            {
                "candidate_name": "张三",
                "expected_location": "北京",
                "past_companies": ["腾讯", "阿里"],
                "role": "高级开发"
            }
        ]
        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        success = adapt_and_generate(input_source=input_path, output_dest=output_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, 'r', encoding='utf-8') as f:
            out_data = json.load(f)

        self.assertEqual(len(out_data), 1)
        self.assertIn("generated_greeting", out_data[0])
        self.assertIn("张三你好！", out_data[0]["generated_greeting"])
        self.assertIn("腾讯", out_data[0]["generated_greeting"])

    @unittest.skipIf(openpyxl is None, "openpyxl not installed")
    def test_happy_path_excel(self):
        """Test processing a valid Excel file."""
        input_path = os.path.join(self.test_dir.name, "input.xlsx")
        output_path = os.path.join(self.test_dir.name, "output.xlsx")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["姓名", "期望地点", "过往公司", "岗位"])
        ws.append(["李四", "上海", "字节", "产品"])
        wb.save(input_path)

        success = adapt_and_generate(input_source=input_path, output_dest=output_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_path))

        out_wb = openpyxl.load_workbook(output_path)
        out_ws = out_wb.active

        # Header should have added column
        headers = [cell.value for cell in out_ws[1]]
        self.assertEqual(headers[-1], "generated_greeting")

        # Second row should have greeting
        greeting = out_ws.cell(row=2, column=5).value
        self.assertIsNotNone(greeting)
        self.assertIn("李四你好！", greeting)

    def test_dirty_data_self_healing_json(self):
        """Test dirty JSON data (not a list, malformed items)."""
        input_path = os.path.join(self.test_dir.name, "dirty.json")
        output_path = os.path.join(self.test_dir.name, "dirty_out.json")

        # Mixed types, invalid objects
        data = [
            "Just a string, should be skipped",
            {"candidate_name": "王五"}, # valid enough, missing others will fallback
            12345
        ]
        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        success = adapt_and_generate(input_source=input_path, output_dest=output_path)
        self.assertTrue(success)

        with open(output_path, 'r', encoding='utf-8') as f:
            out_data = json.load(f)

        # Only one valid row should be processed and kept
        self.assertEqual(len(out_data), 1)
        self.assertEqual(out_data[0]["candidate_name"], "王五")
        self.assertIn("王五你好！", out_data[0]["generated_greeting"])

    def test_extreme_boundaries(self):
        """Test invalid file types and non-existent files."""
        # Non-existent
        success = adapt_and_generate(input_source="does_not_exist.json")
        self.assertFalse(success)

        # Unsupported format
        input_txt = os.path.join(self.test_dir.name, "test.txt")
        with open(input_txt, 'w') as f:
            f.write("test")
        success = adapt_and_generate(input_source=input_txt)
        self.assertFalse(success)

    def test_unwritable_output_path(self):
        """Test with an unwritable path for default zero-config mode."""
        # Write to a restricted directory like /root or /
        success = adapt_and_generate(input_source=None, output_dest="/root/restricted.txt")
        # Should gracefully fail and return False instead of throwing uncaught exception
        self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()

import unittest
import os
import json
import zipfile
import io
import tempfile
import sys
from io import StringIO
import openpyxl

from ultra_modules.batch_commission_zip_exporter_cli_one_click import BatchCommissionZipExporterOneClick, main

class TestBatchCommissionZipExporterCliOneClick(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.exporter = BatchCommissionZipExporterOneClick()

    def tearDown(self):
        for root, dirs, files in os.walk(self.test_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.test_dir)

        # Clean up demo zip if generated
        if os.path.exists("demo_commissions.zip"):
            os.remove("demo_commissions.zip")

    def test_normal_json_processing(self):
        json_path = os.path.join(self.test_dir, "input.json")
        out_path = os.path.join(self.test_dir, "output.zip")
        data = [
            {'supplier_name': 'Tech Corp', 'commission_amount': 150.5},
            {'supplier_name': 'Alpha Inc', 'commission_amount': 50.0}
        ]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        success = self.exporter.process_file(json_path, out_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path))

        with zipfile.ZipFile(out_path, 'r') as zf:
            files = zf.namelist()
            self.assertIn("Tech Corp/commissions.csv", files)
            self.assertIn("Alpha Inc/commissions.csv", files)

    def test_normal_excel_processing(self):
        xlsx_path = os.path.join(self.test_dir, "input.xlsx")
        out_path = os.path.join(self.test_dir, "output_xlsx.zip")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["supplier_name", "commission_amount"])
        ws.append(["Beta LLC", 200.0])
        ws.append(["Gamma Co", 100.0])
        wb.save(xlsx_path)

        success = self.exporter.process_file(xlsx_path, out_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path))

        with zipfile.ZipFile(out_path, 'r') as zf:
            files = zf.namelist()
            self.assertIn("Beta LLC/commissions.csv", files)
            self.assertIn("Gamma Co/commissions.csv", files)

    def test_dirty_data_self_healing(self):
        json_path = os.path.join(self.test_dir, "dirty.json")
        out_path = os.path.join(self.test_dir, "dirty_output.zip")

        # Missing supplier, invalid amount
        data = [
            {'supplier_name': '', 'commission_amount': 'invalid'},
            {'supplier_name': None, 'commission_amount': None}
        ]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        success = self.exporter.process_file(json_path, out_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path))

        with zipfile.ZipFile(out_path, 'r') as zf:
            files = zf.namelist()
            self.assertIn("Unknown_Supplier/commissions.csv", files)

    def test_default_fallback_missing_parameters(self):
        # Simulate zero configuration (no args) by patching sys.argv
        original_argv = sys.argv
        sys.argv = ['batch_commission_zip_exporter_cli_one_click.py']

        original_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            main()
            output = sys.stdout.getvalue()
            self.assertIn("Zero-config mode", output)
            self.assertTrue(os.path.exists("demo_commissions.zip"))
        finally:
            sys.argv = original_argv
            sys.stdout = original_stdout

    def test_extreme_edge_cases(self):
        # Test 1: Empty list JSON
        json_path = os.path.join(self.test_dir, "empty.json")
        out_path = os.path.join(self.test_dir, "empty_out.zip")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

        success = self.exporter.process_file(json_path, out_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path))

        # Test 2: Non-list data (a single dictionary)
        json_path2 = os.path.join(self.test_dir, "single.json")
        out_path2 = os.path.join(self.test_dir, "single_out.zip")
        with open(json_path2, 'w', encoding='utf-8') as f:
            json.dump({"supplier_name": "Edge Co", "commission_amount": 50}, f)

        success = self.exporter.process_file(json_path2, out_path2)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_path2))

        with zipfile.ZipFile(out_path2, 'r') as zf:
            self.assertIn("Edge Co/commissions.csv", zf.namelist())

if __name__ == '__main__':
    unittest.main()

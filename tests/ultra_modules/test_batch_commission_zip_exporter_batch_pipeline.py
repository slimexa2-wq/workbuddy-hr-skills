import unittest
import zipfile
import io
import csv
from unittest.mock import patch
from ultra_modules.batch_commission_zip_exporter_batch_pipeline import run_pipeline, sanitize_data, process_batch_worker

class TestBatchCommissionZipExporterBatchPipeline(unittest.TestCase):
    def test_normal_data_processing(self):
        """Test with valid data grouping by vendor and output ZIP contains expected files and audit_status."""
        records = [
            {"vendor": "VendorA", "project": "Proj1", "amount": 100.5},
            {"vendor": "VendorB", "project": "Proj2", "amount": 200.0},
            {"vendor": "VendorA", "project": "Proj3", "amount": "300"},
        ]
        zip_bytes = run_pipeline(records)
        self.assertIsInstance(zip_bytes, bytes)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            file_names = zf.namelist()
            self.assertIn("VendorA_《（审核版）》.csv", file_names)
            self.assertIn("VendorB_《（审核版）》.csv", file_names)

            # Read VendorA file and check contents
            with zf.open("VendorA_《（审核版）》.csv") as f:
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["audit_status"], "PENDING")

                # Check unordered due to concurrent processing
                amounts = {float(row["amount"]) for row in rows}
                self.assertSetEqual(amounts, {100.5, 300.0})

    def test_missing_params_fallback(self):
        """Test zero-configuration fallback when None or non-list is passed."""
        zip_bytes_none = run_pipeline(None)
        with zipfile.ZipFile(io.BytesIO(zip_bytes_none), 'r') as zf:
            self.assertIn("empty.txt", zf.namelist())

        zip_bytes_invalid = run_pipeline({"wrong": "type"})
        with zipfile.ZipFile(io.BytesIO(zip_bytes_invalid), 'r') as zf:
            self.assertIn("empty.txt", zf.namelist())

        zip_bytes_empty_list = run_pipeline([])
        with zipfile.ZipFile(io.BytesIO(zip_bytes_empty_list), 'r') as zf:
            self.assertIn("empty.txt", zf.namelist())

    def test_dirty_data_self_healing(self):
        """Test dirty records: missing fields, invalid amounts, blank vendor."""
        records = [
            {"vendor": "", "project": None, "amount": "invalid"},
            {"vendor": 123, "project": 456, "amount": None},
            "Not a dictionary"
        ]
        zip_bytes = run_pipeline(records)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            file_names = zf.namelist()
            self.assertIn("UNKNOWN_VENDOR_《（审核版）》.csv", file_names)

            with zf.open("UNKNOWN_VENDOR_《（审核版）》.csv") as f:
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
                self.assertEqual(len(rows), 2)

                # First record checks
                self.assertEqual(rows[0]["vendor"], "UNKNOWN_VENDOR")
                self.assertEqual(rows[0]["project"], "UNKNOWN_PROJECT")
                self.assertEqual(float(rows[0]["amount"]), 0.0)

                # Second record checks
                self.assertEqual(rows[1]["vendor"], "UNKNOWN_VENDOR")
                self.assertEqual(rows[1]["project"], "UNKNOWN_PROJECT")
                self.assertEqual(float(rows[1]["amount"]), 0.0)

    def test_large_batch_processing(self):
        """Test boundary of 1000 records."""
        records = [{"vendor": f"Vendor{i%5}", "project": f"Proj{i}", "amount": i} for i in range(1000)]
        zip_bytes = run_pipeline(records, concurrency=4)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            file_names = zf.namelist()
            self.assertEqual(len(file_names), 5)  # 5 vendors
            for i in range(5):
                self.assertIn(f"Vendor{i}_《（审核版）》.csv", file_names)
                with zf.open(f"Vendor{i}_《（审核版）》.csv") as f:
                    content = f.read().decode('utf-8-sig')
                    reader = list(csv.DictReader(io.StringIO(content)))
                    self.assertEqual(len(reader), 200)  # 1000 / 5

    def test_empty_vendor_groups(self):
        """Test case where all records are filtered out (e.g. invalid types)."""
        records = ["invalid1", "invalid2"]
        zip_bytes = run_pipeline(records)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            self.assertIn("empty.txt", zf.namelist())

            with zf.open("empty.txt") as f:
                self.assertEqual(f.read(), b"No valid records processed.")

    @patch('ultra_modules.batch_commission_zip_exporter_batch_pipeline.process_batch_worker')
    def test_worker_exception(self, mock_worker):
        """Test exception handling within the threadpool worker."""
        mock_worker.side_effect = Exception("Simulated Worker Error")
        records = [{"vendor": "VendorA", "project": "Proj1", "amount": 100}]

        # The pipeline should silently ignore the error and result in empty processing
        zip_bytes = run_pipeline(records)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            self.assertIn("empty.txt", zf.namelist())
            with zf.open("empty.txt") as f:
                self.assertEqual(f.read(), b"No valid records processed.")

if __name__ == '__main__':
    unittest.main()

import unittest
import zipfile
import io
import csv
import time
from ultra_modules.batch_commission_zip_exporter_benchmark_suite import process_commission_data

class TestBatchCommissionZipExporter(unittest.TestCase):
    def _read_zip_csv(self, zip_bytes: bytes, filename: str) -> list[dict]:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with zf.open(filename) as f:
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                return list(reader)

    def test_normal_usage(self):
        """Test normal usage with valid data."""
        data = [
            {"supplier": "Supplier A", "amount": 100, "date": "2023-01-01"},
            {"supplier": "Supplier B", "amount": 200, "date": "2023-01-02"},
            {"supplier": "Supplier A", "amount": 150, "date": "2023-01-03"},
        ]
        result = process_commission_data(data)

        self.assertIn("Supplier A", result)
        self.assertIn("Supplier B", result)

        rows_a = self._read_zip_csv(result["Supplier A"], "Supplier A_commissions.csv")
        self.assertEqual(len(rows_a), 2)
        self.assertEqual(rows_a[0]["《（审核版）》"], "已核对")
        self.assertEqual(rows_a[0]["status"], "processed")
        self.assertEqual(rows_a[0]["amount"], "100")

    def test_dirty_data_self_healing(self):
        """Test with dirty data like None values, empty strings, non-dict rows."""
        data = [
            {"supplier": None, "amount": 100, "status": None},
            {"supplier": "  ", "amount": None},
            {"supplier": "Supplier C", "amount": 300, None: "bad_key", "  ": "empty_key"},
            "this is not a dict",
            123,
        ]
        result = process_commission_data(data)

        self.assertIn("Unknown Supplier", result)
        self.assertIn("Supplier C", result)

        rows_unknown = self._read_zip_csv(result["Unknown Supplier"], "Unknown Supplier_commissions.csv")
        self.assertEqual(len(rows_unknown), 2)
        self.assertEqual(rows_unknown[0]["amount"], "100")
        self.assertEqual(rows_unknown[0]["status"], "processed")
        self.assertEqual(rows_unknown[1]["amount"], "")

        rows_c = self._read_zip_csv(result["Supplier C"], "Supplier C_commissions.csv")
        self.assertEqual(len(rows_c), 1)
        self.assertNotIn("None", rows_c[0])
        self.assertNotIn("  ", rows_c[0])

    def test_missing_params_fallback(self):
        """Test with empty dataset and fallback configurations."""
        self.assertEqual(process_commission_data([]), {})

        # Missing supplier handled by default
        data = [{"amount": 500}]
        result = process_commission_data(data, default_supplier="Fallback Supplier")
        self.assertIn("Fallback Supplier", result)
        rows = self._read_zip_csv(result["Fallback Supplier"], "Fallback Supplier_commissions.csv")
        self.assertEqual(rows[0]["amount"], "500")

    def test_existing_status(self):
        """Test with an existing status."""
        data = [{"amount": 500, "status": "existing_status"}]
        result = process_commission_data(data)
        self.assertIn("Unknown Supplier", result)
        rows = self._read_zip_csv(result["Unknown Supplier"], "Unknown Supplier_commissions.csv")
        self.assertEqual(rows[0]["status"], "existing_status")

    def test_extreme_boundary_cases(self):
        """Test cross-year/month boundaries and encoding edge cases."""
        data = [
            {"supplier": "Sup D", "date": "1999-12-31 23:59:59", "amount": 1},
            {"supplier": "Sup D", "date": "2000-01-01 00:00:00", "amount": 2},
            {"supplier": "Sup 🚀", "note": "你好, \n world, 😎"},
            {"supplier": "Sup E", "key_with_,_comma": "value"}
        ]
        result = process_commission_data(data)

        self.assertIn("Sup D", result)
        self.assertIn("Sup 🚀", result)

        rows_d = self._read_zip_csv(result["Sup D"], "Sup D_commissions.csv")
        self.assertEqual(len(rows_d), 2)

        rows_emoji = self._read_zip_csv(result["Sup 🚀"], "Sup 🚀_commissions.csv")
        self.assertEqual(rows_emoji[0]["note"], "你好, \n world, 😎")

    def test_synthetic_benchmark(self):
        """Benchmark test with large synthetic payload to ensure millisecond response (if possible) and no crashes."""
        # Generate large dataset
        data = []
        for i in range(10000): # 10k rows
            supplier_id = i % 10 # 10 suppliers
            data.append({
                "supplier": f"Benchmark_Supplier_{supplier_id}",
                "amount": i * 10.5,
                "tx_id": f"TXN_{i}",
                "random_data": "A" * 100 # 100 bytes of padding
            })

        start_time = time.time()
        result = process_commission_data(data)
        end_time = time.time()

        self.assertEqual(len(result), 10)
        for i in range(10):
            sup = f"Benchmark_Supplier_{i}"
            self.assertIn(sup, result)
            rows = self._read_zip_csv(result[sup], f"{sup}_commissions.csv")
            self.assertEqual(len(rows), 1000)

        print(f"\\nProcessed 10,000 rows in {end_time - start_time:.4f} seconds")

    def test_invalid_all_rows(self):
        """Test where all rows are invalid, should return empty dict."""
        data = ["invalid", 123, None]
        result = process_commission_data(data)
        self.assertEqual(result, {})

if __name__ == "__main__":
    unittest.main()

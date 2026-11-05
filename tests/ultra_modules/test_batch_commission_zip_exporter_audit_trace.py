import unittest
import zipfile
import io
import json
import csv
from ultra_modules.batch_commission_zip_exporter_audit_trace import process_commissions

class TestBatchCommissionZipExporterAuditTrace(unittest.TestCase):

    def test_normal_processing(self):
        """Test processing of normal, clean records without any missing data."""
        raw_data = [
            {"record_id": "r1", "vendor_name": "VendorA", "project_id": "P1", "amount": 100.5},
            {"record_id": "r2", "vendor_name": "VendorB", "project_id": "P2", "amount": 200.0},
        ]

        results = process_commissions(raw_data)

        self.assertIn("VendorA", results)
        self.assertIn("VendorB", results)

        # Verify VendorA contents
        zip_bytes = results["VendorA"]
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            self.assertIn("VendorA_audited_commissions.csv", zf.namelist())
            self.assertIn("VendorA_audit_trace.json", zf.namelist())

            csv_content = zf.read("VendorA_audited_commissions.csv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["audit_flag"], "OK")
            self.assertEqual(rows[0]["amount"], "100.5")

            json_content = zf.read("VendorA_audit_trace.json").decode("utf-8")
            audit_log = json.loads(json_content)
            self.assertEqual(len(audit_log), 1)
            self.assertEqual(audit_log[0]["action"], "kept")
            self.assertEqual(len(audit_log[0]["modifications"]), 0)

    def test_dirty_data_auto_healing(self):
        """Test auto-healing of dirty data (e.g. string amounts with commas, unparseable amounts)."""
        raw_data = [
            {"record_id": "r1", "vendor_name": "VendorA", "project_id": "P1", "amount": "1,234.56"},
            {"record_id": "r2", "vendor_name": "VendorA", "project_id": "P2", "amount": "invalid_amount"},
        ]

        results = process_commissions(raw_data)
        zip_bytes = results["VendorA"]

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            csv_content = zf.read("VendorA_audited_commissions.csv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["amount"], "1234.56")
            self.assertEqual(rows[0]["audit_flag"], "HEALED")

            self.assertEqual(rows[1]["amount"], "0.0")
            self.assertEqual(rows[1]["audit_flag"], "HEALED")

            json_content = zf.read("VendorA_audit_trace.json").decode("utf-8")
            audit_log = json.loads(json_content)
            self.assertEqual(len(audit_log), 2)
            self.assertTrue(any("Cleaned string amount" in mod for mod in audit_log[0]["modifications"]))
            self.assertTrue(any("Failed to parse amount" in mod for mod in audit_log[1]["modifications"]))

    def test_missing_parameter_fallback(self):
        """Test fallback behavior for missing vendor, project, and record IDs."""
        raw_data = [
            {"amount": 500},
            {"vendor_name": " ", "project_id": None, "amount": 100}
        ]

        results = process_commissions(raw_data)
        self.assertIn("Unknown_Vendor", results)

        zip_bytes = results["Unknown_Vendor"]
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            csv_content = zf.read("Unknown_Vendor_audited_commissions.csv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)

            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["vendor_name"], "Unknown_Vendor")
                self.assertEqual(row["project_id"], "Unknown_Project")
                self.assertTrue(row["record_id"].startswith("generated_id_"))
                self.assertEqual(row["audit_flag"], "HEALED")

    def test_deduplication(self):
        """Test that duplicate record IDs for the same vendor are dropped."""
        raw_data = [
            {"record_id": "dup1", "vendor_name": "VendorD", "project_id": "P1", "amount": 100},
            {"record_id": "dup1", "vendor_name": "VendorD", "project_id": "P1", "amount": 100},
            {"record_id": "r2", "vendor_name": "VendorD", "project_id": "P2", "amount": 200},
        ]

        results = process_commissions(raw_data)
        zip_bytes = results["VendorD"]

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            csv_content = zf.read("VendorD_audited_commissions.csv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["record_id"], "dup1")
            self.assertEqual(rows[1]["record_id"], "r2")

            json_content = zf.read("VendorD_audit_trace.json").decode("utf-8")
            audit_log = json.loads(json_content)
            self.assertEqual(len(audit_log), 3)
            self.assertEqual(audit_log[1]["action"], "dropped_duplicate")

    def test_extreme_boundaries(self):
        """Test extreme boundaries like empty input and massive amount of data."""
        # Empty input
        self.assertEqual(process_commissions([]), {})
        self.assertEqual(process_commissions(None), {})

        # Massive amount of data (simulate with 10,000 records)
        massive_data = []
        for i in range(10000):
            massive_data.append({
                "record_id": f"rec_{i}",
                "vendor_name": "VendorMassive",
                "project_id": "P_Massive",
                "amount": i
            })

        results = process_commissions(massive_data)
        self.assertIn("VendorMassive", results)

        zip_bytes = results["VendorMassive"]
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            csv_content = zf.read("VendorMassive_audited_commissions.csv").decode("utf-8")
            # Just count lines to verify (header + 10000)
            lines = csv_content.strip().split('\n')
            self.assertEqual(len(lines), 10001)

if __name__ == "__main__":
    unittest.main()

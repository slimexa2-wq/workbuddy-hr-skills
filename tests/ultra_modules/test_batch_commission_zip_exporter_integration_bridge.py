import unittest
import zipfile
import io
import csv
from ultra_modules.batch_commission_zip_exporter_integration_bridge import process_integration_payload, auto_convert_schema

class TestBatchCommissionZipExporterIntegrationBridge(unittest.TestCase):

    def setUp(self):
        # We will helper function to read the contents of the zip
        pass

    def extract_zip_content(self, zip_bytes):
        result = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for file_name in z.namelist():
                content = z.read(file_name)
                # Ensure it's correctly decoding utf-8-sig (which core engine uses)
                text = content.decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(text))
                result[file_name] = list(reader)
        return result

    def test_normal_data_parsing(self):
        """Test with normal current schema data."""
        payload = [
            {"supplier_name": "SupplierA", "commission_amount": 100.5, "extra": "info"},
            {"supplier_name": "SupplierB", "commission_amount": 200}
        ]
        zip_bytes = process_integration_payload(payload)
        self.assertIsInstance(zip_bytes, bytes)
        self.assertTrue(len(zip_bytes) > 0)

        extracted = self.extract_zip_content(zip_bytes)
        self.assertIn("SupplierA/commissions.csv", extracted)
        self.assertIn("SupplierB/commissions.csv", extracted)

        rows_a = extracted["SupplierA/commissions.csv"]
        self.assertEqual(len(rows_a), 1)
        self.assertEqual(rows_a[0]["supplier_name"], "SupplierA")
        self.assertEqual(float(rows_a[0]["commission_amount"]), 100.5)
        self.assertEqual(rows_a[0]["verification_status"], "Verified")

    def test_dirty_data_self_healing(self):
        """Test handling dirty/malformed input structures."""
        # Payload with invalid rows and a wrapped data structure
        payload = {
            "data": [
                {"supplier_name": None, "commission_amount": "invalid_num"},
                "not a dict",
                {"vendor": "SupplierX", "amount": 99.9}
            ]
        }

        zip_bytes = process_integration_payload(payload)
        extracted = self.extract_zip_content(zip_bytes)

        # None supplier should become Unknown_Supplier
        self.assertIn("Unknown_Supplier/commissions.csv", extracted)
        rows_unknown = extracted["Unknown_Supplier/commissions.csv"]
        self.assertEqual(float(rows_unknown[0]["commission_amount"]), 0.0) # self-healed amount

        # SupplierX mapped from 'vendor' and amount mapped from 'amount'
        self.assertIn("SupplierX/commissions.csv", extracted)
        rows_x = extracted["SupplierX/commissions.csv"]
        self.assertEqual(float(rows_x[0]["commission_amount"]), 99.9)

    def test_missing_parameter_default_fallbacks(self):
        """Test default fallback when called without parameters."""
        zip_bytes = process_integration_payload() # None payload
        # Empty payload results in an empty zip archive from zipfile
        self.assertIsInstance(zip_bytes, bytes)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            self.assertEqual(len(z.namelist()), 0)

        # Custom verifier parameters
        payload = [{"vendor": "SupplierY", "fee": 50}]
        zip_bytes_custom = process_integration_payload(
            payload,
            default_verifier="IntegrationBot",
            default_audit_note="Custom Note"
        )
        extracted = self.extract_zip_content(zip_bytes_custom)
        rows_y = extracted["SupplierY/commissions.csv"]
        self.assertEqual(rows_y[0]["verifier"], "IntegrationBot")
        self.assertEqual(rows_y[0]["audit_note"], "Custom Note")

    def test_extreme_boundary_cases(self):
        """Test edge cases like completely wrong types."""
        # String payload instead of dict/list
        zip_bytes_str = process_integration_payload("completely unexpected string")
        with zipfile.ZipFile(io.BytesIO(zip_bytes_str)) as z:
            self.assertEqual(len(z.namelist()), 0)

        # Int payload
        zip_bytes_int = process_integration_payload(12345)
        with zipfile.ZipFile(io.BytesIO(zip_bytes_int)) as z:
            self.assertEqual(len(z.namelist()), 0)

        # Empty dict
        zip_bytes_empty_dict = process_integration_payload({})
        with zipfile.ZipFile(io.BytesIO(zip_bytes_empty_dict)) as z:
            # It will process an empty dict as a single record that triggers self-healing,
            # resulting in Unknown_Supplier with 0 commission.
            self.assertEqual(len(z.namelist()), 1)
            self.assertIn("Unknown_Supplier/commissions.csv", z.namelist())

    def test_schema_auto_mapping(self):
        """Test the schema auto mapping function specifically."""
        old_data = {
            "vendor_id": "LegacySupplier",
            "payout": 500,
            "extra_field": "val"
        }
        converted = auto_convert_schema(old_data)

        # New canonical fields should be present
        self.assertEqual(converted["supplier_name"], "LegacySupplier")
        self.assertEqual(converted["commission_amount"], 500)

        # Old fields should be preserved just in case
        self.assertEqual(converted["vendor_id"], "LegacySupplier")
        self.assertEqual(converted["payout"], 500)
        self.assertEqual(converted["extra_field"], "val")

        # Priority mapping: if both vendor and supplier_name exist, but supplier_name is empty
        conflict_data = {
            "vendor": "ValidSupplier",
            "supplier_name": ""
        }
        converted_conflict = auto_convert_schema(conflict_data)
        self.assertEqual(converted_conflict["supplier_name"], "ValidSupplier")

if __name__ == '__main__':
    unittest.main()

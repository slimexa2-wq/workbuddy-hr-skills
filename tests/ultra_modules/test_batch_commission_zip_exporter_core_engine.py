import unittest
import zipfile
import io
import csv
from ultra_modules.batch_commission_zip_exporter_core_engine import process_and_package_commissions

class TestBatchCommissionZipExporterCoreEngine(unittest.TestCase):

    def extract_zip_content(self, zip_bytes: bytes) -> dict:
        """Helper to extract and read ZIP contents into a dictionary of {filename: [rows]}"""
        if not zip_bytes:
            return {}

        result = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            for name in zf.namelist():
                content = zf.read(name).decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                result[name] = list(reader)
        return result

    def test_normal_case_with_typical_inputs(self):
        """Test normal processing with valid inputs."""
        records = [
            {'supplier_name': 'Tech Corp', 'commission_amount': 150.5, 'id': 1},
            {'supplier_name': 'Tech Corp', 'commission_amount': 200.0, 'id': 2},
            {'supplier_name': 'Alpha Inc', 'commission_amount': 50.0, 'id': 3}
        ]
        zip_bytes = process_and_package_commissions(records)

        self.assertTrue(len(zip_bytes) > 0)

        extracted = self.extract_zip_content(zip_bytes)
        self.assertIn('Tech Corp/commissions.csv', extracted)
        self.assertIn('Alpha Inc/commissions.csv', extracted)

        tech_rows = extracted['Tech Corp/commissions.csv']
        self.assertEqual(len(tech_rows), 2)
        self.assertEqual(tech_rows[0]['verification_status'], 'Verified')
        self.assertEqual(tech_rows[0]['verifier'], 'System_Auto')
        self.assertEqual(tech_rows[0]['audit_note'], 'Auto-verified by batch engine')
        self.assertEqual(float(tech_rows[0]['commission_amount']), 150.5)

        alpha_rows = extracted['Alpha Inc/commissions.csv']
        self.assertEqual(len(alpha_rows), 1)

    def test_dirty_data_self_healing_case(self):
        """Test handling of missing supplier, invalid amounts, unparsable rows."""
        records = [
            {'supplier_name': '', 'commission_amount': 'invalid', 'id': 1},
            {'supplier_name': None, 'commission_amount': None, 'id': 2},
            {'supplier_name': '  ', 'commission_amount': [], 'id': 3},
            "this is an invalid row that should be skipped",
            {'supplier_name': 'Null', 'commission_amount': -5.0, 'id': 4}
        ]

        zip_bytes = process_and_package_commissions(records)
        extracted = self.extract_zip_content(zip_bytes)

        self.assertIn('Unknown_Supplier/commissions.csv', extracted)
        unknown_rows = extracted['Unknown_Supplier/commissions.csv']

        # There should be 4 valid dictionary rows, the string row should be skipped
        self.assertEqual(len(unknown_rows), 4)

        # Check defaults for missing/invalid amounts
        self.assertEqual(float(unknown_rows[0]['commission_amount']), 0.0)
        self.assertEqual(float(unknown_rows[1]['commission_amount']), 0.0)
        self.assertEqual(float(unknown_rows[2]['commission_amount']), 0.0)
        self.assertEqual(float(unknown_rows[3]['commission_amount']), -5.0)

    def test_missing_arguments_case(self):
        """Test with None records to ensure it returns empty zip gracefully."""
        zip_bytes = process_and_package_commissions(None)
        extracted = self.extract_zip_content(zip_bytes)
        self.assertEqual(extracted, {})

        # Test completely omitted arguments
        zip_bytes_empty = process_and_package_commissions()
        extracted_empty = self.extract_zip_content(zip_bytes_empty)
        self.assertEqual(extracted_empty, {})

    def test_extreme_edge_case_single_dict(self):
        """Test extreme edge case where a single dictionary is passed instead of a list."""
        record = {'supplier_name': 'Beta LLC', 'commission_amount': 100.0, 'id': 99}
        zip_bytes = process_and_package_commissions(record)

        extracted = self.extract_zip_content(zip_bytes)
        self.assertIn('Beta LLC/commissions.csv', extracted)

        beta_rows = extracted['Beta LLC/commissions.csv']
        self.assertEqual(len(beta_rows), 1)
        self.assertEqual(beta_rows[0]['supplier_name'], 'Beta LLC')
        self.assertEqual(float(beta_rows[0]['commission_amount']), 100.0)

    def test_custom_verifier_and_empty_list_case(self):
        """Test custom verifier/note and empty input list."""
        records = [{'supplier_name': 'Gamma Co', 'commission_amount': 300.0, 'id': 5}]
        custom_verifier = "HR_Admin_01"
        custom_note = "Manually reviewed by Admin"

        zip_bytes = process_and_package_commissions(records, default_verifier=custom_verifier, default_audit_note=custom_note)
        extracted = self.extract_zip_content(zip_bytes)

        gamma_rows = extracted['Gamma Co/commissions.csv']
        self.assertEqual(gamma_rows[0]['verifier'], custom_verifier)
        self.assertEqual(gamma_rows[0]['audit_note'], custom_note)

        # Test empty list
        zip_bytes_empty = process_and_package_commissions([])
        extracted_empty = self.extract_zip_content(zip_bytes_empty)
        self.assertEqual(extracted_empty, {})

if __name__ == '__main__':
    unittest.main()

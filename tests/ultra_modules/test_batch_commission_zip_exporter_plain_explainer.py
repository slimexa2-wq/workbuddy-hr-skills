import unittest
import json
from ultra_modules.batch_commission_zip_exporter_plain_explainer import generate_plain_explainer_card

class TestBatchCommissionZipExporterPlainExplainer(unittest.TestCase):

    def test_normal_data_json(self):
        commissions = [
            {'supplier_name': 'Supplier A', 'amount': 100.5},
            {'supplier_name': 'Supplier B', 'amount': 200.0},
            {'supplier_name': 'Supplier A', 'amount': 50.25}
        ]
        result = generate_plain_explainer_card(commissions, 'json')
        parsed = json.loads(result)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['supplier'], 'Supplier A')
        self.assertEqual(parsed[0]['total_commission'], 150.75)
        self.assertEqual(parsed[1]['supplier'], 'Supplier B')
        self.assertEqual(parsed[1]['total_commission'], 200.0)

    def test_dirty_data_healing(self):
        commissions = [
            {'supplier_name': None, 'amount': 'invalid'}, # Should be "Unknown Supplier", 0.0
            {'supplier_name': 123, 'amount': None}, # Should be "Unknown Supplier", 0.0
            {'amount': 50.0}, # Should be "Unknown Supplier", 50.0
            'invalid_item', # Should be ignored
            {'supplier_name': 'Supplier X', 'amount': '10.5'} # Should be parsed to float 10.5
        ]
        result = generate_plain_explainer_card(commissions, 'json')
        parsed = json.loads(result)

        self.assertEqual(len(parsed), 2)
        # Sorted by supplier: "Supplier X" then "Unknown Supplier"
        self.assertEqual(parsed[0]['supplier'], 'Supplier X')
        self.assertEqual(parsed[0]['total_commission'], 10.5)
        self.assertEqual(parsed[1]['supplier'], 'Unknown Supplier')
        self.assertEqual(parsed[1]['total_commission'], 50.0)

    def test_missing_commissions_parameter(self):
        result_none = generate_plain_explainer_card(None, 'json')
        self.assertEqual(json.loads(result_none), [])

        result_invalid_type = generate_plain_explainer_card("invalid_string", 'json')
        self.assertEqual(json.loads(result_invalid_type), [])

    def test_html_format_output(self):
        commissions = [
            {'supplier_name': 'Supplier Z', 'amount': 300.0}
        ]
        result = generate_plain_explainer_card(commissions, 'html')
        self.assertIn("<div class='commission-card'>", result)
        self.assertIn("<li><strong>Supplier Z</strong>: 300.0</li>", result)

    def test_markdown_format_output(self):
        commissions = [
            {'supplier_name': 'Supplier Y', 'amount': 150.0}
        ]
        result = generate_plain_explainer_card(commissions, 'markdown')
        self.assertIn("# Supplier Commission Summary", result)
        self.assertIn("- **Supplier Y**: 150.0", result)

    def test_invalid_format_fallback(self):
        commissions = [
            {'supplier_name': 'Supplier X', 'amount': 100.0}
        ]
        result = generate_plain_explainer_card(commissions, 'unknown_format')
        # Should fallback to json
        parsed = json.loads(result)
        self.assertEqual(parsed[0]['supplier'], 'Supplier X')

    def test_extreme_boundary_scenarios(self):
        commissions = [
            {'supplier_name': 'Supplier Neg', 'amount': -500.5},
            {'supplier_name': 'Supplier Neg', 'amount': -100.5},
            {'supplier_name': 'Supplier Huge', 'amount': 1e12},
            {'supplier_name': 'Supplier Zero', 'amount': 0.0},
            {'supplier_name': 'Supplier Float', 'amount': 0.1 + 0.2} # tests rounding to 0.3
        ]
        result = generate_plain_explainer_card(commissions, 'json')
        parsed = json.loads(result)

        self.assertEqual(len(parsed), 4)

        # We need to sort or find properly, let's turn it into a dict for easy asserting
        parsed_dict = {item['supplier']: item['total_commission'] for item in parsed}

        self.assertEqual(parsed_dict['Supplier Neg'], -601.0)
        self.assertEqual(parsed_dict['Supplier Huge'], 1000000000000.0)
        self.assertEqual(parsed_dict['Supplier Zero'], 0.0)
        self.assertEqual(parsed_dict['Supplier Float'], 0.3)

if __name__ == '__main__':
    unittest.main()

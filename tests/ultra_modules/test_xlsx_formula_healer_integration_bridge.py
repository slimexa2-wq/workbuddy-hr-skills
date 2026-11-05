import unittest
from ultra_modules.xlsx_formula_healer_integration_bridge import XlsxFormulaHealerIntegrationBridge

class TestXlsxFormulaHealerIntegrationBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = XlsxFormulaHealerIntegrationBridge()
        self.bridge_strict = XlsxFormulaHealerIntegrationBridge(strict_mode=True, fallback_value=0)

    def test_normal_inputs_and_healing(self):
        # Normal healing data
        data = [
            {"name": "Alice", "score": "95", "error": "#REF!"},
            {"name": "Bob", "score": "80", "error": "#DIV/0!"},
            {"name": "Charlie", "score": " 100 ", "error": "#VALUE!"}
        ]
        healed = self.bridge.heal_data(data)
        self.assertEqual(healed[0]["error"], 0)
        self.assertEqual(healed[1]["error"], 0)
        self.assertEqual(healed[2]["error"], 0)

        converted = self.bridge.scan_and_convert_text_numbers(healed)
        self.assertEqual(converted[0]["score"], 95)
        self.assertEqual(converted[1]["score"], 80)
        self.assertEqual(converted[2]["score"], 100)

    def test_dirty_data_self_healing(self):
        dirty_data = [
            ["#REF!", " 10.5 ", "valid"],
            ["#NAME?", "#NULL!", "  -20 "],
            "#NUM!"
        ]
        healed = self.bridge.heal_data(dirty_data)
        self.assertEqual(healed[0], [0, " 10.5 ", "valid"])
        self.assertEqual(healed[1], [0, 0, "  -20 "])
        self.assertEqual(healed[2], 0)

        converted = self.bridge.scan_and_convert_text_numbers(healed)
        self.assertEqual(converted[0], [0, 10.5, "valid"])
        self.assertEqual(converted[1], [0, 0, -20])
        self.assertEqual(converted[2], 0)

    def test_missing_parameter_default_fallbacks(self):
        bridge_default = XlsxFormulaHealerIntegrationBridge(fallback_value=None, strict_mode=None, schema_threshold=None)
        self.assertEqual(bridge_default.fallback_value, 0)
        self.assertFalse(bridge_default.strict_mode)
        self.assertEqual(bridge_default.schema_threshold, 0.8)

        self.assertEqual(bridge_default.process_payload(None), [])
        self.assertEqual(bridge_default.heal_data(None), [])
        self.assertEqual(bridge_default.scan_and_convert_text_numbers(None), [])
        self.assertEqual(bridge_default.bridge_schema(None, ["key"]), [])
        self.assertEqual(bridge_default.bridge_schema({"a": 1}, None), {"a": 1})

    def test_schema_version_auto_forward_compatibility(self):
        old_data = [
            {"user_nm": "Alice", "user_age": 30},
            {"user_nm": "Bob", "user_age": 25}
        ]
        target_schema = ["user_name", "user_age", "department"]

        # Non-strict mode
        bridged = self.bridge.bridge_schema(old_data, target_schema)
        self.assertEqual(bridged[0]["user_name"], "Alice")
        self.assertEqual(bridged[0]["user_age"], 30)
        self.assertEqual(bridged[0]["department"], 0) # fallback value

        # Strict mode
        bridged_strict = self.bridge_strict.bridge_schema(old_data, target_schema)
        self.assertEqual(bridged_strict[0]["user_name"], "Alice")
        self.assertEqual(bridged_strict[0]["user_age"], 30)
        self.assertIsNone(bridged_strict[0]["department"]) # strict mode fallback

    def test_extreme_boundary_cases_and_process_payload(self):
        # Empty inputs
        self.assertEqual(self.bridge.process_payload([]), [])
        self.assertEqual(self.bridge.process_payload({}), {})

        # Process payload integration test
        complex_payload = [
            {"emp_id": " 123 ", "emp_name": "Dave", "salary": "#DIV/0!", "bonus": "  1000.50 "},
            {"emp_id": " 124 ", "emp_name": "Eve", "salary": " 5000 ", "bonus": "#REF!"}
        ]
        target_keys = ["emp_id", "emp_name", "salary", "bonus", "tax"]

        processed = self.bridge.process_payload(complex_payload, target_keys)

        self.assertEqual(processed[0]["emp_id"], 123)
        self.assertEqual(processed[0]["emp_name"], "Dave")
        self.assertEqual(processed[0]["salary"], 0)
        self.assertEqual(processed[0]["bonus"], 1000.5)
        self.assertEqual(processed[0]["tax"], 0)

        self.assertEqual(processed[1]["emp_id"], 124)
        self.assertEqual(processed[1]["emp_name"], "Eve")
        self.assertEqual(processed[1]["salary"], 5000)
        self.assertEqual(processed[1]["bonus"], 0)
        self.assertEqual(processed[1]["tax"], 0)

if __name__ == "__main__":
    unittest.main()

import unittest
from ultra_modules.zero_comment_null_guard_audit_trace import ExcelDeliveryPrechecker, one_click_precheck

class TestExcelDeliveryPrechecker(unittest.TestCase):
    def test_normal_flow(self):
        """Test with valid normal data."""
        data = [
            {"id": 1, "value": 100, "name": "Item A"},
            {"id": 2, "value": 200, "name": "Item B"}
        ]
        result = one_click_precheck(data)
        self.assertEqual(len(result["clean_data"]), 2)
        self.assertEqual(result["clean_data"][0]["value"], 100)
        self.assertEqual(len(result["highlights"]), 0)
        self.assertTrue("audit_trace_id" in result)
        self.assertTrue(len(result["audit_logs"]) > 0)

    def test_zero_comment_policy(self):
        """Test the removal of comment fields (case-insensitive)."""
        data = [
            {"id": 1, "value": 100, "comment": "A note", "User_COMMENT_1": "Another note", "name": "Item A"}
        ]
        result = one_click_precheck(data)
        clean_row = result["clean_data"][0]
        self.assertNotIn("comment", clean_row)
        self.assertNotIn("User_COMMENT_1", clean_row)
        self.assertIn("id", clean_row)
        self.assertEqual(len(result["highlights"][0]["changes"]), 2)

    def test_null_guard_autofill(self):
        """Test numeric column null guard and type normalization."""
        data = [
            {"id": 1, "score": None, "price": "", "count": "10", "ratio": "1.5"},
            {"id": 2, "score": 90, "price": "invalid", "count": 20, "ratio": 2.5}
        ]
        # explicitly providing numeric columns
        result = one_click_precheck(data, numeric_columns=["score", "price", "count", "ratio"])

        row1 = result["clean_data"][0]
        self.assertEqual(row1["score"], 0)
        self.assertEqual(row1["price"], 0)
        self.assertEqual(row1["count"], 10)
        self.assertEqual(row1["ratio"], 1.5)

        row2 = result["clean_data"][1]
        self.assertEqual(row2["price"], 0) # Self-healing dirty string

        self.assertTrue(len(result["highlights"]) > 0)

    def test_dirty_data_self_healing_and_deduplication(self):
        """Test self healing of invalid rows and deduplication based on keys."""
        data = [
            {"id": 1, "value": 100},
            "invalid_row_string",
            None,
            {"id": 1, "value": 100}, # Duplicate
            {"id": 2, "value": 200}
        ]
        result = one_click_precheck(data, deduplicate_keys=["id"])
        clean_data = result["clean_data"]

        self.assertEqual(len(clean_data), 2)
        self.assertEqual(clean_data[0]["id"], 1)
        self.assertEqual(clean_data[1]["id"], 2)

    def test_missing_parameter_default_fallback(self):
        """Test the zero-configuration auto-fallback when parameters are missing."""
        # Missing data parameter
        result_empty = one_click_precheck()
        self.assertEqual(result_empty["clean_data"], [])

        # Numeric columns inferred automatically
        data = [
            {"id": 1, "count": 10, "label": "A"},
            {"id": 2, "count": None, "label": "B"}
        ]
        result = one_click_precheck(data)
        clean_data = result["clean_data"]
        # "count" should be inferred as numeric since row 1 has int, and row 2's None should become 0
        self.assertEqual(clean_data[1]["count"], 0)

        # Verify deduplicate default (no deduplication)
        data_dup = [{"id": 1}, {"id": 1}]
        result_dup = one_click_precheck(data_dup)
        self.assertEqual(len(result_dup["clean_data"]), 2)

    def test_extreme_edge_cases(self):
        """Test extreme scenarios with completely empty dicts and unexpected structures."""
        data = [
            {},
            {"comment": "only comment"},
            {"val": None},
            {"val": ""}
        ]
        result = one_click_precheck(data, numeric_columns=["val"])
        clean_data = result["clean_data"]

        self.assertEqual(len(clean_data), 4)
        self.assertEqual(clean_data[0], {})
        self.assertEqual(clean_data[1], {})
        self.assertEqual(clean_data[2]["val"], 0)
        self.assertEqual(clean_data[3]["val"], 0)

if __name__ == '__main__':
    unittest.main()

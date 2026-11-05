import unittest
import time
from unittest.mock import patch
from ultra_modules.monday_3reports_runner_self_healing_guard import (
    Monday3ReportsRunner,
    generate,
    undo,
    get_current_state,
    _runner
)

class TestMonday3ReportsRunnerSelfHealingGuard(unittest.TestCase):
    def setUp(self):
        # Reset the global instance state for isolated tests
        _runner.current_reports_state = None
        _runner.snapshots.clear()

    def test_normal_operation_and_defaults(self):
        """Test basic normal operations and missing parameter defaults."""
        data = [{"id": 1, "name": "Test User"}, {"id": 2, "name": "Another User"}]
        result = generate(data)

        self.assertTrue(result["success"])
        self.assertIn("项目需求", result["reports"])
        self.assertIn("学生工", result["reports"])
        self.assertIn("存量校招绩效", result["reports"])

        for r_type in ["项目需求", "学生工", "存量校招绩效"]:
            self.assertEqual(result["reports"][r_type]["record_count"], 2)

    def test_dirty_data_self_healing(self):
        """Test self-healing mechanisms for malformed inputs."""
        # 1. Invalid JSON string
        res1 = generate("dirty string that is not json")
        self.assertEqual(res1["reports"]["项目需求"]["record_count"], 1)
        self.assertEqual(res1["reports"]["项目需求"]["data_preview"][0]["raw_text"], "dirty string that is not json")

        # 2. Empty string
        res2 = generate("   ")
        self.assertEqual(res2["reports"]["项目需求"]["record_count"], 0)

        # 3. Single Dict
        res3 = generate({"dirty_key ": " dirty_val "})
        self.assertEqual(res3["reports"]["项目需求"]["record_count"], 1)
        self.assertEqual(res3["reports"]["项目需求"]["data_preview"][0]["dirty_key"], "dirty_val")

        # 4. Mix of invalid types inside list
        res4 = generate([None, {"a": "b"}, 42, "hello"])
        self.assertEqual(res4["reports"]["项目需求"]["record_count"], 3) # None is skipped
        self.assertEqual(res4["reports"]["项目需求"]["data_preview"][1], {"value": "42"})
        self.assertEqual(res4["reports"]["项目需求"]["data_preview"][2], {"value": "hello"})

        # 5. Invalid JSON but looks like list (isinstance str)
        res5 = generate('["valid", "json"]')
        self.assertEqual(res5["reports"]["项目需求"]["record_count"], 2)

        # 6. Not a list, not string, not dict (e.g. integer)
        res6 = generate(123)
        self.assertEqual(res6["reports"]["项目需求"]["record_count"], 1)
        self.assertEqual(res6["reports"]["项目需求"]["data_preview"][0], {"value": 123})

        # 7. List of list
        res7 = generate([["a", "b"]])
        self.assertEqual(res7["reports"]["项目需求"]["record_count"], 1)
        self.assertEqual(res7["reports"]["项目需求"]["data_preview"][0], {"value": "['a', 'b']"})

        # 8. List with dict containing integer value (should not string-strip integers)
        res8 = generate([{"a": 1}])
        self.assertEqual(res8["reports"]["项目需求"]["data_preview"][0], {"a": 1})

    def test_missing_parameters_fallback(self):
        """Test parameter defaults logic and edge cases."""
        # report_types is string instead of list
        res = generate([], report_types="wrong_type")
        self.assertIn("项目需求", res["reports"]) # Falls back to defaults

        # report_types contains empty strings
        res2 = generate([], report_types=["", "   ", "custom_report"])
        self.assertIn("custom_report", res2["reports"])
        self.assertNotIn("项目需求", res2["reports"])

        # report_types contains only empty strings
        res3 = generate([], report_types=["", "   "])
        self.assertIn("项目需求", res3["reports"]) # Falls back to defaults

        # missing both raw_data and report_types
        res4 = generate()
        self.assertTrue(res4["success"])
        self.assertEqual(res4["reports"]["项目需求"]["record_count"], 0)

    def test_undo_mechanism(self):
        """Test the 5-second one-click undo mechanism."""
        # Initial empty state
        self.assertIsNone(get_current_state())

        # Action 1
        generate([{"v": 1}])
        state1 = get_current_state()
        self.assertIsNotNone(state1)
        self.assertEqual(state1["项目需求"]["record_count"], 1)

        # Action 2
        generate([{"v": 1}, {"v": 2}])
        state2 = get_current_state()
        self.assertEqual(state2["项目需求"]["record_count"], 2)

        # Undo Action 2
        undo_res = undo()
        self.assertTrue(undo_res["success"])
        self.assertEqual(get_current_state(), state1)

        # Undo Action 1
        undo_res2 = undo()
        self.assertTrue(undo_res2["success"])
        self.assertIsNone(get_current_state())

        # Undo when empty
        undo_res3 = undo()
        self.assertFalse(undo_res3["success"])
        self.assertEqual(undo_res3["message"], "No snapshots available to undo.")

    def test_undo_expired(self):
        """Test undo behavior when the 5-second window has expired."""
        generate([{"v": 1}])

        # Mock time.time to simulate expiration
        with patch('time.time', return_value=time.time() + 6.0):
            undo_res = undo()
            self.assertFalse(undo_res["success"])
            self.assertEqual(undo_res["message"], "Undo time window (5 seconds) expired.")
            self.assertIsNotNone(get_current_state()) # State should remain unchanged

    def test_extreme_boundaries(self):
        """Test boundary conditions like snapshot limits."""
        runner = Monday3ReportsRunner(max_snapshots=2)

        runner.generate_reports([1])
        runner.generate_reports([1, 2])
        runner.generate_reports([1, 2, 3])

        # Snapshot limit is 2, so the first action is gone
        self.assertEqual(len(runner.snapshots), 2)

        runner.undo_last_generation()
        self.assertEqual(runner.current_reports_state["项目需求"]["record_count"], 2)

        runner.undo_last_generation()
        self.assertEqual(runner.current_reports_state["项目需求"]["record_count"], 1)

        undo_res = runner.undo_last_generation()
        self.assertFalse(undo_res["success"])

if __name__ == '__main__':
    unittest.main()

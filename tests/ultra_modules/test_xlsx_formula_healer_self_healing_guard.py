import unittest
import time
from ultra_modules.xlsx_formula_healer_self_healing_guard import XlsxFormulaHealerSelfHealingGuard

class TestXlsxFormulaHealerSelfHealingGuard(unittest.TestCase):

    def setUp(self):
        self.guard = XlsxFormulaHealerSelfHealingGuard(fallback_value=0, undo_window_seconds=0.1)

    def test_normal_operations(self):
        """Test that normal, clean data remains unchanged."""
        data = [[1, 2.5, "Valid String"], {"key": 42}]
        deps = {"A": ["B"], "B": ["C"], "C": []}

        healed_data, healed_deps = self.guard.heal(data, deps)

        self.assertEqual(healed_data, data)
        self.assertEqual(healed_deps, deps)

    def test_dirty_data_self_healing(self):
        """Test healing of Excel errors and conversion of text-as-numbers."""
        data = [
            "#REF!",
            "#DIV/0!",
            "  123  ",
            "45.67",
            {"val": "#VALUE!"},
            "#N/A", "#NAME?", "#NUM!", "#NULL!"
        ]
        expected_data = [
            0,
            0,
            123,
            45.67,
            {"val": 0},
            0, 0, 0, 0
        ]

        healed_data, healed_deps = self.guard.heal(data)
        self.assertEqual(healed_data, expected_data)
        self.assertEqual(healed_deps, {})

    def test_circular_references_broken(self):
        """Test that circular dependencies are silently broken."""
        deps = {
            "A": ["B"],
            "B": ["C"],
            "C": ["A", "D"], # Cycle: C -> A -> B -> C
            "D": ["D"], # Self-loop
            "E": "F" # Malformed edge list (string instead of list)
        }

        # Expected: A->B, B->C, C->D (C->A dropped), D->[] (D->D dropped), E->["F"]
        expected_deps = {
            "A": ["B"],
            "B": ["C"],
            "C": ["D"],
            "D": [],
            "E": ["F"]
        }

        _, healed_deps = self.guard.heal(None, deps)
        self.assertEqual(healed_deps, expected_deps)

    def test_default_fallbacks(self):
        """Test default fallbacks for None, dict keys, and missing params."""
        # Custom fallback
        guard2 = XlsxFormulaHealerSelfHealingGuard(fallback_value=None, undo_window_seconds=None)
        self.assertEqual(guard2.fallback_value, 0)
        self.assertEqual(guard2.undo_window_seconds, 5.0)

        guard_custom = XlsxFormulaHealerSelfHealingGuard(fallback_value=-1)
        data = {"err": "#REF!"}
        healed_data, _ = guard_custom.heal(data)
        self.assertEqual(healed_data, {"err": -1})

        # None params
        healed_data, healed_deps = self.guard.heal(None, None)
        self.assertIsNone(healed_data)
        self.assertEqual(healed_deps, {})

        # Invalid deps
        _, healed_deps2 = self.guard.heal(None, ["not", "a", "dict"])
        self.assertEqual(healed_deps2, {})

        # Deps with None values
        deps = {"A": None, "B": []}
        _, healed_deps3 = self.guard.heal(None, deps)
        self.assertEqual(healed_deps3, {"A": [], "B": []})

        # Test cross edge case for full coverage
        deps2 = {"A": ["B", "C"], "B": ["C"], "C": []}
        _, healed_deps4 = self.guard.heal(None, deps2)
        self.assertEqual(healed_deps4, deps2)

        # Test full branch coverage on final cleanups
        # To hit `node not in final_deps` it has to be unvisited or dropped
        # We can drop by modifying final_deps logic directly or by unvisitable nodes
        deps3 = {"A": ["B"], "B": [], "C": []}
        _, healed_deps5 = self.guard.heal(None, deps3)
        self.assertEqual(healed_deps5, {"A": ["B"], "B": [], "C": []})

        deps4 = {"A": None}
        _, healed_deps6 = self.guard.heal(None, deps4)
        self.assertEqual(healed_deps6, {"A": []})

    def test_undo_and_expiration(self):
        """Test that one-click undo works within the window and expires afterwards."""
        data = ["#REF!"]
        deps = {"A": ["A"]}

        # No snapshot yet
        undo_data, undo_deps = self.guard.undo()
        self.assertIsNone(undo_data)
        self.assertIsNone(undo_deps)

        # Heal and snapshot
        self.guard.heal(data, deps)

        # Undo within window (0.1s)
        undo_data, undo_deps = self.guard.undo()
        self.assertEqual(undo_data, data)
        self.assertEqual(undo_deps, deps)

        # Snapshot consumed
        undo_data2, undo_deps2 = self.guard.undo()
        self.assertIsNone(undo_data2)
        self.assertIsNone(undo_deps2)

        # Expiration test
        self.guard.heal(data, deps)
        time.sleep(0.15) # Wait for expiration
        undo_data3, undo_deps3 = self.guard.undo()
        self.assertIsNone(undo_data3)
        self.assertIsNone(undo_deps3)

if __name__ == '__main__':
    unittest.main()

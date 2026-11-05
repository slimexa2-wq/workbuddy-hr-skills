import unittest
from ultra_modules.xlsx_formula_healer_core_engine import XlsxFormulaHealerCoreEngine

class TestXlsxFormulaHealerCoreEngine(unittest.TestCase):
    def test_default_fallback(self):
        """Test missing param default fallback (strict_mode and fallback_value defaults)."""
        engine = XlsxFormulaHealerCoreEngine(fallback_value=None, strict_mode=None)
        self.assertEqual(engine.fallback_value, 0)
        self.assertFalse(engine.strict_mode)

        # Test healing a matrix with default fallback
        dirty_data = [["Normal", "#DIV/0!"], ["#REF!", 123]]
        healed = engine.heal_error_values(dirty_data)
        self.assertEqual(healed, [["Normal", 0], [0, 123]])

    def test_normal_data_healing(self):
        """Test normal data healing."""
        engine = XlsxFormulaHealerCoreEngine(fallback_value=-1)
        data = ["Normal", 42, 3.14]
        healed = engine.heal_error_values(data)
        self.assertEqual(healed, ["Normal", 42, 3.14])

        healed_text = engine.heal_text_as_number(data)
        self.assertEqual(healed_text, ["Normal", 42, 3.14])

    def test_dirty_data_auto_healing(self):
        """Test dirty data auto-healing (text as number)."""
        engine = XlsxFormulaHealerCoreEngine()
        data = [" 42 ", "3.14", "not_a_number", "#DIV/0!"]
        healed = engine.heal_text_as_number(data)
        self.assertEqual(healed, [42, 3.14, "not_a_number", "#DIV/0!"])

        matrix_data = [[" 100 "], [" 2.5 "], [" text "]]
        healed_matrix = engine.heal_text_as_number(matrix_data)
        self.assertEqual(healed_matrix, [[100], [2.5], [" text "]])

    def test_extreme_boundaries_and_matrices(self):
        """Test extreme boundaries and empty structures."""
        engine = XlsxFormulaHealerCoreEngine()
        self.assertEqual(engine.heal_error_values([]), [])
        self.assertEqual(engine.heal_error_values(None), [])
        self.assertEqual(engine.heal_error_values("not a list"), "not a list")

        self.assertEqual(engine.heal_text_as_number([]), [])
        self.assertEqual(engine.heal_text_as_number(None), [])
        self.assertEqual(engine.heal_text_as_number("not a list"), "not a list")

    def test_circular_reference_detection(self):
        """Test circular reference detection (Tarjan's SCC)."""
        engine = XlsxFormulaHealerCoreEngine()

        # Test empty dependencies
        self.assertEqual(engine.detect_circular_dependencies({}), [])
        self.assertEqual(engine.detect_circular_dependencies(None), [])

        # Test self-loop
        deps_self_loop = {"A": ["A"]}
        cycles = engine.detect_circular_dependencies(deps_self_loop)
        self.assertEqual(len(cycles), 1)
        self.assertIn("A", cycles[0])

        # Test larger cycle
        deps_cycle = {
            "A": ["B"],
            "B": ["C"],
            "C": ["A"],
            "D": ["E"],
            "E": []
        }
        cycles2 = engine.detect_circular_dependencies(deps_cycle)
        self.assertEqual(len(cycles2), 1)
        self.assertTrue(set(["A", "B", "C"]).issubset(set(cycles2[0])))
        self.assertEqual(len(cycles2[0]), 3)

        # Test complex cycles
        deps_complex = {
            "1": ["2"],
            "2": ["3"],
            "3": ["1"],
            "4": ["5"],
            "5": ["6"],
            "6": ["4"],
            "7": ["8"]
        }
        cycles3 = engine.detect_circular_dependencies(deps_complex)
        self.assertEqual(len(cycles3), 2)

if __name__ == '__main__':
    unittest.main()

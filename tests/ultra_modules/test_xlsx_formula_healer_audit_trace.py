import unittest
from ultra_modules.xlsx_formula_healer_audit_trace import ExcelErrorHealer

class TestExcelErrorHealer(unittest.TestCase):

    def setUp(self):
        self.healer = ExcelErrorHealer()

    def test_normal_flow_no_error(self):
        """测试正常流程，数据中没有错误"""
        row_data = [100, 200, "Valid String", 400]
        healed_row = self.healer.heal_row(row_data)

        self.assertEqual(healed_row, row_data)
        self.assertEqual(len(self.healer.get_audit_trail()), 0)
        self.assertEqual(len(self.healer.get_diff_highlight()), 0)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈：处理#REF!, #DIV/0!, #VALUE! 等"""
        row_data = ["Data1", "#REF! Error here", 300, "Result is #DIV/0!", "#VALUE!"]
        # Replace errors with default 0
        healed_row = self.healer.heal_row(row_data, default_fallback=0)

        # Valid data stays the same
        self.assertEqual(healed_row[0], "Data1")
        self.assertEqual(healed_row[2], 300)

        # Error data gets replaced
        self.assertEqual(healed_row[1], "0 Error here")
        self.assertEqual(healed_row[3], "Result is 0")
        self.assertEqual(healed_row[4], "0")

        # Check audit trail
        audit = self.healer.get_audit_trail()
        self.assertEqual(len(audit), 3)
        self.assertEqual(audit[0]['error_type'], '#REF!')
        self.assertEqual(audit[1]['error_type'], '#DIV/0!')
        self.assertEqual(audit[2]['error_type'], '#VALUE!')

        # Check diff highlights
        diffs = self.healer.get_diff_highlight()
        self.assertEqual(len(diffs), 3)
        self.assertIn("[#REF!] -> [0 Error here]", diffs[0]['highlight'])

    def test_missing_parameter_fallback(self):
        """测试缺参默认兜底与容错（如传入 None 等）"""
        # Test 1: Passing None for row_data
        healed_row = self.healer.heal_row(None)
        self.assertEqual(healed_row, [])

        # Test 2: Passing a None element inside row_data
        row_data = ["Valid", None, "#N/A"]
        healed_row = self.healer.heal_row(row_data) # Default fallback is ""
        self.assertEqual(healed_row[0], "Valid")
        self.assertEqual(healed_row[1], "")
        self.assertEqual(healed_row[2], "") # #N/A replaced by ""

        audit = self.healer.get_audit_trail()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]['error_type'], '#N/A')
        self.assertEqual(audit[0]['original_value'], '#N/A')

    def test_circular_reference(self):
        """测试循环引用错误处理"""
        # Circular refs can sometimes come as a specific string marker
        row_data = ["Data", "Warning: CIRCULAR_REF detected", 10]
        healed_row = self.healer.heal_row(row_data, default_fallback="ERROR_RESOLVED")

        self.assertEqual(healed_row[0], "Data")
        self.assertEqual(healed_row[1], "ERROR_RESOLVED")
        self.assertEqual(healed_row[2], 10)

        audit = self.healer.get_audit_trail()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]['error_type'], 'CIRCULAR_REF')

    def test_extreme_edge_cases(self):
        """测试极端边界：处理字典、非列表/字典的单体数据"""
        # Dictionary input
        dict_data = {"col_A": 100, "col_B": "#NAME?", "col_C": "Normal"}
        healed_dict = self.healer.heal_row(dict_data, default_fallback=-1)

        self.assertEqual(healed_dict["col_A"], 100)
        self.assertEqual(healed_dict["col_B"], "-1")
        self.assertEqual(healed_dict["col_C"], "Normal")

        # Single value input (Fault tolerance fallback)
        single_val = "#NUM! Error"
        healed_single = self.healer.heal_row(single_val, default_fallback="CLEAN")

        self.assertEqual(healed_single, ["CLEAN Error"])

        audit = self.healer.get_audit_trail()
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]['error_type'], '#NAME?')
        self.assertEqual(audit[1]['error_type'], '#NUM!')

if __name__ == '__main__':
    unittest.main()

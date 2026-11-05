import unittest
import openpyxl
from openpyxl.comments import Comment
from ultra_modules.zero_comment_null_guard_integration_bridge import integrate_and_bridge_excel, _normalize_header

class TestZeroCommentNullGuardIntegrationBridge(unittest.TestCase):

    def setUp(self):
        # Create a fresh workbook for each test
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active

    def test_normal_operation_and_basic_schema_mapping(self):
        # Test basic schema mapping and null guard combined
        self.ws.append(["Emp_Name", "Emp_Age"])
        self.ws.append(["Alice", None])
        self.ws.append(["Bob", "null"])

        # Add comment
        self.ws["A2"].comment = Comment("test comment", "author")

        target_headers = ["EmpName", "EmpAge"]

        res_wb = integrate_and_bridge_excel(self.wb, target_headers, default_fill=0)
        res_ws = res_wb.active

        # Check headers mapped
        self.assertEqual(res_ws["A1"].value, "EmpName")
        self.assertEqual(res_ws["B1"].value, "EmpAge")

        # Check nulls handled
        self.assertEqual(res_ws["B2"].value, 0)
        self.assertEqual(res_ws["B3"].value, 0)

        # Check comment stripped
        self.assertIsNone(res_ws["A2"].comment)

    def test_dirty_data_self_healing(self):
        # Test with messy target headers and messy cell data
        self.ws.append([" messy_header! "])
        self.ws.append(["NaN"])
        self.ws.append(["undefined"])
        self.ws.append([""])

        target_headers = ["MessyHeader"]

        res_wb = integrate_and_bridge_excel(self.wb, target_headers, default_fill=999)
        res_ws = res_wb.active

        self.assertEqual(res_ws["A1"].value, "MessyHeader")
        self.assertEqual(res_ws["A2"].value, 999)
        self.assertEqual(res_ws["A3"].value, 999)
        self.assertEqual(res_ws["A4"].value, 999)

    def test_missing_parameter_fallbacks(self):
        # 缺参默认兜底

        # 1. No workbook, no headers
        res_wb1 = integrate_and_bridge_excel()
        self.assertIsInstance(res_wb1, openpyxl.Workbook)
        self.assertEqual(res_wb1.active["A1"].value, None)

        # 2. No workbook, has headers
        res_wb2 = integrate_and_bridge_excel(target_headers=["Test"])
        self.assertEqual(res_wb2.active["A1"].value, "Test")

        # 3. Has workbook, no headers
        self.ws.append(["A"])
        self.ws.append([None])
        res_wb3 = integrate_and_bridge_excel(self.wb)
        self.assertEqual(res_wb3.active["A2"].value, 0)

    def test_fuzzy_schema_mapping_rules(self):
        # Test version prefix removal and fuzziness
        self.assertEqual(_normalize_header("v1_Employee_Name"), "employeename")
        self.assertEqual(_normalize_header("old_salary_amt"), "salaryamt")
        self.assertEqual(_normalize_header("new_DEPARTMENT"), "department")
        self.assertEqual(_normalize_header("  Bonus  % "), "bonus")

        # Test it applies in bridge
        self.ws.append(["v2_employee_id", "OLD_Dept!Name", "New_Location "])
        target_headers = ["EmployeeId", "DeptName", "Location"]

        res_wb = integrate_and_bridge_excel(self.wb, target_headers)
        res_ws = res_wb.active

        self.assertEqual(res_ws["A1"].value, "EmployeeId")
        self.assertEqual(res_ws["B1"].value, "DeptName")
        self.assertEqual(res_ws["C1"].value, "Location")

    def test_extreme_boundaries(self):
        # Extreme boundaries
        # Empty workbook with no rows
        wb_empty = openpyxl.Workbook()
        res_wb = integrate_and_bridge_excel(wb_empty, target_headers=["A"])
        self.assertEqual(res_wb, wb_empty) # Returns same workbook

        # Invalid target headers
        self.ws.append(["Valid"])
        res_wb2 = integrate_and_bridge_excel(self.wb, target_headers=[None, "", 123])
        self.assertEqual(res_wb2.active["A1"].value, "Valid") # Should just apply core engine, not fail

if __name__ == '__main__':
    unittest.main()

import os
import unittest
import openpyxl
from collections import namedtuple
import sys
import importlib.machinery

# add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import agent-preflight-guard dynamically
loader = importlib.machinery.SourceFileLoader("agent_preflight_guard", os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'guards', 'agent-preflight-guard')))
agent_preflight_guard = loader.load_module()

class TestAgentPreflightGuard(unittest.TestCase):
    def setUp(self):
        self.test_xlsx = "test_merged.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "周度数据表"

        # Add some headers
        ws["A1"] = "Category"
        ws["B1"] = "Subcategory"
        ws["C1"] = "Data1"
        ws["D1"] = "Data2"
        ws["E1"] = "Data3"

        # Add data to be checked (row 3 onwards)
        ws["A3"] = "Row1"
        ws["B3"] = "Row1_Sub"
        ws["C3"] = 10
        ws["D3"] = 20
        # E3 is merged with F3
        ws["E3"] = 30
        ws.merge_cells('E3:F3')
        # Set values for the rest of columns 3-9 to avoid unwanted violations
        ws["G3"] = 40
        ws["H3"] = 50
        ws["I3"] = 60

        # Row 4 with empty violation
        ws["A4"] = "Row2"
        ws["B4"] = "Row2_Sub"
        ws["C4"] = 15
        ws["D4"] = "" # Empty violation
        ws["E4"] = 0
        ws["F4"] = 0
        ws["G4"] = 0
        ws["H4"] = 0
        ws["I4"] = 0

        wb.save(self.test_xlsx)

    def tearDown(self):
        if os.path.exists(self.test_xlsx):
            os.remove(self.test_xlsx)

    def test_xlsx_check_merged_cells(self):
        Args = namedtuple('Args', ['file', 'sheet', 'strict_all_comments', 'json'])
        args_json = Args(file=self.test_xlsx, sheet=None, strict_all_comments=False, json=True)

        import io

        captured_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            # We mock sys.argv or use the function directly
            ret = agent_preflight_guard.cmd_xlsx_check(args_json)
        finally:
            sys.stdout = original_stdout

        output = captured_output.getvalue()
        import json
        data = json.loads(output)

        self.assertFalse(data["gates"]["2_numeric_no_blanks"]["passed"])

        violations = data["gates"]["2_numeric_no_blanks"]["violations"]

        violation_cells = [v["cell"] for v in violations]
        self.assertNotIn("F3", violation_cells)

        self.assertIn("D4", violation_cells)

if __name__ == "__main__":
    unittest.main()

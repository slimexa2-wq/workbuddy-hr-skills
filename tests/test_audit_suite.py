import unittest
import openpyxl
import os
import sqlite3
import sys
import json
import zipfile

sys.path.append("skills/supplier-commission-audit/scripts")
sys.path.append("skills/periodic-resource-reports/scripts")

import sync_policy_sqlite
import periodic_reports_suite
import fast_index_builder
import ooxml_append

class TestAuditSuite(unittest.TestCase):
    def setUp(self):
        self.share_root = "test_share_root_suite"
        self.batch_dir = "test_batch_dir_suite"
        self.out_dir = "test_out_dir_suite"
        self.db_path = "test_policy_suite.db"
        self.wb_path = "test_wb_suite.xlsx"

        os.makedirs(self.share_root, exist_ok=True)
        os.makedirs(self.batch_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(self.share_root):
            shutil.rmtree(self.share_root)
        if os.path.exists(self.batch_dir):
            shutil.rmtree(self.batch_dir)
        if os.path.exists(self.out_dir):
            shutil.rmtree(self.out_dir)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.wb_path):
            os.remove(self.wb_path)
        if os.path.exists("test_dst_suite.xlsx"):
            os.remove("test_dst_suite.xlsx")
        if os.path.exists("test_demand.xlsx"):
            os.remove("test_demand.xlsx")

    def test_verify_zero_comments_and_blanks(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws["A1"] = "Value"
        ws["A2"] = None # Blank
        from openpyxl.comments import Comment
        ws["A1"].comment = Comment("Test comment", "Author")

        strict_grid_ranges = {"Sheet1": [(1, 2, 1, 1)]}
        res = periodic_reports_suite.verify_zero_comments_and_blanks(wb, strict_grid_ranges)
        self.assertEqual(res["comments_removed"], 1)
        self.assertFalse(res["passed"])
        self.assertIn("Sheet1!A2", res["blank_cells"])

        # Numeric nulls filled with 0 should pass
        ws["A2"] = 0
        res = periodic_reports_suite.verify_zero_comments_and_blanks(wb, strict_grid_ranges)
        self.assertTrue(res["passed"])

    def test_to_int(self):
        self.assertEqual(periodic_reports_suite._to_int(None), 0)
        self.assertEqual(periodic_reports_suite._to_int(10.5), 10)
        self.assertEqual(periodic_reports_suite._to_int(" 10 "), 10)
        self.assertEqual(periodic_reports_suite._to_int("/"), 0)
        self.assertEqual(periodic_reports_suite._to_int("-"), 0)
        self.assertEqual(periodic_reports_suite._to_int("abc 123"), 123)

    def test_sync_policy_sqlite(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["身份证号", "姓名", "企业", "供应商", "政策", "入职日期"])
        # Test a name with dot (boundary case)
        ws.append(["110105199001011234", "买买提·艾力", "某企业", "某供应商", "100", "2023-01-01"])

        os.makedirs(os.path.join(self.share_root, "batch1"), exist_ok=True)
        test_file = os.path.join(self.share_root, "batch1", "所有企业名单汇总.xlsx")
        wb.save(test_file)

        sync_policy_sqlite.sync_policy_db(self.share_root, self.db_path)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id_card, name FROM policy_records")
        rows = cur.fetchall()
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "110105199001011234")
        self.assertEqual(rows[0][1], "买买提·艾力")

    def test_fast_index_builder(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "TargetSheet"
        ws.append(["身份证号", "姓名", "企业"])
        ws.append(["110105199001011234", "买买提·艾力", "某企业"])
        batch_file = os.path.join(self.batch_dir, "结款工作簿.xlsx")
        wb.save(batch_file)

        target_ids, target_names = fast_index_builder.extract_targets(self.batch_dir)
        self.assertIn("110105199001011234", target_ids)
        self.assertIn("买买提·艾力", target_names)

    def test_ooxml_append(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["Col1", "Col2"])
        ws.append(["A", "B"])
        wb.save(self.wb_path)

        dst_file = "test_dst_suite.xlsx"
        sheets_audit_spec = {
            "Sheet1": {
                "header_row": 1,
                "start_col_idx": 3,
                "rows": {
                    2: ["Val1", "Val2", "Val3", "Val4", "Val5", "通过"]
                }
            }
        }
        ooxml_append.create_audited_workbook(self.wb_path, dst_file, sheets_audit_spec)

        self.assertTrue(os.path.exists(dst_file))

        wb2 = openpyxl.load_workbook(dst_file)
        ws2 = wb2["Sheet1"]
        self.assertEqual(ws2.cell(row=1, column=3).value, "工时/天数核对")
        self.assertEqual(ws2.cell(row=2, column=3).value, "Val1")
        self.assertEqual(ws2.cell(row=2, column=8).value, "通过")

class TestFormulaCorrection(unittest.TestCase):
    def test_parse_project_demand_sheet(self):
        # Create a dummy workbook simulating 《分公司企业需求动态表.xlsx》
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "2026年11月需求"

        # Populate headers and structural data to trigger the formula anomalies detection
        ws.cell(row=4, column=1, value="双流") # 区域
        ws.cell(row=4, column=2, value="大茂丰安保") # 项目
        ws.cell(row=4, column=13, value="2\n") # This contains newline, simulating text newline bug

        # Add total row
        ws.cell(row=29, column=1, value="宜宾")
        ws.cell(row=29, column=2, value="某项目")
        ws.cell(row=29, column=13, value=15)

        ws.cell(row=30, column=1, value="总计")

        # Save to temp file
        test_file = "test_demand.xlsx"
        wb.save(test_file)

        # We need another workbook for formulas
        wb_f = openpyxl.load_workbook(test_file)
        ws_f = wb_f.active
        ws_f.cell(row=30, column=13, value="=SUM(M4:M28)") # Missing row 29
        wb_f.save(test_file)

        # Call the parser
        res = periodic_reports_suite.parse_project_demand_sheet(test_file, sheet_name="2026年11月需求")

        # We expect a formula anomaly for the total row and the text newline
        anomalies = res["formula_anomalies"]

        self.assertTrue(any("含文本换行符 '2\\n'" in a for a in anomalies))
        self.assertTrue(any("总计行 M30 公式错位" in a for a in anomalies))

        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == '__main__':
    unittest.main()

import pytest
import datetime as dt
from pathlib import Path
import os
import sys

# Ensure the module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from periodic_reports_suite import excel_serial_to_date_str

def test_excel_serial_to_date_str():
    # Test valid integer serial number (e.g. 46256 -> 2026-08-22)
    # Excel base date is 1899-12-30.
    # 46256 days from 1899-12-30 = 2026-08-22
    val, converted = excel_serial_to_date_str(46256)
    assert val == "2026-08-22"
    assert converted is True

    # Test string serial number
    val, converted = excel_serial_to_date_str("46256")
    assert val == "2026-08-22"
    assert converted is True

    # Test float serial number
    val, converted = excel_serial_to_date_str(46256.0)
    assert val == "2026-08-22"
    assert converted is True

    # Test actual datetime object
    d = dt.datetime(2026, 8, 22)
    val, converted = excel_serial_to_date_str(d)
    assert val == "2026-08-22"
    assert converted is False

    # Test actual date object
    d = dt.date(2026, 8, 22)
    val, converted = excel_serial_to_date_str(d)
    assert val == "2026-08-22"
    assert converted is False

    # Test already formatted string
    val, converted = excel_serial_to_date_str("2026-08-22")
    assert val == "2026-08-22"
    assert converted is False

    # Test None
    val, converted = excel_serial_to_date_str(None)
    assert val == "/"
    assert converted is False

    # Test empty string
    val, converted = excel_serial_to_date_str("   ")
    assert val == "/"
    assert converted is False

from periodic_reports_suite import verify_zero_comments_and_blanks
import openpyxl
from openpyxl.comments import Comment

def test_verify_zero_comments_and_blanks():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Fill some data
    ws.cell(1, 1, "Data1")
    ws.cell(1, 2, "Data2")
    ws.cell(2, 1, 100)
    ws.cell(2, 2, None) # Blank cell
    ws.cell(3, 1, "") # Blank string
    ws.cell(3, 2, "Data3")

    # Add comment
    ws.cell(1, 1).comment = Comment("This is a comment", "Author")

    strict_grid_ranges = {
        "Sheet1": [(1, 3, 1, 2)]
    }

    audit = verify_zero_comments_and_blanks(wb, strict_grid_ranges)

    assert audit["comments_removed"] == 1
    assert audit["passed"] is False
    assert len(audit["blank_cells"]) == 2
    assert "Sheet1!B2" in audit["blank_cells"]
    assert "Sheet1!A3" in audit["blank_cells"]

    # Verify the comment was removed from the cell
    assert ws.cell(1, 1).comment is None

    # Fix the blanks and run again
    ws.cell(2, 2, 0)
    ws.cell(3, 1, "/")

    audit = verify_zero_comments_and_blanks(wb, strict_grid_ranges)
    assert audit["comments_removed"] == 0
    assert audit["passed"] is True
    assert len(audit["blank_cells"]) == 0

from periodic_reports_suite import compute_self_recruitment_month

def test_compute_self_recruitment_month(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    headers = ["面试日期", "姓名", "身份证", "面试企业", "供应商", "面试结果", "推荐人", "供应商政策", "入职日期", "离职日期"]
    ws.append(headers)

    rows = [
        # 0: stays >= 7 days (should pass)
        ["2026-10-01", "User1", "ID1", "CompanyA", "祥能自招", "已入职", "Ref1", "Pol", "2026-10-02", "2026-10-10"],
        # 1: stays < 7 days (should be excluded)
        ["2026-10-01", "User2", "ID2", "CompanyB", "祥能自招", "已入职", "Ref2", "Pol", "2026-10-02", "2026-10-05"],
        # 2: stays >= 7 days but year typo in leave date (should be auto-fixed and pass)
        ["2026-10-01", "User3", "ID3", "CompanyC", "祥能自招", "已入职", "Ref3", "Pol", "2026-10-02", "2020-10-10"],
        # 3: not from 祥能自招
        ["2026-10-01", "User4", "ID4", "CompanyD", "OtherSupplier", "已入职", "Ref4", "Pol", "2026-10-02", "2026-10-10"],
        # 4: invalid interview status
        ["2026-10-01", "User5", "ID5", "CompanyE", "祥能自招", "未入职", "Ref5", "Pol", "2026-10-02", ""],
        # 5: not left yet
        ["2026-10-01", "User6", "ID6", "CompanyF", "祥能自招", "已入职", "Ref6", "Pol", "2026-10-02", ""],
        # 6: month mismatch
        ["2026-09-01", "User7", "ID7", "CompanyG", "祥能自招", "已入职", "Ref7", "Pol", "2026-09-02", ""],
        # 7: Aliased referrer (135 5134 4625 -> 杨水容)
        ["2026-10-01", "User8", "ID8", "CompanyH", "祥能自招", "已入职", "135 5134 4625", "Pol", "2026-10-02", "2026-10-15"],
    ]

    for row in rows:
        ws.append(row)

    test_file = tmp_path / "test_recruit.xlsx"
    wb.save(test_file)

    res = compute_self_recruitment_month(test_file, target_month="2026-10")

    assert res["target_month"] == "2026-10"

    # User1, User3, User6, User8 should pass
    assert len(res["valid_details"]) == 4
    names = [d["name"] for d in res["valid_details"]]
    assert "User1" in names
    assert "User3" in names
    assert "User6" in names
    assert "User8" in names
    assert "User2" not in names

    assert res["valid_counts"]["Ref1"] == 1
    assert res["valid_counts"]["Ref3"] == 1
    assert res["valid_counts"]["Ref6"] == 1
    assert res["valid_counts"]["杨水容"] == 1

    # User2 should be in excluded_short_stay
    assert len(res["excluded_short_stay"]) == 1
    assert res["excluded_short_stay"][0]["name"] == "User2"

    # User5 should be in excluded_status
    assert len(res["excluded_status"]) == 1
    assert res["excluded_status"][0]["name"] == "User5"

    # User3 should be in year_typos_fixed
    assert len(res["year_typos_fixed"]) == 1
    assert res["year_typos_fixed"][0]["name"] == "User3"
    assert res["year_typos_fixed"][0]["fixed_leave_date"] == "2026-10-10"

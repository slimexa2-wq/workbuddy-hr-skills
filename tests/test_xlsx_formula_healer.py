import os
import pytest
from openpyxl import Workbook
from openpyxl.comments import Comment
from guards.xlsx_formula_healer import heal_xlsx

@pytest.fixture
def temp_xlsx_file(tmp_path):
    filepath = tmp_path / "test_data.xlsx"
    wb = Workbook()
    ws = wb.active

    # 1. Blank cell and Zero comments test
    ws['A1'] = 10
    ws['A1'].comment = Comment("This is a comment", "Author")
    ws['A2'] = None # Should be filled with 0
    ws['A3'] = "   " # Should be filled with 0

    # 2. Numeric strings with spaces/newlines test
    ws['B1'] = " 123 "
    ws['B2'] = "45.67\n"
    ws['B3'] = "Not a number"

    # 3. Formula fixes (SUM): misaligned columns
    # Formula in C5 but SUM is for B1:B4
    ws['C1'] = 1
    ws['C2'] = 2
    ws['C3'] = 3
    ws['C4'] = 4
    ws['C5'] = "=SUM(B1:B4)"

    # 4. Formula fixes (SUM): missing rows
    # Formula in D5, but SUM is for D1:D3 (missing D4)
    ws['D1'] = 10
    ws['D2'] = 20
    ws['D3'] = 30
    ws['D4'] = 40
    ws['D5'] = "=SUM(D1:D3)"

    wb.save(filepath)
    wb.close()
    return str(filepath)


def test_heal_xlsx(temp_xlsx_file):
    heal_xlsx(temp_xlsx_file)

    # Check if snapshot is created
    snapshot_path = temp_xlsx_file + ".snapshot"
    assert os.path.exists(snapshot_path)

    from openpyxl import load_workbook
    wb = load_workbook(temp_xlsx_file)
    ws = wb.active

    # Test 1: Zero comments and Blanks filled with 0
    assert ws['A1'].comment is None
    assert ws['A1'].value == 10
    assert ws['A2'].value == 0
    assert ws['A3'].value == 0

    # Test 2: Numeric strings
    assert ws['B1'].value == 123
    assert ws['B2'].value == 45.67
    assert ws['B3'].value == "Not a number"

    # Test 3: Formula fixes (misaligned column)
    assert ws['C5'].value == "=SUM(C1:C4)"

    # Test 4: Formula fixes (missing rows)
    assert ws['D5'].value == "=SUM(D1:D4)"

    wb.close()

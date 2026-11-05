#!/usr/bin/env python3
"""
OOXML 最小合入工具：严格遵循 references/workbook-preservation.md
在不改动原表任何原有单元格、公式、共享字符串、行高、列宽、合并区域、隐藏属性及外链的前提下，
向指定工作表右侧追加6列审核结果（使用 inlineStr + 追加末尾样式）。
"""
import copy
import os
import re
import zipfile
import xml.etree.ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

AUDIT_HEADERS = [
    "工时/天数核对",
    "政策核对（原始优先）",
    "金额核对（少结不增）",
    "原始数据依据",
    "审核说明",
    "审核结果",
]


def col_idx_to_letter(idx: int) -> str:
    """1-based column index to Excel column letter."""
    res = []
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        res.append(chr(ord("A") + rem))
    return "".join(reversed(res))


def col_letter_to_idx(col_str: str) -> int:
    """Excel column letter to 1-based column index."""
    res = 0
    for ch in col_str:
        if "A" <= ch <= "Z":
            res = res * 26 + (ord(ch) - ord("A") + 1)
    return res


def split_cell_ref(ref: str):
    m = re.match(r"^([A-Z]+)(\d+)$", ref)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def append_audit_styles(styles_xml_bytes: bytes):
    """
    Append 5 cellXfs styles to xl/styles.xml without altering existing indices:
    - header: bold, light blue/slate fill (#D9E1F2), thin border, wrapText
    - pass (通过): green fill (#E2EFDA), dark green text (#375623), thin border, wrapText
    - diff (差异): red fill (#FCE4D6), dark red text (#C00000), thin border, wrapText
    - pending (待核实/部分待核): yellow fill (#FFF2CC), dark ochre text (#806000), thin border, wrapText
    - zero (0元暂不审核): gray fill (#EDEDED), dark gray text (#595959), thin border, wrapText
    Returns (new_styles_xml_bytes, style_idx_map)
    """
    # Preserve namespaces
    ET.register_namespace("", MAIN_NS)
    ET.register_namespace("r", REL_NS)
    ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
    ET.register_namespace("x14ac", "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac")
    ET.register_namespace("x16r2", "http://schemas.microsoft.com/office/spreadsheetml/2015/02/main")

    root = ET.fromstring(styles_xml_bytes)

    def ensure_child(parent, tag):
        el = parent.find(f"{{{MAIN_NS}}}{tag}")
        if el is None:
            el = ET.SubElement(parent, f"{{{MAIN_NS}}}{tag}", {"count": "0"})
        return el

    fonts = ensure_child(root, "fonts")
    fills = ensure_child(root, "fills")
    borders = ensure_child(root, "borders")
    cellXfs = ensure_child(root, "cellXfs")

    # Add fonts
    font_specs = [
        ("header", True, "FF1F4E78"),
        ("pass", False, "FF274E13"),
        ("diff", False, "FFC00000"),
        ("pending", False, "FF7F6000"),
        ("zero", False, "FF595959"),
    ]
    font_ids = {}
    base_font_idx = len(fonts.findall(f"{{{MAIN_NS}}}font"))
    for i, (key, is_bold, rgb) in enumerate(font_specs):
        f_el = ET.SubElement(fonts, f"{{{MAIN_NS}}}font")
        if is_bold:
            ET.SubElement(f_el, f"{{{MAIN_NS}}}b")
        ET.SubElement(f_el, f"{{{MAIN_NS}}}sz", {"val": "10"})
        ET.SubElement(f_el, f"{{{MAIN_NS}}}color", {"rgb": rgb})
        ET.SubElement(f_el, f"{{{MAIN_NS}}}name", {"val": "微软雅黑"})
        font_ids[key] = base_font_idx + i
    fonts.attrib["count"] = str(len(fonts.findall(f"{{{MAIN_NS}}}font")))

    # Add fills
    fill_specs = [
        ("header", "FFD9E1F2"),
        ("pass", "FFE2EFDA"),
        ("diff", "FFFCE4D6"),
        ("pending", "FFFFF2CC"),
        ("zero", "FFEDEDED"),
    ]
    fill_ids = {}
    base_fill_idx = len(fills.findall(f"{{{MAIN_NS}}}fill"))
    for i, (key, rgb) in enumerate(fill_specs):
        fl_el = ET.SubElement(fills, f"{{{MAIN_NS}}}fill")
        pf_el = ET.SubElement(fl_el, f"{{{MAIN_NS}}}patternFill", {"patternType": "solid"})
        ET.SubElement(pf_el, f"{{{MAIN_NS}}}fgColor", {"rgb": rgb})
        ET.SubElement(pf_el, f"{{{MAIN_NS}}}bgColor", {"indexed": "64"})
        fill_ids[key] = base_fill_idx + i
    fills.attrib["count"] = str(len(fills.findall(f"{{{MAIN_NS}}}fill")))

    # Add thin border
    base_border_idx = len(borders.findall(f"{{{MAIN_NS}}}border"))
    b_el = ET.SubElement(borders, f"{{{MAIN_NS}}}border")
    for side in ("left", "right", "top", "bottom"):
        s_el = ET.SubElement(b_el, f"{{{MAIN_NS}}}{side}", {"style": "thin"})
        ET.SubElement(s_el, f"{{{MAIN_NS}}}color", {"rgb": "FFBFBFBF"})
    ET.SubElement(b_el, f"{{{MAIN_NS}}}diagonal")
    border_id = base_border_idx
    borders.attrib["count"] = str(len(borders.findall(f"{{{MAIN_NS}}}border")))

    # Add cellXfs
    xf_ids = {}
    base_xf_idx = len(cellXfs.findall(f"{{{MAIN_NS}}}xf"))
    for i, (key, _, _) in enumerate(font_specs):
        xf_el = ET.SubElement(
            cellXfs,
            f"{{{MAIN_NS}}}xf",
            {
                "numFmtId": "0",
                "fontId": str(font_ids[key]),
                "fillId": str(fill_ids[key]),
                "borderId": str(border_id),
                "xfId": "0",
                "applyFont": "1",
                "applyFill": "1",
                "applyBorder": "1",
                "applyAlignment": "1",
            },
        )
        ET.SubElement(
            xf_el,
            f"{{{MAIN_NS}}}alignment",
            {"vertical": "center", "wrapText": "1"},
        )
        xf_ids[key] = base_xf_idx + i
    cellXfs.attrib["count"] = str(len(cellXfs.findall(f"{{{MAIN_NS}}}xf")))

    out_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return out_bytes, xf_ids


def status_to_style_key(status_text: str) -> str:
    s = (status_text or "").strip()
    if "0元" in s or "暂不审核" in s:
        return "zero"
    if "差异" in s or "多付" in s or "不通过" in s or "错误" in s:
        return "diff"
    if "待核" in s:
        return "pending"
    if "通过" in s:
        return "pass"
    return "pending"


def inject_sheet_audit_columns(sheet_xml_bytes: bytes, header_row: int, start_col_idx: int, row_audit_map: dict, xf_ids: dict) -> bytes:
    """
    Inject 6 audit columns starting at start_col_idx (1-based) into sheet_xml_bytes.
    - header_row: 1-based row number where the 6 headers are written.
    - row_audit_map: {row_num (int): [col1_str, col2_str, col3_str, col4_str, col5_str, col6_status_str]}
    """
    ET.register_namespace("", MAIN_NS)
    ET.register_namespace("r", REL_NS)
    ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
    ET.register_namespace("x14ac", "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac")

    root = ET.fromstring(sheet_xml_bytes)
    sheetData = root.find(f"{{{MAIN_NS}}}sheetData")

    # Map existing rows and strip trailing empty cells >= start_col_idx across all rows
    rows_by_num = {}
    max_row_seen = header_row
    for r_el in sheetData.findall(f"{{{MAIN_NS}}}row"):
        r_num = int(r_el.attrib.get("r", "0"))
        rows_by_num[r_num] = r_el
        if r_num > max_row_seen:
            max_row_seen = r_num
        for c_el in list(r_el.findall(f"{{{MAIN_NS}}}c")):
            c_col, _ = split_cell_ref(c_el.attrib.get("r", ""))
            if c_col and col_letter_to_idx(c_col) >= start_col_idx:
                r_el.remove(c_el)

    def write_six_cells(r_el, r_num: int, values: list, style_idx: int):
        # Remove any existing cells at or after start_col_idx in case of re-run on copy
        for c_el in list(r_el.findall(f"{{{MAIN_NS}}}c")):
            c_col, _ = split_cell_ref(c_el.attrib.get("r", ""))
            if c_col and col_letter_to_idx(c_col) >= start_col_idx:
                r_el.remove(c_el)
        for offset, text in enumerate(values):
            c_idx = start_col_idx + offset
            c_ref = f"{col_idx_to_letter(c_idx)}{r_num}"
            c_el = ET.SubElement(
                r_el,
                f"{{{MAIN_NS}}}c",
                {"r": c_ref, "s": str(style_idx), "t": "inlineStr"},
            )
            is_el = ET.SubElement(c_el, f"{{{MAIN_NS}}}is")
            t_el = ET.SubElement(is_el, f"{{{MAIN_NS}}}t")
            t_el.text = str(text) if text is not None else ""

    # Write header row
    if header_row in rows_by_num:
        write_six_cells(rows_by_num[header_row], header_row, AUDIT_HEADERS, xf_ids["header"])

    # Write data rows
    for r_num, vals in sorted(row_audit_map.items()):
        if r_num not in rows_by_num:
            continue
        assert len(vals) == 6, f"Row {r_num} must have 6 audit values, got {len(vals)}"
        s_key = status_to_style_key(vals[5])
        write_six_cells(rows_by_num[r_num], r_num, vals, xf_ids[s_key])

    # Update dimension if present
    dim_el = root.find(f"{{{MAIN_NS}}}dimension")
    end_col_letter = col_idx_to_letter(start_col_idx + 5)
    if dim_el is not None and "ref" in dim_el.attrib:
        ref = dim_el.attrib["ref"]
        if ":" in ref:
            start_part, end_part = ref.split(":", 1)
            _, end_r = split_cell_ref(end_part)
            end_r = max(end_r or max_row_seen, max_row_seen)
            dim_el.attrib["ref"] = f"{start_part}:{end_col_letter}{end_r}"

    # Optionally append col widths if <cols> exists
    cols_el = root.find(f"{{{MAIN_NS}}}cols")
    if cols_el is not None:
        for col_el in list(cols_el.findall(f"{{{MAIN_NS}}}col")):
            c_min = int(col_el.attrib.get("min", "0"))
            c_max = int(col_el.attrib.get("max", "0"))
            if c_min >= start_col_idx:
                cols_el.remove(col_el)
            elif c_max >= start_col_idx:
                col_el.attrib["max"] = str(start_col_idx - 1)
        widths = [28, 32, 28, 32, 42, 16]
        for offset, w in enumerate(widths):
            c_idx = start_col_idx + offset
            ET.SubElement(
                cols_el,
                f"{{{MAIN_NS}}}col",
                {"min": str(c_idx), "max": str(c_idx), "width": str(w), "customWidth": "1"},
            )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def create_audited_workbook(src_path: str, dst_path: str, sheets_audit_spec: dict):
    """
    Create dst_path from src_path by injecting 6 audit columns into each specified sheet.
    sheets_audit_spec: {
        sheet_name: {
            "header_row": int,
            "start_col_idx": int, # 1-based column index where the 6 new columns start
            "rows": {row_num (int): [c1, c2, c3, c4, c5, c6]}
        }
    }
    """
    with zipfile.ZipFile(src_path, "r") as zin:
        # Resolve sheet_name -> xml path inside archive
        wb_root = ET.fromstring(zin.read("xl/workbook.xml"))
        rels_root = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
        rel_map = {r.attrib["Id"]: r.attrib["Target"] for r in rels_root}
        sheet_target_map = {}
        for s_el in wb_root.findall(f".//{{{MAIN_NS}}}sheet"):
            name = s_el.attrib["name"]
            rid = s_el.attrib[f"{{{REL_NS}}}id"]
            target = rel_map[rid].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheet_target_map[name] = target

        # Modify styles.xml
        new_styles_bytes, xf_ids = append_audit_styles(zin.read("xl/styles.xml"))

        # Modify target worksheet XMLs
        modified_entries = {"xl/styles.xml": new_styles_bytes}
        for s_name, spec in sheets_audit_spec.items():
            if s_name not in sheet_target_map:
                raise KeyError(f"Sheet {s_name} not found in {src_path}: {list(sheet_target_map.keys())}")
            target_path = sheet_target_map[s_name]
            orig_sheet_bytes = zin.read(target_path)
            new_sheet_bytes = inject_sheet_audit_columns(
                orig_sheet_bytes,
                header_row=int(spec["header_row"]),
                start_col_idx=int(spec["start_col_idx"]),
                row_audit_map={int(k): v for k, v in spec["rows"].items()},
                xf_ids=xf_ids,
            )
            modified_entries[target_path] = new_sheet_bytes

        # Write new zip preserving all original entries & cloned ZipInfo
        os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
        with zipfile.ZipFile(dst_path, "w") as zout:
            for item in zin.infolist():
                data = modified_entries.get(item.filename, zin.read(item.filename))
                new_info = zipfile.ZipInfo(filename=item.filename, date_time=item.date_time)
                new_info.compress_type = item.compress_type
                new_info.comment = item.comment
                new_info.extra = item.extra
                new_info.create_system = item.create_system
                new_info.create_version = item.create_version
                new_info.extract_version = item.extract_version
                new_info.flag_bits = item.flag_bits
                new_info.volume = item.volume
                new_info.internal_attr = item.internal_attr
                new_info.external_attr = item.external_attr
                zout.writestr(new_info, data)

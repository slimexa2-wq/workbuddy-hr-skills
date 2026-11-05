#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
祥能集团人员入职资料 Word (.docx) 自动化生成工具
功能：
1. 支持命令行 create-from-manifest 根据 JSON 清单生成与原版 100% 像素级一致的入职资料 Word 文档
2. 支持 PDF 自动调用同目录 pdf2png (原生 PDFKit) 渲染为高清 PNG
3. 自动校正图片 EXIF 方向，按模块类型智能计算最佳物理宽高（pt）
4. 修复性格测试页 VML 悬浮文本框与内嵌截图的绑定，杜绝文本框背景变成拉扁截图的 Bug
"""

import argparse
import copy
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

NS = {
    'wpc': "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    'mc': "http://schemas.openxmlformats.org/markup-compatibility/2006",
    'o': "urn:schemas-microsoft-com:office:office",
    'r': "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    'm': "http://schemas.openxmlformats.org/officeDocument/2006/math",
    'v': "urn:schemas-microsoft-com:vml",
    'wp14': "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    'wp': "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    'w10': "urn:schemas-microsoft-com:office:word",
    'w': "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    'w14': "http://schemas.microsoft.com/office/word/2010/wordml",
    'wpg': "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    'wpi': "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    'wne': "http://schemas.microsoft.com/office/word/2006/wordml",
    'wps': "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    'wpsCustomData': "http://www.wps.cn/officeDocument/2013/wpsCustomData",
}

for k, v in NS.items():
    ET.register_namespace(k, v)


def w_tag(name):
    return f"{{{NS['w']}}}{name}"


def v_tag(name):
    return f"{{{NS['v']}}}{name}"


def o_tag(name):
    return f"{{{NS['o']}}}{name}"


def r_tag(name):
    return f"{{{NS['r']}}}{name}"


def w10_tag(name):
    return f"{{{NS['w10']}}}{name}"


def get_image_size_and_normalize(img_path, work_dir, idx, rotate=0):
    """获取图片宽高，处理 EXIF 方向或指定旋转角度，输出标准 png/jpg 到 work_dir"""
    ext = os.path.splitext(img_path)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg']:
        ext = '.png'
    out_name = f"image{idx}{ext}"
    out_path = os.path.join(work_dir, out_name)
    shutil.copy2(img_path, out_path)

    if rotate in [90, 180, 270]:
        subprocess.run(['/usr/bin/sips', '-r', str(rotate), out_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    res = subprocess.run(['/usr/bin/sips', '-g', 'pixelWidth', '-g', 'pixelHeight', out_path],
                         capture_output=True, text=True)
    w, h = 500, 700
    for line in res.stdout.splitlines():
        if 'pixelWidth:' in line:
            w = int(line.split(':')[1].strip())
        elif 'pixelHeight:' in line:
            h = int(line.split(':')[1].strip())
    return out_name, out_path, w, h


def render_pdf_to_images(pdf_path, temp_dir, scale=2.0):
    """使用内置原生 pdf2png 工具将 PDF 每一页渲染为高清 PNG"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf2png_bin = os.path.join(script_dir, 'pdf2png')
    pdf2png_swift = os.path.join(script_dir, 'pdf2png.swift')
    if not os.path.exists(pdf2png_bin) and os.path.exists(pdf2png_swift):
        subprocess.run(['/usr/bin/swiftc', '-O', pdf2png_swift, '-o', pdf2png_bin], check=True)

    out_sub = os.path.join(temp_dir, os.path.basename(pdf_path) + "_pages")
    os.makedirs(out_sub, exist_ok=True)
    res = subprocess.run([pdf2png_bin, pdf_path, out_sub, str(scale)],
                         capture_output=True, text=True, check=True)
    pages = [line.strip() for line in res.stdout.splitlines() if line.strip() and os.path.exists(line.strip())]
    return sorted(pages)


def calc_display_pt(w_px, h_px, mode='full_page', custom_w=None, custom_h=None):
    """计算在 Word 中的物理显示宽高 (pt)"""
    if custom_w and custom_h:
        return float(custom_w), float(custom_h)
    aspect = h_px / float(w_px) if w_px else 1.414

    if mode == 'photo':
        # 证件照标准高度约 155pt
        h_pt = 155.05
        w_pt = round(h_pt / aspect, 2)
        return w_pt, h_pt
    elif mode == 'id_card':
        # 身份证正反面同页上下排布，宽度约 235pt，高度约 148pt
        w_pt = 235.0
        h_pt = round(w_pt * aspect, 2)
        if h_pt > 180.0:
            h_pt = 175.0
            w_pt = round(h_pt / aspect, 2)
        return w_pt, h_pt
    elif mode == 'certificate_pair':
        # 毕业证+学位证同页上下排布，宽度最大 478pt，单张高度不超过 325pt
        w_pt = 478.0
        h_pt = round(w_pt * aspect, 2)
        if h_pt > 325.0:
            h_pt = 325.0
            w_pt = round(h_pt / aspect, 2)
        return w_pt, h_pt
    elif mode == 'personality':
        # 性格测试手机长截图，留出下方两个悬浮文本框空间，高度控制在 515pt 以内
        h_pt = 515.55
        w_pt = round(h_pt / aspect, 2)
        if w_pt > 380.0:
            w_pt = 371.35
            h_pt = round(w_pt * aspect, 2)
        return w_pt, h_pt
    elif mode == 'Standard_Sec2':
        # 第2节（左右边距 90pt/38pt，可用宽约 467pt，可用高约 665pt）
        max_w, max_h = 479.0, 665.0
        w_pt = max_w
        h_pt = round(w_pt * aspect, 2)
        if h_pt > max_h:
            h_pt = max_h
            w_pt = round(h_pt / aspect, 2)
        return w_pt, h_pt
    else:
        # 第3节及以后（左右边距 36pt，可用宽约 523pt，可用高约 739.6pt）
        max_w, max_h = 523.0, 739.6
        w_pt = max_w
        h_pt = round(w_pt * aspect, 2)
        if h_pt > max_h:
            h_pt = max_h
            w_pt = round(h_pt / aspect, 2)
        return w_pt, h_pt


def pad_underline_value(val, total_visual_width=38):
    """生成带前后空格居中的封面下划线文本"""
    val = str(val).strip()
    val_len = sum(2 if ord(c) > 127 else 1 for c in val)
    rem = max(4, total_visual_width - val_len)
    left = rem // 2
    right = rem - left
    return (" " * left) + val + (" " * right)


def make_heading_p(caption, numbered=True, page_break_before=True):
    """创建章节标题段落（如 一、《应聘人员登记表》 或 个人征信报告（第2页））"""
    p = ET.Element(w_tag('p'))
    pPr = ET.SubElement(p, w_tag('pPr'))
    if numbered:
        numPr = ET.SubElement(pPr, w_tag('numPr'))
        ET.SubElement(numPr, w_tag('ilvl'), {w_tag('val'): '0'})
        ET.SubElement(numPr, w_tag('numId'), {w_tag('val'): '1'})
        ET.SubElement(pPr, w_tag('ind'), {
            w_tag('left'): '0',
            w_tag('leftChars'): '0',
            w_tag('firstLine'): '0',
            w_tag('firstLineChars'): '0'
        })
    rPr_p = ET.SubElement(pPr, w_tag('rPr'))
    ET.SubElement(rPr_p, w_tag('rFonts'), {w_tag('hint'): 'eastAsia'})
    ET.SubElement(rPr_p, w_tag('b'))
    ET.SubElement(rPr_p, w_tag('bCs'))
    ET.SubElement(rPr_p, w_tag('lang'), {w_tag('val'): 'en-US', w_tag('eastAsia'): 'zh-CN'})

    if page_break_before:
        r_br = ET.SubElement(p, w_tag('r'))
        rPr_br = ET.SubElement(r_br, w_tag('rPr'))
        ET.SubElement(rPr_br, w_tag('rFonts'), {w_tag('hint'): 'eastAsia'})
        ET.SubElement(rPr_br, w_tag('b'))
        ET.SubElement(rPr_br, w_tag('bCs'))
        ET.SubElement(rPr_br, w_tag('lang'), {w_tag('val'): 'en-US', w_tag('eastAsia'): 'zh-CN'})
        ET.SubElement(r_br, w_tag('br'), {w_tag('type'): 'page'})

    r_txt = ET.SubElement(p, w_tag('r'))
    rPr_txt = ET.SubElement(r_txt, w_tag('rPr'))
    ET.SubElement(rPr_txt, w_tag('rFonts'), {w_tag('hint'): 'eastAsia'})
    ET.SubElement(rPr_txt, w_tag('b'))
    ET.SubElement(rPr_txt, w_tag('bCs'))
    ET.SubElement(rPr_txt, w_tag('lang'), {w_tag('val'): 'en-US', w_tag('eastAsia'): 'zh-CN'})
    t = ET.SubElement(r_txt, w_tag('t'))
    t.text = caption
    return p


def make_image_p(rid, w_pt, h_pt, shape_idx=1026):
    """创建内嵌图片的段落"""
    p = ET.Element(w_tag('p'))
    pPr = ET.SubElement(p, w_tag('pPr'))
    numPr = ET.SubElement(pPr, w_tag('numPr'))
    ET.SubElement(numPr, w_tag('ilvl'), {w_tag('val'): '0'})
    ET.SubElement(numPr, w_tag('numId'), {w_tag('val'): '0'})
    ET.SubElement(pPr, w_tag('ind'), {w_tag('leftChars'): '0'})

    r = ET.SubElement(p, w_tag('r'))
    pict = ET.SubElement(r, w_tag('pict'))
    shape = ET.SubElement(pict, v_tag('shape'), {
        'id': f'_x0000_i{shape_idx}',
        o_tag('spt'): '75',
        'alt': '',
        'type': '#_x0000_t75',
        'style': f'height:{h_pt:.2f}pt;width:{w_pt:.2f}pt;',
        'filled': 'f',
        o_tag('preferrelative'): 't',
        'stroked': 'f',
        'coordsize': '21600,21600'
    })
    ET.SubElement(shape, v_tag('path'))
    ET.SubElement(shape, v_tag('fill'), {'on': 'f', 'focussize': '0,0'})
    ET.SubElement(shape, v_tag('stroke'), {'on': 'f'})
    ET.SubElement(shape, v_tag('imagedata'), {r_tag('id'): rid, o_tag('title'): ''})
    ET.SubElement(shape, o_tag('lock'), {v_tag('ext'): 'edit', 'aspectratio': 't'})
    ET.SubElement(shape, w10_tag('wrap'), {'type': 'none'})
    ET.SubElement(shape, w10_tag('anchorlock'))
    return p


def make_section_break_p(top="1440", right="1800", bottom="356", left="760"):
    """创建包含分节符 (sectPr) 的空段落"""
    p = ET.Element(w_tag('p'))
    pPr = ET.SubElement(p, w_tag('pPr'))
    numPr = ET.SubElement(pPr, w_tag('numPr'))
    ET.SubElement(numPr, w_tag('ilvl'), {w_tag('val'): '0'})
    ET.SubElement(numPr, w_tag('numId'), {w_tag('val'): '0'})
    sectPr = ET.SubElement(pPr, w_tag('sectPr'))
    ET.SubElement(sectPr, w_tag('pgSz'), {w_tag('w'): '11906', w_tag('h'): '16838'})
    ET.SubElement(sectPr, w_tag('pgMar'), {
        w_tag('top'): str(top),
        w_tag('right'): str(right),
        w_tag('bottom'): str(bottom),
        w_tag('left'): str(left),
        w_tag('header'): '851',
        w_tag('footer'): '992',
        w_tag('gutter'): '0'
    })
    ET.SubElement(sectPr, w_tag('cols'), {w_tag('space'): '720', w_tag('num'): '1'})
    ET.SubElement(sectPr, w_tag('docGrid'), {
        w_tag('type'): 'lines',
        w_tag('linePitch'): '312',
        w_tag('charSpace'): '0'
    })
    return p


def build_personality_p(template_p34, rid, w_pt, h_pt, fit_text, trait_text):
    """基于原版 P34 克隆生成性格测试页段落，精确填充两段式悬浮文本框与居中截图"""
    p = copy.deepcopy(template_p34)
    shapes = p.findall(f".//{v_tag('shape')}")
    # shapes[0]: _x0000_s1054 (margin-top:637.25pt, 下方框 -> 放 fit_text 或 trait_text)
    # shapes[1]: _x0000_s1038 (margin-top:540.75pt, 上方框 -> 放 fit_text)
    # shapes[2]: _x0000_i1051 (内嵌性格测试截图)
    # 注意原版朱悦珊中：_x0000_s1038 (top=540.75pt) 是上方框，_x0000_s1054 (top=637.25pt) 是下方框
    for s in shapes:
        sid = s.attrib.get('id', '')
        im = s.find(v_tag('imagedata'))
        tbx = s.find(f".//{w_tag('txbxContent')}")
        if tbx is not None:
            # 文本框严禁带有 r:id，否则会把图片当成背景填充！
            if im is not None and r_tag('id') in im.attrib:
                del im.attrib[r_tag('id')]
            ts = tbx.findall(f".//{w_tag('t')}")
            if ts:
                # margin-top:540.75pt 在视觉上方，放岗位契合度 (fit_text)；margin-top:637.25pt 在视觉下方，放性格特征与建议 (trait_text)
                if '540.75pt' in s.attrib.get('style', ''):
                    ts[0].text = fit_text
                else:
                    ts[0].text = trait_text
                for extra_t in ts[1:]:
                    extra_t.text = ''
        else:
            # 内嵌图片 shape
            s.attrib['style'] = f"height:{h_pt:.2f}pt;width:{w_pt:.2f}pt;"
            if im is not None:
                im.attrib[r_tag('id')] = rid
    return p


def create_from_manifest(manifest_path, output_docx):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_docx = os.path.join(os.path.dirname(script_dir), 'templates', 'base_template.docx')
    if not os.path.exists(template_docx):
        raise FileNotFoundError(f"Template not found: {template_docx}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        unzip_dir = os.path.join(tmp_dir, 'docx')
        pdf_cache_dir = os.path.join(tmp_dir, 'pdf_pages')
        os.makedirs(unzip_dir, exist_ok=True)
        os.makedirs(pdf_cache_dir, exist_ok=True)

        with zipfile.ZipFile(template_docx, 'r') as z:
            z.extractall(unzip_dir)

        media_dir = os.path.join(unzip_dir, 'word', 'media')
        # 保留封面右上角祥能集团 Logo (image1.png)，清理其余旧图片
        for fname in os.listdir(media_dir):
            if fname != 'image1.png':
                os.remove(os.path.join(media_dir, fname))

        doc_xml_path = os.path.join(unzip_dir, 'word', 'document.xml')
        rels_xml_path = os.path.join(unzip_dir, 'word', '_rels', 'document.xml.rels')

        doc_tree = ET.parse(doc_xml_path)
        doc_root = doc_tree.getroot()
        body = doc_root.find(w_tag('body'))

        # 保存原版 P34 作为性格测试页克隆模板，以及末尾 body_sectPr
        template_p34 = copy.deepcopy(body[34])
        body_sectPr = copy.deepcopy(body[-1])

        # 更新封面字段：P5(姓名)、P6(应聘岗位)、P7(所属部门)、P8(资料说明)、P17(年月)
        name_val = manifest.get('name', '')
        pos_val = manifest.get('position', '')
        dept_val = manifest.get('department', '')
        materials_desc = manifest.get('materials_desc', '应聘登记及面试记录表、简历、相关资质证书      ')
        year_val = str(manifest.get('year', '2026'))
        month_val = str(manifest.get('month', '10'))

        def set_cover_line(p_elem, value_str, left_target=17, right_target=17):
            val = str(value_str).strip()
            val_w = sum(2 if ord(c) > 127 else 1 for c in val)
            # 以中文4字(宽8)为基准，调节左右半角空格数，确保三行文字中心垂直对齐且下划线右端齐平
            diff = 8 - val_w
            left_spaces = max(2, left_target + (diff // 2))
            right_spaces = max(2, right_target + (diff - diff // 2))
            ts = p_elem.findall(f".//{w_tag('t')}")
            if len(ts) >= 2:
                ts[1].text = (" " * left_spaces) + val + (" " * right_spaces)
                for extra in ts[2:]:
                    extra.text = ''

        # 姓名：（标签3字，比5字标签少2个汉字=4个半角空格，故左侧基准为16，右侧基准为16）
        set_cover_line(body[5], name_val, left_target=16, right_target=16)
        # 应聘岗位：（标签5字，左侧基准12，右侧基准24）
        set_cover_line(body[6], pos_val, left_target=12, right_target=24)
        # 所属部门：（标签5字，左侧基准12，右侧基准18）
        set_cover_line(body[7], dept_val, left_target=12, right_target=18)
        if 'materials_desc' in manifest:
            ts8 = body[8].findall(f".//{w_tag('t')}")
            if len(ts8) >= 2:
                ts8[1].text = materials_desc

        # P17: 人力资源部制：  _2026_年_10_月
        ts17 = body[17].findall(f".//{w_tag('t')}")
        for t_el in ts17:
            if t_el.text and t_el.text.strip().isdigit():
                if len(t_el.text.strip()) == 4:
                    t_el.text = year_val
                else:
                    t_el.text = month_val

        # 截断 body[19:]，保留 P0..P18（封面 + 封面分节符）
        for child in list(body)[19:]:
            body.remove(child)

        # 处理 relationships：保留非图片的 rel 以及 image1.png (rId4)
        rels_tree = ET.parse(rels_xml_path)
        rels_root = rels_tree.getroot()
        rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        ET.register_namespace('', rel_ns)

        for rel in list(rels_root):
            target = rel.attrib.get('Target', '')
            if target.startswith('media/') and target != 'media/image1.png':
                rels_root.remove(rel)

        next_img_idx = 2
        next_rid_num = 20
        shape_counter = 1026

        def add_image_rel(img_path, rotate=0):
            nonlocal next_img_idx, next_rid_num
            fname, fpath, w_px, h_px = get_image_size_and_normalize(img_path, media_dir, next_img_idx, rotate=rotate)
            rid = f"rId{next_rid_num}"
            next_img_idx += 1
            next_rid_num += 1
            ET.SubElement(rels_root, f"{{{rel_ns}}}Relationship", {
                'Id': rid,
                'Type': "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                'Target': f"media/{fname}"
            })
            return rid, w_px, h_px

        items = manifest.get('items', [])
        in_sec2 = True  # 性格测试之前处于 Section 2，性格测试之后处于 Section 3

        for item_idx, item in enumerate(items):
            caption = item.get('caption', '').strip()
            is_personality = bool(item.get('personality', False)) or ('性格测试' in caption)
            is_photo = bool(item.get('photo', False)) or (caption == '证件照')
            is_id_card = bool(item.get('id_card', False)) or (caption == '身份证')
            same_page_with_prev = bool(item.get('same_page_as_previous', False)) or (is_id_card and item_idx > 0 and items[item_idx - 1].get('caption') == '证件照' and item.get('page_break_before') is not True)

            # 展开 item 中的图片列表（如果某项传入的是 .pdf 文件，自动拆页渲染为 PNG）
            raw_images = item.get('images', [])
            expanded_images = []
            for img_entry in raw_images:
                if isinstance(img_entry, str):
                    img_entry = {'path': img_entry}
                p_str = img_entry.get('path', '')
                if p_str.lower().endswith('.pdf'):
                    rendered_pages = render_pdf_to_images(p_str, pdf_cache_dir)
                    for pg_i, pg_path in enumerate(rendered_pages):
                        sub_entry = dict(img_entry)
                        sub_entry['path'] = pg_path
                        if pg_i > 0 and 'caption' not in sub_entry and '个人征信报告' in caption:
                            sub_entry['caption'] = f"{caption}（第{pg_i + 1}页）"
                        expanded_images.append(sub_entry)
                else:
                    expanded_images.append(img_entry)

            if is_personality:
                # 性格测试前插入 Section 2 结束分节符（若当前在 Sec2）
                if in_sec2:
                    body.append(make_section_break_p(top="1440", right="1800", bottom="356", left="760"))
                    in_sec2 = False
                # 插入编号标题“性格测试结果”（紧跟分节符后，无需重复 page_break_before）
                body.append(make_heading_p(caption, numbered=True, page_break_before=False))
                if expanded_images:
                    first_img = expanded_images[0]
                    rid, w_px, h_px = add_image_rel(first_img['path'], rotate=first_img.get('rotate', 0))
                    w_pt, h_pt = calc_display_pt(w_px, h_px, mode='personality',
                                                 custom_w=first_img.get('width_pt'),
                                                 custom_h=first_img.get('height_pt'))
                    p_info = item.get('p', {})
                    fit_text = p_info.get('fit', '')
                    trait_text = p_info.get('trait', '')
                    body.append(build_personality_p(template_p34, rid, w_pt, h_pt, fit_text, trait_text))
                continue

            # 普通章节
            # 判断是否需要段前分页：第1个章节紧接封面分节符不加分页；紧跟性格测试分节符后的第1个章节也不加分页；证件照后的身份证若同页也不加分页
            prev_was_personality = (item_idx > 0 and (bool(items[item_idx - 1].get('personality', False)) or '性格测试' in items[item_idx - 1].get('caption', '')))
            need_pb = (item_idx > 0) and (not prev_was_personality) and (not same_page_with_prev)
            if 'page_break_before' in item:
                need_pb = bool(item['page_break_before'])

            body.append(make_heading_p(caption, numbered=True, page_break_before=need_pb))

            # 如果选择了证件照与身份证同页（原版朱悦珊/孙福行风格），证件照后留空行间隔
            for img_i, img_entry in enumerate(expanded_images):
                sub_cap = img_entry.get('caption')
                if img_i > 0 and sub_cap:
                    # 如“个人征信报告（第2页）”，不参与一、二、三编号，但强制换页并加粗
                    body.append(make_heading_p(sub_cap, numbered=False, page_break_before=True))
                elif img_i > 0 and not is_id_card and not ('毕业' in caption or '学位' in caption) and img_entry.get('same_page') is not True:
                    # 多页文档（如2页简历、2页面试评价）第2页自动换页或直接連続排布（Word中高度660pt自然换页）
                    pass

                rid, w_px, h_px = add_image_rel(img_entry['path'], rotate=img_entry.get('rotate', 0))
                aspect = (h_px / float(w_px)) if w_px else 1.414
                if is_photo:
                    mode = 'photo'
                elif is_id_card:
                    mode = 'id_card'
                elif ('毕业' in caption or '学位' in caption) and len(expanded_images) >= 2 and aspect < 1.0:
                    mode = 'certificate_pair'
                elif in_sec2:
                    mode = 'Standard_Sec2'
                else:
                    mode = 'Standard_Sec3'

                w_pt, h_pt = calc_display_pt(w_px, h_px, mode=mode,
                                             custom_w=img_entry.get('width_pt'),
                                             custom_h=img_entry.get('height_pt'))
                shape_counter += 1
                body.append(make_image_p(rid, w_pt, h_pt, shape_idx=shape_counter))

            # 如果是证件照且下一个章节是身份证同页，补充3个空行让排版更舒展
            if is_photo and item_idx + 1 < len(items) and items[item_idx + 1].get('caption') == '身份证':
                for _ in range(3):
                    body.append(ET.Element(w_tag('p')))

        # 恢复文档末尾的 body_sectPr
        body.append(body_sectPr)

        # 确保 [Content_Types].xml 包含 jpg/jpeg 和 png 扩展名支持
        ct_path = os.path.join(unzip_dir, '[Content_Types].xml')
        ct_tree = ET.parse(ct_path)
        ct_root = ct_tree.getroot()
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        ET.register_namespace('', ct_ns)
        existing_exts = {el.attrib.get('Extension', '').lower() for el in ct_root.findall(f"{{{ct_ns}}}Default")}
        if 'jpg' not in existing_exts:
            ET.SubElement(ct_root, f"{{{ct_ns}}}Default", {'Extension': 'jpg', 'ContentType': 'image/jpeg'})
        if 'jpeg' not in existing_exts:
            ET.SubElement(ct_root, f"{{{ct_ns}}}Default", {'Extension': 'jpeg', 'ContentType': 'image/jpeg'})
        if 'png' not in existing_exts:
            ET.SubElement(ct_root, f"{{{ct_ns}}}Default", {'Extension': 'png', 'ContentType': 'image/png'})
        ct_tree.write(ct_path, encoding='utf-8', xml_declaration=True)

        doc_tree.write(doc_xml_path, encoding='utf-8', xml_declaration=True)
        rels_tree.write(rels_xml_path, encoding='utf-8', xml_declaration=True)

        # 重新打包为 .docx
        os.makedirs(os.path.dirname(os.path.abspath(output_docx)), exist_ok=True)
        with zipfile.ZipFile(output_docx, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root_dir, _, files in os.walk(unzip_dir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, unzip_dir)
                    zf.write(full_path, rel_path)

    return output_docx


def main():
    parser = argparse.ArgumentParser(description="祥能集团人员入职资料 Word 生成工具")
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_create = sub.add_parser('create', help='根据 JSON 清单生成入职资料 .docx')
    p_create.add_argument('--manifest', required=True, help='JSON 清单路径')
    p_create.add_argument('--output', required=True, help='输出的 .docx 文件路径')

    p_pdf = sub.add_parser('render-pdf', help='将 PDF 拆页渲染为高清 PNG')
    p_pdf.add_argument('--pdf', required=True, help='输入 PDF 路径')
    p_pdf.add_argument('--outdir', required=True, help='输出图片目录')
    p_pdf.add_argument('--scale', type=float, default=2.0, help='渲染缩放倍数（默认 2.0）')

    args = parser.parse_args()
    if args.cmd == 'create':
        out = create_from_manifest(args.manifest, args.output)
        print(f"Success! Dossier generated at: {out}")
    elif args.cmd == 'render-pdf':
        pages = render_pdf_to_images(args.pdf, args.outdir, scale=args.scale)
        print(json.dumps({"pages": pages}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

import unittest
import os
import json
import openpyxl
from openpyxl.comments import Comment

from ultra_modules.zero_comment_null_guard_plain_explainer import ZeroCommentNullGuardPlainExplainer

class TestZeroCommentNullGuardPlainExplainer(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/test_data"
        os.makedirs(self.test_dir, exist_ok=True)
        self.normal_file = os.path.join(self.test_dir, "normal.xlsx")
        self.dirty_file = os.path.join(self.test_dir, "dirty.xlsx")
        self.empty_file = os.path.join(self.test_dir, "empty.xlsx")

        # 1. 正常无脏数据文件
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 10
        ws['B1'] = 20
        wb.save(self.normal_file)

        # 2. 脏数据文件（带批注，带空值）
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 10
        ws['A2'] = None # Null value
        ws['B1'] = " "  # String whitespace
        ws['B2'] = 30
        comment = Comment("This is a comment", "Author")
        ws['A1'].comment = comment
        ws['B2'].comment = comment
        wb.save(self.dirty_file)

        # 3. 极端边界（空Excel）
        wb = openpyxl.Workbook()
        wb.save(self.empty_file)

    def tearDown(self):
        for f in [self.normal_file, self.dirty_file, self.empty_file]:
            if os.path.exists(f):
                os.remove(f)
            healed = os.path.join(os.path.dirname(f), "healed_" + os.path.basename(f))
            if os.path.exists(healed):
                os.remove(healed)

    def test_1_normal_data(self):
        """测试1：正常数据流转，不产生误操作"""
        explainer = ZeroCommentNullGuardPlainExplainer(self.normal_file)
        result = explainer.process()

        self.assertEqual(explainer.stats['status'], 'success')
        self.assertEqual(explainer.stats['comments_removed'], 0)
        self.assertEqual(explainer.stats['nulls_filled'], 0)
        self.assertTrue("✅ 数据预检与自愈完成" in result)

    def test_2_dirty_data_self_healing(self):
        """测试2：脏数据自愈（批注清零，空值填0）"""
        explainer = ZeroCommentNullGuardPlainExplainer(self.dirty_file)
        result = explainer.process()

        self.assertEqual(explainer.stats['status'], 'success')
        self.assertEqual(explainer.stats['comments_removed'], 2)
        # A2 (None), B1 (" ") -> 2 nulls filled to 0
        self.assertEqual(explainer.stats['nulls_filled'], 2)

        # 验证生成的愈合文件
        healed_file = explainer.healed_file_path
        self.assertTrue(os.path.exists(healed_file))
        wb = openpyxl.load_workbook(healed_file)
        ws = wb.active
        self.assertEqual(ws['A2'].value, 0)
        self.assertEqual(ws['B1'].value, 0)
        self.assertIsNone(ws['A1'].comment)
        self.assertIsNone(ws['B2'].comment)

    def test_3_missing_params_fallback(self):
        """测试3：缺参默认兜底，零异常抛出"""
        explainer = ZeroCommentNullGuardPlainExplainer() # 缺失文件路径
        result = explainer.process()

        self.assertEqual(explainer.stats['status'], 'error')
        self.assertTrue("未提供有效文件" in explainer.stats['error'])
        self.assertTrue("⚠️ 预检提醒" in result)
        self.assertTrue("已为您进行安全兜底" in result)

    def test_4_extreme_boundary_empty_excel(self):
        """测试4：极端边界情况（完全空的Excel文件）"""
        explainer = ZeroCommentNullGuardPlainExplainer(self.empty_file)
        result = explainer.process()

        self.assertEqual(explainer.stats['status'], 'success')
        self.assertEqual(explainer.stats['comments_removed'], 0)
        # openpyxl对于完全空的文件，max_row=1, max_column=1，且值为None
        self.assertEqual(explainer.stats['nulls_filled'], 1)

        healed_file = explainer.healed_file_path
        wb = openpyxl.load_workbook(healed_file)
        ws = wb.active
        self.assertEqual(ws['A1'].value, 0)

    def test_5_different_output_formats(self):
        """测试5：不同输出格式验证 (JSON/HTML)"""
        # 测试 HTML
        explainer_html = ZeroCommentNullGuardPlainExplainer(self.normal_file, output_format="html")
        res_html = explainer_html.process()
        self.assertTrue(res_html.startswith("<div"))
        self.assertTrue("<h3" in res_html)
        self.assertTrue("✅" in res_html)

        # 测试 JSON
        explainer_json = ZeroCommentNullGuardPlainExplainer(self.normal_file, output_format="JsoN")
        res_json = explainer_json.process()
        data = json.loads(res_json)
        self.assertEqual(data['status'], 'success')
        self.assertTrue("✅" in data['title'])
        self.assertEqual(data['metrics']['comments_removed'], 0)

if __name__ == '__main__':
    unittest.main()

import os
import unittest
import openpyxl
from ultra_modules.xlsx_formula_healer_plain_explainer import XlsxFormulaHealerPlainExplainer

class TestXlsxFormulaHealerPlainExplainer(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.clean_file = os.path.join(self.test_dir, "test_clean.xlsx")
        self.dirty_file = os.path.join(self.test_dir, "test_dirty.xlsx")
        self.corrupted_file = os.path.join(self.test_dir, "test_corrupted.xlsx")

        # 1. 创建干净的测试文件
        wb_clean = openpyxl.Workbook()
        ws_clean = wb_clean.active
        ws_clean['A1'] = 100
        ws_clean['A2'] = 200
        ws_clean['A3'] = "=A1+A2"
        wb_clean.save(self.clean_file)

        # 2. 创建脏数据的测试文件
        wb_dirty = openpyxl.Workbook()
        ws_dirty = wb_dirty.active
        ws_dirty['A1'] = "#DIV/0!"     # 模拟公式错误结果缓存
        ws_dirty['A2'] = "#REF!"       # 模拟公式错误结果缓存
        ws_dirty['A3'] = " 123.45 "    # 模拟文本型数字
        ws_dirty['A4'] = "00123"       # 模拟工号，不应被转换
        ws_dirty['A5'] = "=A5+1"       # 模拟循环引用公式
        wb_dirty.save(self.dirty_file)

        # 3. 创建极端的错误文件 (非excel格式的文本文件)
        with open(self.corrupted_file, "w") as f:
            f.write("This is not an excel file. 这是一个损坏的文件。")

    def tearDown(self):
        # 清理测试生成的文件
        files_to_remove = [
            self.clean_file,
            self.dirty_file,
            self.corrupted_file,
            self.clean_file.replace(".xlsx", "_healed.xlsx"),
            self.dirty_file.replace(".xlsx", "_healed.xlsx")
        ]
        for f in files_to_remove:
            if os.path.exists(f):
                os.remove(f)

    def test_normal_file(self):
        """测试1：正常干净的文件，不应进行任何修复操作"""
        healer = XlsxFormulaHealerPlainExplainer(self.clean_file)
        result = healer.scan_and_heal()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["healed_count"], 0)
        self.assertIn("非常健康", result["plain_summary"])
        self.assertTrue(os.path.exists(result["healed_file"]))

    def test_dirty_data_healing(self):
        """测试2：脏数据静默自愈能力（错误值、文本数字、循环引用）"""
        healer = XlsxFormulaHealerPlainExplainer(self.dirty_file)
        result = healer.scan_and_heal()

        self.assertEqual(result["status"], "success")
        # 至少应该修复 #DIV/0!, #REF!, " 123.45 ", =A5+1 四个问题
        self.assertGreaterEqual(result["healed_count"], 4)
        self.assertEqual(result["issues"]["formula_errors"], 2)
        self.assertEqual(result["issues"]["text_numbers"], 1)
        self.assertEqual(result["issues"]["circular_references"], 1)
        self.assertIn("悄悄修复了表格里", result["plain_summary"])

        # 验证修复后的文件内容
        healed_path = result["healed_file"]
        self.assertTrue(os.path.exists(healed_path))
        wb_healed = openpyxl.load_workbook(healed_path)
        ws_healed = wb_healed.active

        self.assertEqual(ws_healed['A1'].value, 0)
        self.assertEqual(ws_healed['A2'].value, 0)
        self.assertEqual(ws_healed['A3'].value, 123.45)
        self.assertEqual(ws_healed['A4'].value, "00123")  # 字符串工号未被错误转换
        self.assertEqual(ws_healed['A5'].value, 0)

    def test_missing_parameter_fallback(self):
        """测试3：缺参默认兜底测试，零配置容错"""
        healer = XlsxFormulaHealerPlainExplainer()
        result = healer.scan_and_heal()

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["healed_count"], 0)
        self.assertIn("没有收到", result["plain_summary"])
        self.assertIsNone(result["healed_file"])

    def test_file_not_found_fallback(self):
        """测试4：文件不存在时的兜底测试"""
        healer = XlsxFormulaHealerPlainExplainer("non_existent_file_path_12345.xlsx")
        result = healer.scan_and_heal()

        self.assertEqual(result["status"], "fallback")
        self.assertIn("跑丢了", result["plain_summary"])

    def test_extreme_boundaries(self):
        """测试5：极端边界/损坏文件的安全容错与异常捕获"""
        healer = XlsxFormulaHealerPlainExplainer(self.corrupted_file)
        result = healer.scan_and_heal()

        self.assertEqual(result["status"], "fallback")
        self.assertIn("遇到了一些小状况", result["plain_summary"])
        self.assertIsNone(result["healed_file"])

if __name__ == "__main__":
    unittest.main()

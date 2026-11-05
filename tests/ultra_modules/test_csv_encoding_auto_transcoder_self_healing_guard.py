import unittest
import os
import shutil
from ultra_modules.csv_encoding_auto_transcoder_self_healing_guard import CSVTranscoderGuard

class TestCSVTranscoderGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_workspace_temp"
        os.makedirs(self.test_dir, exist_ok=True)
        self.utf8_file = os.path.join(self.test_dir, "test_utf8.csv")
        self.gbk_file = os.path.join(self.test_dir, "test_gbk.csv")
        self.dirty_file = os.path.join(self.test_dir, "test_dirty.csv")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_normal_utf8(self):
        """测试正常 UTF-8 CSV 文件操作"""
        content = "姓名,工资\n张三,1000\n"
        with open(self.utf8_file, 'wb') as f:
            f.write(content.encode('utf-8'))

        result = CSVTranscoderGuard.transcode_and_heal(self.utf8_file)
        self.assertTrue(result)

        with open(self.utf8_file, 'r', encoding='utf-8') as f:
            new_content = f.read()
        self.assertEqual(new_content, content)

    def test_transcode_gbk(self):
        """测试 GBK 编码转换"""
        content = "姓名,工资\r\n李四,2000\r\n"
        expected = "姓名,工资\n李四,2000\n"

        with open(self.gbk_file, 'wb') as f:
            f.write(content.encode('gbk'))

        result = CSVTranscoderGuard.transcode_and_heal(self.gbk_file)
        self.assertTrue(result)

        with open(self.gbk_file, 'r', encoding='utf-8') as f:
            new_content = f.read()
        self.assertEqual(new_content, expected)

    def test_self_healing_dirty_data(self):
        """测试脏数据自愈（空字符和不规则换行）"""
        # \x00 空字符和 \r, \r\n 混合
        content_with_nulls_and_mixed_newlines = b"name,salary\x00\r\nwang,3000\r\n\x00zhao,4000\r"
        expected = "name,salary\nwang,3000\nzhao,4000\n"

        with open(self.dirty_file, 'wb') as f:
            f.write(content_with_nulls_and_mixed_newlines)

        result = CSVTranscoderGuard.transcode_and_heal(self.dirty_file)
        self.assertTrue(result)

        with open(self.dirty_file, 'r', encoding='utf-8') as f:
            new_content = f.read()
        self.assertEqual(new_content, expected)

    def test_silent_fallback(self):
        """测试缺参或不存在的文件静默兜底"""
        # 测试空参数
        self.assertFalse(CSVTranscoderGuard.transcode_and_heal())
        self.assertFalse(CSVTranscoderGuard.transcode_and_heal(""))

        # 测试不存在的文件
        non_existent = os.path.join(self.test_dir, "does_not_exist.csv")
        self.assertFalse(CSVTranscoderGuard.transcode_and_heal(non_existent))

        # 撤销空参数或不存在文件也应静默
        self.assertFalse(CSVTranscoderGuard.undo())
        self.assertFalse(CSVTranscoderGuard.undo(non_existent))

    def test_snapshot_and_undo(self):
        """测试快照和撤回功能"""
        original_content = "original,data\n"
        with open(self.utf8_file, 'wb') as f:
            f.write(original_content.encode('utf-8'))

        # 转码操作
        result = CSVTranscoderGuard.transcode_and_heal(self.utf8_file)
        self.assertTrue(result)

        # 修改文件内容模拟其他操作
        with open(self.utf8_file, 'w', encoding='utf-8') as f:
            f.write("modified,data\n")

        # 撤回
        undo_result = CSVTranscoderGuard.undo(self.utf8_file)
        self.assertTrue(undo_result)

        # 检查是否恢复到转码前的原始内容
        with open(self.utf8_file, 'r', encoding='utf-8') as f:
            restored_content = f.read()
        self.assertEqual(restored_content, original_content)

        # 检查快照文件是否被清理
        snapshot_path = CSVTranscoderGuard.get_snapshot_path(self.utf8_file)
        self.assertFalse(os.path.exists(snapshot_path))

if __name__ == '__main__':
    unittest.main()

import unittest
import os
from ultra_modules.csv_encoding_auto_transcoder_batch_pipeline import CsvEncodingAutoTranscoder

class TestCsvEncodingAutoTranscoder(unittest.TestCase):

    def setUp(self):
        self.transcoder = CsvEncodingAutoTranscoder()

    def test_normal_utf8_processing(self):
        """测试用例 1: 正常情况，UTF-8 编码的普通 CSV 文件"""
        csv_content = "Name,Salary\nAlice,5000\nBob,6000\n"
        raw_bytes = csv_content.encode('utf-8')

        result = self.transcoder.process_file_bytes(raw_bytes)

        # Windows 和 Unix 换行符可能不同，这里统一用 \n 断言
        self.assertEqual(result, csv_content)

        # 批量处理测试
        batch_result = self.transcoder.process_batch([raw_bytes, raw_bytes])
        self.assertEqual(batch_result["processed_count"], 2)
        self.assertEqual(batch_result["results"][0], csv_content)
        self.assertEqual(batch_result["results"][1], csv_content)

    def test_gbk_gb18030_decoding(self):
        """测试用例 2: GBK/GB18030 乱码自适应，支持历史遗留考勤文件"""
        # 测试 GBK 编码数据
        csv_content = "姓名,工资\n张三,5000\n李四,6000\n"
        raw_bytes = csv_content.encode('gbk')

        result = self.transcoder.process_file_bytes(raw_bytes)
        self.assertEqual(result, csv_content)

    def test_dirty_data_self_healing(self):
        """测试用例 3: 脏数据自愈功能，包含 \x00 等无效字符"""
        # 含有一个空字符 \x00 和多余空格
        dirty_csv = "Name,Salary\nAli\x00ce, 5000 \n"
        expected_csv = "Name,Salary\nAlice,5000\n"
        raw_bytes = dirty_csv.encode('utf-8')

        result = self.transcoder.process_file_bytes(raw_bytes)
        self.assertEqual(result, expected_csv)

    def test_missing_params_fallback(self):
        """测试用例 4: 缺参默认兜底（缺省编码、缺省线程数等）"""
        # 不传参初始化，默认值应被设置
        transcoder = CsvEncodingAutoTranscoder(default_encoding=None, max_workers=None)
        self.assertEqual(transcoder.default_encoding, None)
        self.assertTrue(transcoder.max_workers > 0)

        # 传入空数据
        result = transcoder.process_file_bytes(b"")
        self.assertEqual(result, "")

        # 批量传入空列表
        batch_result = transcoder.process_batch([])
        self.assertEqual(batch_result["processed_count"], 0)
        self.assertEqual(batch_result["results"], [])

    def test_extreme_boundaries(self):
        """测试用例 5: 极端边界处理"""
        # 完全无法解析的随机字节（非任何有效字符串编码）
        invalid_bytes = b'\xff\xfe\xff\xff\x00\x11\x22'

        # 不应抛出异常，而应该采用容错替代字符进行降级处理
        result = self.transcoder.process_file_bytes(invalid_bytes)
        self.assertTrue(isinstance(result, str))

        # 批量处理包含异常数据的情况，也不应阻塞整个流水线
        valid_bytes = "Name\nTest\n".encode('utf-8')
        batch_result = self.transcoder.process_batch([valid_bytes, invalid_bytes, b""])

        self.assertEqual(batch_result["processed_count"], 3)
        self.assertEqual(batch_result["results"][0], "Name\nTest\n")
        self.assertTrue(isinstance(batch_result["results"][1], str))
        self.assertEqual(batch_result["results"][2], "")

if __name__ == '__main__':
    unittest.main()

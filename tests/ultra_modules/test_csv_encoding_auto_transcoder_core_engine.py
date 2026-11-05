import unittest
from ultra_modules.csv_encoding_auto_transcoder_core_engine import transcode_csv_to_utf8

class TestCSVEncodingAutoTranscoder(unittest.TestCase):

    def test_utf8_sig_normal(self):
        # 正常带有BOM的UTF-8
        original = "姓名,工资\n张三,10000"
        raw_data = original.encode("utf-8-sig")
        result = transcode_csv_to_utf8(raw_data)
        self.assertEqual(result, original)

    def test_gb18030_normal(self):
        # 正常的GB18030/GBK
        original = "姓名,考勤\n李四,全勤"
        raw_data = original.encode("gb18030")
        result = transcode_csv_to_utf8(raw_data)
        self.assertEqual(result, original)

    def test_missing_param_default_fallback(self):
        # 缺参自动赋默认值
        self.assertEqual(transcode_csv_to_utf8(), "")
        self.assertEqual(transcode_csv_to_utf8(None), "")
        self.assertEqual(transcode_csv_to_utf8(b""), "")

    def test_dirty_data_silent_cleaning(self):
        # 脏数据静默清洗 (无法正常解码的随机字节)
        # 用无法被 gb18030 解码的字节序列 (GB18030虽然覆盖面广，但仍有不合法序列，或者我们直接测试最后 fallback 的情况)
        # "\xff\xff" is often invalid in many encodings
        dirty_data = b'\xff\xff\xff\xff'
        # 不应抛出异常
        result = transcode_csv_to_utf8(dirty_data)
        self.assertIsInstance(result, str)
        # 应该进行了解码，可能含有 \ufffd

    def test_extreme_boundary_wrong_type(self):
        # 极端边界：传入非bytes/str的奇怪类型
        class WeirdType:
            def __bytes__(self):
                raise ValueError("Cannot convert")

        result = transcode_csv_to_utf8(WeirdType())
        self.assertEqual(result, "")

        # 传入可以转换为bytes的类型
        result2 = transcode_csv_to_utf8([104, 101, 108, 108, 111]) # "hello" in ascii
        self.assertEqual(result2, "hello")

    def test_string_input(self):
        # 如果直接传入字符串，应该原样返回
        self.assertEqual(transcode_csv_to_utf8("已经是字符串"), "已经是字符串")

if __name__ == '__main__':
    unittest.main()

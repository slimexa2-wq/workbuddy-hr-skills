import unittest
import codecs
from ultra_modules.csv_encoding_auto_transcoder_audit_trace import process_csv_with_audit

class TestCsvEncodingAutoTranscoderAuditTrace(unittest.TestCase):

    def test_normal_utf8(self):
        """测试正常 UTF-8 编码输入"""
        content = "姓名,工资\n张三,5000".encode('utf-8')
        result, audit = process_csv_with_audit(content)
        self.assertEqual(result, "姓名,工资\n张三,5000")
        self.assertTrue(audit["success"])
        # Our implementation checks 'utf-8-sig' before 'utf-8',
        # and a standard utf-8 string parses fine as utf-8-sig (no BOM).
        self.assertIn(audit["final_encoding"], ["utf-8", "utf-8-sig"])
        self.assertFalse(audit["dirty_data_healed"])

    def test_normal_gbk(self):
        """测试正常 GBK 编码输入"""
        content = "姓名,工资\n李四,6000".encode('gbk')
        result, audit = process_csv_with_audit(content)
        self.assertEqual(result, "姓名,工资\n李四,6000")
        self.assertTrue(audit["success"])
        # gb18030 covers gbk, and it's evaluated before gbk in our list
        self.assertIn(audit["final_encoding"], ["gbk", "gb18030"])
        self.assertFalse(audit["dirty_data_healed"])

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈（无效字节静默替换）"""
        # \xff is invalid in utf-8, gbk, etc., forcing a fallback replacement
        content = b"Name,Salary\nBad,\xffData"
        result, audit = process_csv_with_audit(content, fallback_encoding="utf-8")
        # Python replace character is usually \ufffd
        self.assertIn("\ufffd", result)
        self.assertTrue(audit["success"])
        self.assertTrue(audit["dirty_data_healed"])
        self.assertTrue("replaced" in audit["final_encoding"])

    def test_missing_parameter_fallback(self):
        """测试缺参/默认兜底（传入 None, 空字节流等）"""
        # None parameter
        result_none, audit_none = process_csv_with_audit(None)
        self.assertEqual(result_none, "")
        self.assertTrue(audit_none["success"])
        self.assertTrue(any("Null parameter self-healed" in step for step in audit_none["steps"]))

        # Empty parameter (default)
        result_empty, audit_empty = process_csv_with_audit()
        self.assertEqual(result_empty, "")
        self.assertTrue(audit_empty["success"])

        # String parameter
        result_str, audit_str = process_csv_with_audit("Test String")
        self.assertEqual(result_str, "Test String")
        self.assertEqual(audit_str["final_encoding"], "utf-8 (assumed)")

        # Non-bytes parameter convertible to bytes
        result_list, audit_list = process_csv_with_audit([65, 66, 67])
        self.assertEqual(result_list, "ABC")

        # Unconvertible object
        class Unconvertible:
            def __bytes__(self):
                raise TypeError("Cannot convert")

        result_unconv, audit_unconv = process_csv_with_audit(Unconvertible())
        self.assertEqual(result_unconv, "")
        self.assertTrue(any("Failed to coerce" in step for step in audit_unconv["steps"]))

    def test_extreme_boundary_conditions(self):
        """测试极端边界条件（如极大文本、含有各种特殊字符等）"""
        # Large text
        large_content = ("A" * 1000000).encode('utf-8')
        result, audit = process_csv_with_audit(large_content)
        self.assertEqual(len(result), 1000000)
        self.assertEqual(audit["input_length"], 1000000)

        # UTF-8 SIG
        sig_content = codecs.BOM_UTF8 + "姓名,工资\n王五,7000".encode('utf-8')
        result_sig, audit_sig = process_csv_with_audit(sig_content)
        self.assertEqual(result_sig, "姓名,工资\n王五,7000")
        self.assertEqual(audit_sig["final_encoding"], "utf-8-sig")

if __name__ == "__main__":
    unittest.main()

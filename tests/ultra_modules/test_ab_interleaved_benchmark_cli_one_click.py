import unittest
import os
import json
import tempfile
import time

from ultra_modules.ab_interleaved_benchmark_cli_one_click import run_cli_one_click

class TestABInterleavedBenchmarkCliOneClick(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_params_default_fallback(self):
        # 1. 缺参默认兜底与自动运行
        output_path = os.path.join(self.temp_dir.name, "report_default.json")
        result = run_cli_one_click(output_path=output_path)

        self.assertEqual(result["status"], "success")
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["snapshot"]["total"], 10)  # 默认 10 个 dummy input

    def test_normal_json_output(self):
        # 2. 正常场景 JSON 输出
        def mock_func_a(item):
            time.sleep(0.001)

        def mock_func_b(item):
            time.sleep(0.001)

        output_path = os.path.join(self.temp_dir.name, "report_normal.json")
        result = run_cli_one_click(
            func_a=mock_func_a,
            func_b=mock_func_b,
            inputs=["a", "b", "c", "d"],
            output_format="json",
            output_path=output_path
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["snapshot"]["total"], 4)

    def test_dirty_data_self_healing(self):
        # 3. 脏数据自愈测试（错误类型输入数据，应该被自动纠正）
        output_path = os.path.join(self.temp_dir.name, "report_dirty.json")
        result = run_cli_one_click(
            inputs="this_is_a_string_not_a_list",  # 脏输入，应该兜底恢复为 dummy_input
            output_path=output_path
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["snapshot"]["total"], 10)  # 默认 10 个 dummy input

    def test_extreme_boundary_single_input(self):
        # 4. 极端边界测试：输入空列表
        output_path = os.path.join(self.temp_dir.name, "report_empty.json")
        result = run_cli_one_click(
            inputs=[],
            output_path=output_path
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["snapshot"]["total"], 1)  # 恢复为单条 dummy

    def test_excel_output(self):
        # 5. Excel 导出测试 (无感回退或直接导出)
        output_path = os.path.join(self.temp_dir.name, "report_excel.xlsx")
        result = run_cli_one_click(
            output_format="excel",
            output_path=output_path
        )

        self.assertEqual(result["status"], "success")
        # 验证是否写入了对应文件（如果有 openpyxl 就是 .xlsx，否则回退到了 .json）
        try:
            import openpyxl
            self.assertTrue(os.path.exists(output_path))
        except ImportError:
            fallback_path = output_path.rsplit(".", 1)[0] + ".json"
            self.assertTrue(os.path.exists(fallback_path))

if __name__ == "__main__":
    unittest.main()

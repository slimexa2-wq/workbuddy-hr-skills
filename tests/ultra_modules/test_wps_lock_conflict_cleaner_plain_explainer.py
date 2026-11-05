import os
import shutil
import tempfile
import unittest
import json

from ultra_modules.wps_lock_conflict_cleaner_plain_explainer import clean_and_explain

class TestWpsLockConflictCleaner(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normal_cleanup_success(self):
        # 1. 正常情况：创建锁文件并清理
        lock_file1 = os.path.join(self.test_dir, "~$test1.xlsx")
        lock_file2 = os.path.join(self.test_dir, ".~lock.test2.docx#")
        normal_file = os.path.join(self.test_dir, "normal.txt")

        with open(lock_file1, "w") as f: f.write("lock")
        with open(lock_file2, "w") as f: f.write("lock")
        with open(normal_file, "w") as f: f.write("content")

        result_md = clean_and_explain(self.test_dir, "markdown")

        # 验证文件是否被清理
        self.assertFalse(os.path.exists(lock_file1))
        self.assertFalse(os.path.exists(lock_file2))
        self.assertTrue(os.path.exists(normal_file))

        # 验证输出文案
        self.assertIn("搞定！成功为您解锁了 2 个被卡住的办公文件", result_md)
        self.assertIn("~$test1.xlsx", result_md)

    def test_dirty_data_self_healing(self):
        # 2. 脏数据自愈：传入不存在的路径
        fake_path = os.path.join(self.test_dir, "does_not_exist_xyz")

        result_json = clean_and_explain(fake_path, "json")
        data = json.loads(result_json)

        self.assertEqual(data["status"], "warning")
        self.assertIn("指定的文件夹不存在", data["summary"])
        self.assertEqual(data["unlocked_count"], 0)

    def test_missing_parameters_fallback(self):
        # 3. 缺参默认兜底：不传参数，默认检查当前目录，输出 markdown
        # 为了不影响真实环境，我们在测试目录执行
        original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            # 创建一个假锁文件
            lock_file = "~$default_test.xlsx"
            with open(lock_file, "w") as f: f.write("lock")

            result = clean_and_explain()
            self.assertFalse(os.path.exists(lock_file))
            self.assertIn("搞定！", result)
            self.assertIn("~$default_test.xlsx", result)
            self.assertIn("办公文档极速卫士", result)
        finally:
            os.chdir(original_cwd)

    def test_zero_lock_files(self):
        # 4. 零锁文件情况
        normal_file = os.path.join(self.test_dir, "just_normal.xlsx")
        with open(normal_file, "w") as f: f.write("data")

        result_html = clean_and_explain(self.test_dir, "html")

        self.assertTrue(os.path.exists(normal_file))
        self.assertIn("太棒了！没有发现任何卡住的文档，一切顺畅！", result_html)
        self.assertIn("办公文档极速卫士", result_html)

    def test_extreme_edge_cases_permission(self):
        # 5. 极端边界情况：锁文件无法删除（权限问题），程序不崩溃，静默跳过
        lock_file = os.path.join(self.test_dir, "~$readonly.xlsx")
        with open(lock_file, "w") as f: f.write("lock")

        # 将文件设置为只读并收回权限，模拟删除失败的情况
        # 在某些 OS 上, 给父文件夹限制写权限能真正阻止删除
        os.chmod(lock_file, 0o400)

        try:
            # 仅仅是为了测试无法删除时的容错性。如果在某些系统如 root 上仍能删除，
            # 我们只需要保证代码不抛错即可。
            # 为了稳定重现无法删除，我们可以 mock os.remove
            import unittest.mock as mock
            with mock.patch("os.remove", side_effect=PermissionError("Permission denied")):
                result = clean_and_explain(self.test_dir, "markdown")
                self.assertIn("太棒了！没有发现任何卡住的文档，一切顺畅！", result) # 因为删除了0个
        finally:
            os.chmod(lock_file, 0o700)

if __name__ == "__main__":
    unittest.main()

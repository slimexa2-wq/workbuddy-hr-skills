import unittest
import time
import os
import tempfile
from ultra_modules.supplier_policy_sqlite_matcher_self_healing_guard import SupplierPolicyMatcher

class TestSupplierPolicyMatcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_matcher.db")
        self.matcher = SupplierPolicyMatcher(self.db_path)

    def tearDown(self):
        self.matcher.conn.close()
        self.temp_dir.cleanup()

    def test_normal_matching(self):
        """测试正常的添加与匹配"""
        self.matcher.add_policy(
            supplier_name="SupplierA", job_type="Engineer",
            start_date="2023-01-01", end_date="2023-12-31",
            step_min=0, step_max=10, unit_price=100.0
        )
        self.matcher.add_policy(
            supplier_name="SupplierA", job_type="Engineer",
            start_date="2023-01-01", end_date="2023-12-31",
            step_min=11, step_max=20, unit_price=90.0
        )

        # 匹配第一个阶梯
        price = self.matcher.match(supplier_name="SupplierA", job_type="Engineer", target_date="2023-06-01", count=5)
        self.assertEqual(price, 100.0)

        # 匹配第二个阶梯
        price = self.matcher.match(supplier_name="SupplierA", job_type="Engineer", target_date="2023-06-01", count=15)
        self.assertEqual(price, 90.0)

        # 匹配不在日期范围内的
        price = self.matcher.match(supplier_name="SupplierA", job_type="Engineer", target_date="2024-01-01", count=5)
        self.assertEqual(price, 0.0)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈（日期格式错乱、阶梯反转等）"""
        self.matcher.add_policy(
            supplier_name=" SupplierB ", # 空格
            job_type=" Designer ",
            start_date="2023/12/31", # 不同的日期格式
            end_date="2023.01.01", # 结束日期早于开始日期，且格式不同
            step_min=20, # step_min > step_max
            step_max=10,
            unit_price="abc 50.5 xyz" # 价格包含非数字字符
        )

        # 期望自愈结果：
        # supplier: SupplierB
        # job: Designer
        # date range: 2023-01-01 to 2023-12-31
        # step range: 10 to 20
        # price: 50.5

        price = self.matcher.match(supplier_name="SupplierB", job_type="Designer", target_date="2023-06-15", count=15)
        self.assertEqual(price, 50.5)

        price = self.matcher.match(supplier_name="SupplierB", job_type="Designer", target_date="2023-06-15", count=25)
        self.assertEqual(price, 0.0)

    def test_missing_parameters_fallback(self):
        """测试缺参兜底机制"""
        self.matcher.add_policy(
            # 全部缺失
        )

        # 缺参会使用默认值：
        # supplier: DEFAULT_SUPPLIER
        # job: DEFAULT_JOB
        # start_date: 1970-01-01
        # end_date: 2099-12-31
        # step_min: 0
        # step_max: 999999999
        # price: 0.0

        price = self.matcher.match(supplier_name=None, job_type=None, target_date=None, count=None)
        self.assertEqual(price, 0.0)

        self.matcher.add_policy(
            unit_price=88.8
        )
        price = self.matcher.match() # 匹配当前日期
        self.assertEqual(price, 88.8)

    def test_5_second_undo_mechanism(self):
        """测试5秒内的撤回机制"""
        self.matcher.add_policy(
            supplier_name="UndoSupplier", job_type="RoleX", unit_price=10.0
        )
        price1 = self.matcher.match(supplier_name="UndoSupplier", job_type="RoleX")
        self.assertEqual(price1, 10.0)

        self.matcher.add_policy(
            supplier_name="UndoSupplier", job_type="RoleX", unit_price=20.0
        )
        price2 = self.matcher.match(supplier_name="UndoSupplier", job_type="RoleX")
        self.assertEqual(price2, 20.0)

        # 撤销最近一次添加（unit_price=20.0的操作）
        success = self.matcher.undo()
        self.assertTrue(success)

        # 应该回退到 unit_price=10.0 的状态
        # 因为 match 是 ORDER BY id DESC LIMIT 1，回退后最新的应该是 10.0（20.0的数据不在了）
        price3 = self.matcher.match(supplier_name="UndoSupplier", job_type="RoleX")
        self.assertEqual(price3, 10.0)

    def test_undo_expiration(self):
        """测试撤回机制过期"""
        self.matcher.add_policy(
            supplier_name="TimeSupplier", job_type="RoleY", unit_price=30.0
        )

        # 人为修改 last_modify_time 模拟超时
        self.matcher.last_modify_time = time.time() - 6.0

        success = self.matcher.undo()
        self.assertFalse(success)

        price = self.matcher.match(supplier_name="TimeSupplier", job_type="RoleY")
        self.assertEqual(price, 30.0)

    def test_extreme_boundaries(self):
        """测试极端边界输入"""
        self.matcher.add_policy(
            supplier_name="A" * 1000, # 超长字符串
            job_type="", # 空字符串
            start_date="0001-01-01", # 极小日期
            end_date="9999-12-31", # 极大日期
            step_min=-9999, # 负数
            step_max=float('inf'), # 无穷大
            unit_price=-100.5 # 负数价格
        )

        price = self.matcher.match(supplier_name="A" * 1000, job_type="", target_date="5000-01-01", count=999999)
        self.assertEqual(price, -100.5)

        # 阶梯为无限大时，_heal_number在字符串转换异常时回退到默认999999999，但对于 float('inf') 会作为浮点数处理，转为 int
        # 测试 float('inf') -> float -> int -> OverflowError or not?
        # 在 python 中 int(float('inf')) 会抛出 OverflowError.
        # 我们需要在 _heal_number 看看：
        # int(float('inf')) -> _heal_number 会发生 Exception，然后返回 default_val。
        # 对于 step_max 它的 default_val 是 999999999，所以会 fallback 到 999999999
        # 所以 count=999999 是在 -9999 到 999999999 之间的。

if __name__ == '__main__':
    unittest.main()

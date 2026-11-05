import unittest
from scripts.cross_month_commission_radar import validate_worker_name, analyze_commissions

class TestCrossMonthCommissionRadar(unittest.TestCase):

    def test_validate_worker_name(self):
        # Valid names
        self.assertTrue(validate_worker_name("张三"))
        self.assertTrue(validate_worker_name("迪丽热巴·牙合甫")) # Contains interpunct
        self.assertTrue(validate_worker_name("阿里木·哈斯木"))

        # Invalid names
        self.assertFalse(validate_worker_name("A")) # Too short
        self.assertFalse(validate_worker_name("123")) # Numbers not allowed
        self.assertFalse(validate_worker_name("John Doe")) # English not allowed
        self.assertFalse(validate_worker_name("张三的非常长的名字超过了十五个中文字符")) # Too long (16 chars)
        self.assertFalse(validate_worker_name("张三*")) # Invalid character

    def test_analyze_commissions_no_anomalies(self):
        historical = [
            {'worker_name': '李四', 'project': '项目A', 'unit_price': 100.0, 'is_backpay': False}
        ]
        current = [
            {'worker_name': '王五', 'project': '项目B', 'unit_price': 150.0, 'is_backpay': False}
        ]
        result = analyze_commissions(current, historical)
        self.assertEqual(result, "无异常发现")

    def test_analyze_commissions_duplicate_claim(self):
        historical = [
            {'worker_name': '张三', 'project': '项目A', 'unit_price': 100.0, 'is_backpay': False}
        ]
        current = [
            {'worker_name': '张三', 'project': '项目A', 'unit_price': 100.0, 'is_backpay': False}
        ]
        result = analyze_commissions(current, historical)
        self.assertIn("重复申领异常: 工人 张三 在项目 项目A 重复申领", result)

    def test_analyze_commissions_unit_price_jump(self):
        historical = [
            {'worker_name': '李四', 'project': '项目B', 'unit_price': 100.0, 'is_backpay': False}
        ]
        current = [
            {'worker_name': '李四', 'project': '项目B', 'unit_price': 120.0, 'is_backpay': False}
        ]
        result = analyze_commissions(current, historical)
        self.assertIn("重复申领异常: 工人 李四 在项目 项目B 重复申领", result)
        self.assertIn("单价跳变异常: 工人 李四 在项目 项目B 单价跳变 (当前: 120.0, 历史: 100.0)", result)

    def test_analyze_commissions_backpay_no_history(self):
        historical = []
        current = [
            {'worker_name': '王五', 'project': '项目C', 'unit_price': 150.0, 'is_backpay': True}
        ]
        result = analyze_commissions(current, historical)
        self.assertIn("跨月补发异常: 工人 王五 在项目 项目C 申领补发，但无历史记录", result)

    def test_analyze_commissions_backpay_unit_price_jump(self):
        historical = [
            {'worker_name': '赵六', 'project': '项目D', 'unit_price': 100.0, 'is_backpay': False}
        ]
        current = [
            {'worker_name': '赵六', 'project': '项目D', 'unit_price': 120.0, 'is_backpay': True}
        ]
        result = analyze_commissions(current, historical)
        self.assertIn("跨月补发异常: 工人 赵六 在项目 项目D 申领补发，单价跳变 (当前: 120.0, 历史: 100.0)", result)

    def test_analyze_commissions_invalid_name(self):
        historical = []
        current = [
            {'worker_name': '张三123', 'project': '项目E', 'unit_price': 100.0, 'is_backpay': False}
        ]
        result = analyze_commissions(current, historical)
        self.assertIn("无效的工人姓名格式: 张三123", result)

if __name__ == '__main__':
    unittest.main()

import unittest
import json
from ultra_modules.zhaopin_greeting_personalizer_integration_bridge import ZhaopinGreetingIntegrationBridge

class TestZhaopinGreetingIntegrationBridge(unittest.TestCase):
    def test_normal_operation_new_schema(self):
        """Test normal operation with standard new schema fields."""
        payload = {
            "candidate_name": "张三",
            "expected_location": "北京",
            "past_companies": ["腾讯", "字节跳动", "百度"],
            "role": "高级后端工程师"
        }
        result = ZhaopinGreetingIntegrationBridge.invoke(payload)
        self.assertIn("张三你好！", result)
        self.assertIn("腾讯、字节跳动等厂区", result)
        self.assertIn("北京", result)
        self.assertIn("高级后端工程师", result)

    def test_forward_compatibility_legacy_schema(self):
        """Test fallback mapping for various legacy schema keys."""
        payload = {
            "c_name": "李四",
            "city": "上海",
            "historyCompanies": "阿里,网易",
            "targetRole": "产品经理"
        }
        result = ZhaopinGreetingIntegrationBridge.invoke(payload)
        self.assertIn("李四你好！", result)
        self.assertIn("阿里、网易厂区", result)
        self.assertIn("上海", result)
        self.assertIn("产品经理", result)

    def test_dirty_data_self_healing(self):
        """Test silent healing of dirty JSON string and malformed JSON payloads."""
        # Valid JSON string
        valid_json_payload = json.dumps({
            "userName": "王五",
            "location": "广州",
            "exp_companies": ["美团"]
        })
        result1 = ZhaopinGreetingIntegrationBridge.invoke(valid_json_payload)
        self.assertIn("王五你好！", result1)
        self.assertIn("美团厂区", result1)
        self.assertIn("广州", result1)

        # Malformed JSON - should fallback to defaults
        malformed_json_payload = "{name: '赵六', missing_quotes...}"
        result2 = ZhaopinGreetingIntegrationBridge.invoke(malformed_json_payload)
        self.assertIn("同学你好！", result2)
        self.assertIn("核心岗位", result2)

    def test_missing_parameters_fallback(self):
        """Test missing parameter fallback (empty, None, partial)."""
        # Empty dict
        payload_empty = {}
        result_empty = ZhaopinGreetingIntegrationBridge.invoke(payload_empty)
        self.assertIn("同学你好！", result_empty)
        self.assertIn("核心岗位", result_empty)

        # Partial with Nones
        payload_partial = {
            "candidate_name": None,
            "role": "测试工程师"
        }
        result_partial = ZhaopinGreetingIntegrationBridge.invoke(payload_partial)
        self.assertIn("同学你好！", result_partial)
        self.assertIn("测试工程师", result_partial)

    def test_extreme_boundary_conditions(self):
        """Test extreme boundary conditions like invalid types and massive lists."""
        # Invalid type (integer)
        result1 = ZhaopinGreetingIntegrationBridge.invoke(12345)
        self.assertIn("同学你好！", result1)
        self.assertIn("核心岗位", result1)

        # Massive list of companies (should truncate to top 2 + "等厂区")
        payload_massive = {
            "candidate_name": "钱七",
            "past_companies": [f"公司{i}" for i in range(100)],
        }
        result2 = ZhaopinGreetingIntegrationBridge.invoke(payload_massive)
        self.assertIn("钱七你好！", result2)
        self.assertIn("公司0、公司1等厂区", result2)
        self.assertNotIn("公司99", result2)

if __name__ == '__main__':
    unittest.main()

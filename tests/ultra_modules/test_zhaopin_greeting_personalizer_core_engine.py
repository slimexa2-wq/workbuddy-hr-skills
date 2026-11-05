import unittest
from ultra_modules.zhaopin_greeting_personalizer_core_engine import generate_greeting

class TestZhaoPinGreetingPersonalizerCoreEngine(unittest.TestCase):
    def test_happy_path_all_params(self):
        """Test with all parameters provided correctly"""
        result = generate_greeting(
            candidate_name="张三",
            expected_location="北京",
            past_companies=["腾讯", "阿里"],
            role="高级开发工程师"
        )
        expected = "张三你好！\n关注到你有腾讯、阿里厂区的经验，同时也期望在北京发展，\n我们目前正在热招高级开发工程师，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

    def test_missing_arguments_defaults(self):
        """Test with missing arguments and None values (default fallbacks)"""
        result = generate_greeting()
        expected = "同学你好！\n我们目前正在热招核心岗位，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

    def test_dirty_data_cleansing(self):
        """Test with dirty strings and empty entries in past companies"""
        result = generate_greeting(
            candidate_name="   李四  ",
            expected_location="  ", # Should be treated as empty
            past_companies=[" 百度 ", "", "  字节跳动", None, "百度"], # Contains duplicates and empties
            role="  产品经理  "
        )
        expected = "李四你好！\n关注到你有百度、字节跳动厂区的经验，\n我们目前正在热招产品经理，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

    def test_past_companies_string_and_truncation(self):
        """Test past_companies as string with multiple delimiters and truncation (> 2 companies)"""
        result = generate_greeting(
            candidate_name="王五",
            expected_location="上海",
            past_companies=" 微软, 谷歌； 苹果 ， 亚马逊 ",
            role="架构师"
        )
        expected = "王五你好！\n关注到你有微软、谷歌等厂区的经验，同时也期望在上海发展，\n我们目前正在热招架构师，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

    def test_boundary_types_invalid_inputs(self):
        """Test with completely invalid boundary types (integers, objects) which should fallback safely"""
        result = generate_greeting(
            candidate_name=12345, # Invalid type, should fallback to "同学"
            expected_location={"city": "Shenzhen"}, # Invalid type, should fallback to ""
            past_companies=456, # Invalid type, should fallback to empty list
            role=["Developer"] # Invalid type, should fallback to "核心岗位"
        )
        expected = "同学你好！\n我们目前正在热招核心岗位，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

    def test_only_location_no_companies(self):
        """Test when only location is provided without companies"""
        result = generate_greeting(
            candidate_name="赵六",
            expected_location="深圳",
            past_companies=[],
            role="前端工程师"
        )
        expected = "赵六你好！\n关注到你期望在深圳发展，\n我们目前正在热招前端工程师，觉得你的过往履历非常匹配。\n期待进一步交流！"
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()

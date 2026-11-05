import unittest
from ultra_modules.zhaopin_greeting_personalizer_anomaly_radar import generate_greetings_and_scan_anomalies

class TestZhaopinGreetingPersonalizerAnomalyRadar(unittest.TestCase):

    def test_normal_usage_and_greetings(self):
        """测试正常使用和生成问候语"""
        candidates = [
            {'name': '张三', 'past_companies': ['腾讯', '网易'], 'expected_location': '深圳', 'job_transitions': 2},
            {'name': '李四', 'past_companies': ['阿里'], 'expected_location': '杭州', 'job_transitions': 1},
            {'name': '王五', 'past_companies': '百度,字节跳动', 'expected_location': '北京', 'job_transitions': 2}
        ]

        results = generate_greetings_and_scan_anomalies(candidates)
        self.assertEqual(len(results), 3)

        # 检查话术生成
        self.assertEqual(results[0]['greeting'], "你好张三，看到你在腾讯的经历很不错，考虑深圳的机会吗？")
        self.assertEqual(results[1]['greeting'], "你好李四，看到你在阿里的经历很不错，考虑杭州的机会吗？")
        self.assertEqual(results[2]['greeting'], "你好王五，看到你在百度的经历很不错，考虑北京的机会吗？")

        # 所有人的跳槽次数都相近，应该都是绿色
        for r in results:
            self.assertEqual(r['anomaly_color'], 'GREEN')
            self.assertEqual(r['anomaly_reason'], '')

    def test_statistical_anomalies_colors(self):
        """测试统计分布异常值标记 (RED, YELLOW, GREEN)"""
        # 创建一个较大的样本集来模拟均值和标准差，使得能够产生明显的 Z-Score
        # 假设 10 个人跳槽 1 次，1 个人跳槽 5 次 (Yellow)，1 个人跳槽 8 次 (Red)
        candidates = [{'name': f'正常人{i}', 'job_transitions': 1} for i in range(10)]
        candidates.append({'name': '稍微频繁者', 'job_transitions': 4})  # Z-score ~ 1.4, Yellow
        candidates.append({'name': '极端频繁者', 'job_transitions': 7})  # Z-score > 2, Red

        results = generate_greetings_and_scan_anomalies(candidates)
        self.assertEqual(len(results), 12)

        red_count = sum(1 for r in results if r['anomaly_color'] == 'RED')
        yellow_count = sum(1 for r in results if r['anomaly_color'] == 'YELLOW')
        green_count = sum(1 for r in results if r['anomaly_color'] == 'GREEN')

        # 应该找到 1 个红色和 1 个黄色
        self.assertEqual(red_count, 1)
        self.assertEqual(yellow_count, 1)
        self.assertEqual(green_count, 10)

        # 检查极端频繁者的原因文本
        extreme = next(r for r in results if r['name'] == '极端频繁者')
        self.assertEqual(extreme['anomaly_color'], 'RED')
        self.assertTrue('跳槽过于频繁' in extreme['anomaly_reason'])

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈（自动计算推断）"""
        candidates = [
            {'name': '脏数据1', 'past_companies': ['A', 'B', 'C'], 'job_transitions': None},  # 应推断为 3 次
            {'name': '脏数据2', 'past_companies': 'X,Y', 'job_transitions': 'invalid'},       # 应推断为 2 次
            {'name': '脏数据3', 'past_companies': None, 'job_transitions': None},             # 应推断为 1 次兜底
            '这不是一个字典',  # 应被静默忽略
            None             # 应被静默忽略
        ]

        results = generate_greetings_and_scan_anomalies(candidates)
        self.assertEqual(len(results), 3)  # 只处理了 3 个字典

        # 所有应该都能正常处理而不崩溃
        for r in results:
            self.assertIn('greeting', r)
            self.assertIn('anomaly_color', r)

    def test_missing_parameter_fallbacks(self):
        """测试缺参兜底"""
        candidates = [
            {}  # 空字典
        ]

        results = generate_greetings_and_scan_anomalies(candidates)
        self.assertEqual(len(results), 1)

        # 检查兜底话术
        r = results[0]
        self.assertEqual(r['greeting'], "你好同学，看到你在您过往平台的经历很不错，考虑我们这边的机会吗？")
        self.assertEqual(r['anomaly_color'], 'GREEN')
        self.assertEqual(r['anomaly_reason'], '')

    def test_extreme_edge_cases(self):
        """测试极端边界情况"""
        # 测试空列表
        self.assertEqual(generate_greetings_and_scan_anomalies([]), [])
        self.assertEqual(generate_greetings_and_scan_anomalies(None), [])

        # 测试单个人（无法计算方差，应该全为 GREEN 且不崩溃）
        single = [{'name': '孤狼', 'job_transitions': 100}]
        res_single = generate_greetings_and_scan_anomalies(single)
        self.assertEqual(res_single[0]['anomaly_color'], 'GREEN')

        # 测试所有人跳槽次数完全一样（标准差为0）
        identical = [{'name': f'人{i}', 'job_transitions': 2} for i in range(5)]
        res_identical = generate_greetings_and_scan_anomalies(identical)
        for r in res_identical:
            self.assertEqual(r['anomaly_color'], 'GREEN')

if __name__ == '__main__':
    unittest.main()

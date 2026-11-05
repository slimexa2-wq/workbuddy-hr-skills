import unittest
from ultra_modules.weekly_leader_brief_writer_anomaly_radar import generate_weekly_leader_brief

class TestWeeklyLeaderBriefWriterAnomalyRadar(unittest.TestCase):
    def test_normal_input_flow(self):
        """测试正常输入数据流"""
        data = [
            {"dept": "研发部", "exit_count": 2, "total_employees": 100},
            {"dept": "销售部", "exit_count": 3, "total_employees": 150},
            {"dept": "市场部", "exit_count": 1, "total_employees": 50},
            {"dept": "人事部", "exit_count": 0, "total_employees": 10},
        ]
        brief = generate_weekly_leader_brief(data)
        self.assertIn("全部 4 个部门在离职率均在正常 🟢 范围内", brief)
        self.assertIn("已静默放行", brief)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈（自动转换类型等）"""
        data = [
            {"dept": "客服部", "exit_count": " 2 ", "total_employees": " 100 "},
            {"dept": "财务部", "exit_count": "invalid", "total_employees": 50},
            {"dept": "运营部", "exit_count": None, "total_employees": "2,000"}
        ]
        brief = generate_weekly_leader_brief(data)
        self.assertIn("全部 3 个部门在离职率均在正常 🟢 范围内", brief)

    def test_missing_param_handling(self):
        """测试缺参情况下的合理默认值处理"""
        brief = generate_weekly_leader_brief()
        self.assertIn("本周无数据", brief)
        self.assertIn("静默放行", brief)

        invalid_type_data = "not a list"
        brief_invalid = generate_weekly_leader_brief(invalid_type_data)
        self.assertIn("输入数据格式异常", brief_invalid)

        empty_list_data = []
        brief_empty = generate_weekly_leader_brief(empty_list_data)
        self.assertIn("本周无数据", brief_empty)

        data = [
            {"department": "设计部", "exits": 1, "headcount": 50},
            {"name": "产品部", "turnover": 2, "total": 100}
        ]
        brief = generate_weekly_leader_brief(data)
        self.assertIn("全部 2 个部门在离职率均在正常 🟢 范围内", brief)

    def test_all_same_values_boundary(self):
        """测试极端边界：所有数据离职率相同（方差为0）"""
        data = [
            {"dept": "A部", "exit_count": 5, "total_employees": 100},
            {"dept": "B部", "exit_count": 5, "total_employees": 100},
            {"dept": "C部", "exit_count": 5, "total_employees": 100},
        ]
        brief = generate_weekly_leader_brief(data)
        self.assertIn("全部 3 个部门在离职率均在正常 🟢 范围内", brief)

    def test_anomaly_highlight(self):
        """测试发现异常并高亮"""
        data = [
            {"dept": f"部门{i}", "exit_count": 1, "total_employees": 100} for i in range(1, 100)
        ]
        # 添加一个极端异常数据，触发 Top 3% 检测
        data.append({"dept": "异常部", "exit_count": 80, "total_employees": 100})

        brief = generate_weekly_leader_brief(data)
        self.assertIn("发现 1 项异常波动需要关注", brief)
        self.assertIn("🔴 异常部：离职 80 人", brief)
        self.assertIn("离职率达50%或以上，存在重大管理或业务风险", brief)
        self.assertIn("其余 99 个部门数据处于正常 🟢 范围", brief)

    def test_anomaly_high_z_score(self):
        """测试由 Z-Score 或 IQR 发现异常并高亮"""
        data = [
            {"dept": f"部门{i}", "exit_count": i % 3 + 1, "total_employees": 100} for i in range(1, 40)
        ]
        # 添加一个显著高于中位数且高于 IQR，但 z-score 不到极端水平的数据
        # exit_rate 均值约 2%，标准差约 0.8%
        # 设置预警部为 4%，使其高于 IQR，但 z-score 约为 2.5
        data.append({"dept": "预警部", "exit_count": 4, "total_employees": 100})

        brief = generate_weekly_leader_brief(data)
        self.assertIn("发现 1 项异常波动需要关注", brief)
        self.assertIn("🟡", brief)
        self.assertIn("预警部", brief)
        self.assertIn("其余 39 个部门数据处于正常 🟢 范围", brief)

if __name__ == "__main__":
    unittest.main()

import unittest
from ultra_modules.resume_fast_scorer_integration_bridge import ResumeFastScorerIntegrationBridge

class TestResumeFastScorerIntegrationBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = ResumeFastScorerIntegrationBridge()

    def test_normal_data_matching(self):
        """测试正常的新老数据格式无缝桥接与匹配"""
        # 测试旧版本格式
        old_resume = {
            'candidate_name': '张三',
            'candidate_age': 28,
            'work_years': 5,
            'tech_stack': ['Python', 'Java']
        }

        # 测试新版本格式
        new_resume = {
            '姓名': '李四',
            '年龄': 29,
            '工龄': 6,
            '技能': 'Python; Java, C++'
        }

        project_req = {
            'min_age': 25,
            'max_age': 35,
            'min_experience_years': 3,
            'required_skills': ['python', 'java']
        }

        res_old = self.bridge.score(old_resume, project_req)
        self.assertEqual(res_old['score'], 100.0)
        self.assertTrue(res_old['is_qualified'])
        self.assertEqual(len(res_old['matched_skills']), 2)

        res_new = self.bridge.score(new_resume, project_req)
        self.assertEqual(res_new['score'], 100.0)
        self.assertTrue(res_new['is_qualified'])
        self.assertEqual(len(res_new['matched_skills']), 2)

    def test_dirty_data_self_healing(self):
        """测试脏数据自愈能力（字符串转数字、非预期类型等）"""
        dirty_resume = {
            'age': '30.5', # 字符串浮点数
            'experience_years': '三年', # 无法转换，依赖正文自愈
            'skills': None, # 异常类型
            'resume_text': '本人30岁，工作经验：4年，熟练掌握 Python 和 React 技能。'
        }

        project_req = {
            'min_experience_years': 3,
            'required_skills': 'python, react'
        }

        result = self.bridge.score(dirty_resume, project_req)
        # age 可以从 '30.5' 转换为 30
        self.assertEqual(result['normalized_data']['age'], 30)
        # experience_years '三年' 转换失败，但从 resume_text "工作经验：4年" 中提取出 4
        self.assertEqual(result['normalized_data']['experience_years'], 4)
        # skills 从 None 恢复，并从文本提取到 python, react
        self.assertIn('python', result['normalized_data']['skills'])
        self.assertIn('react', result['normalized_data']['skills'])
        self.assertEqual(result['score'], 100.0)

    def test_missing_parameter_defaults(self):
        """测试缺参默认兜底（零配置容错）"""
        empty_resume = {}
        empty_req = None # 非字典输入

        result = self.bridge.score(empty_resume, empty_req) # type: ignore

        # 默认要求：min_age=0, max_age=100, min_exp=0, req_skills=[]
        # 但缺失 age 扣 5 分，缺失 exp 扣 10 分
        self.assertEqual(result['score'], 85.0)
        self.assertTrue(result['is_qualified'])
        self.assertEqual(result['normalized_data']['name'], 'Unknown')

    def test_extreme_boundaries(self):
        """测试极端边界情况（应届生、极大年龄、无技能要求等）"""
        fresh_resume = {
            'is_fresh_graduate': True,
            'age': 22
        }

        project_req_high_exp = {
            'min_experience_years': 5
        }

        result = self.bridge.score(fresh_resume, project_req_high_exp)
        self.assertEqual(result['normalized_data']['experience_years'], 0)
        # 经验不足扣 30 分
        self.assertEqual(result['score'], 70.0)
        self.assertTrue(result['is_qualified'])

        # 极端不合格
        unqualified_req = {
            'min_experience_years': 5,
            'min_age': 25,
            'required_skills': ['java', 'spring', 'mysql', 'redis']
        }
        unqualified_res = self.bridge.score(fresh_resume, unqualified_req)
        # 经验不足 -30, 年龄不足 -20, 缺 4 个技能 -50 = 0 分
        self.assertEqual(unqualified_res['score'], 0.0)
        self.assertFalse(unqualified_res['is_qualified'])

    def test_text_extraction(self):
        """测试从自由文本中秒级提取关键信息"""
        text = "我是王五，Age 28，目前已经工作了5年。我的技术栈主要是 golang 和 docker，熟悉 k8s 部署。"
        resume = {
            'text_content': text
        }

        req = {
            'required_skills': ['golang', 'docker', 'k8s', 'python']
        }

        res = self.bridge.score(resume, req)
        self.assertEqual(res['normalized_data']['age'], 28)
        self.assertEqual(res['normalized_data']['experience_years'], 5)
        self.assertIn('golang', res['matched_skills'])
        self.assertIn('docker', res['matched_skills'])
        self.assertIn('k8s', res['matched_skills'])
        self.assertIn('python', res['missing_skills'])

        # 扣分：缺1个技能，总技能4个，每个扣 12.5 分
        self.assertEqual(res['score'], 87.5)

if __name__ == '__main__':
    unittest.main()

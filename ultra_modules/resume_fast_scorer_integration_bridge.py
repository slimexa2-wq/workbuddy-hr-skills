import re

class ResumeFastScorerIntegrationBridge:
    def __init__(self):
        pass

    def _extract_from_text(self, text: str) -> dict:
        """
        从自由格式的简历文本中秒级提取年龄、工龄和技能。
        """
        if not isinstance(text, str):
            text = str(text) if text else ""

        extracted = {
            'age': None,
            'experience_years': None,
            'skills': []
        }

        # 提取年龄：匹配 "年龄: 25", "25岁", "Age 25" 等
        age_match = re.search(r'(?:年龄|岁数|age)[\s:：]*(\d{2})|(\d{2})\s*(?:岁|years?\s*old)', text, re.IGNORECASE)
        if age_match:
            extracted['age'] = int(age_match.group(1) or age_match.group(2))

        # 提取工龄：匹配 "5年经验", "工作了5年", "工龄: 5年", "Experience: 5 years" 等
        exp_match = re.search(r'(?:经验|工龄|工作|experience)[\s:：]*(?:了)?(\d+)\s*(?:年|year|yr)|(\d+)\s*(?:年|year|yr)(?:的|工作)?(?:经验|experience)', text, re.IGNORECASE)
        if exp_match:
            extracted['experience_years'] = int(exp_match.group(1) or exp_match.group(2))

        if "应届" in text or "fresh graduate" in text.lower():
            if extracted['experience_years'] is None:
                extracted['experience_years'] = 0

        common_skills = ['python', 'java', 'c++', 'javascript', 'react', 'vue', 'node', 'sql', 'aws', 'docker', 'k8s', 'golang', 'rust', 'c#', 'php', 'ruby', 'spring', 'mysql', 'redis']
        text_lower = text.lower()
        for skill in common_skills:
            # 避免中文字符边界问题，使用前后非字母数字断言
            escaped_skill = re.escape(skill)
            pattern = r'(?<![a-zA-Z0-9])' + escaped_skill + r'(?![a-zA-Z0-9])'
            if re.search(pattern, text_lower):
                extracted['skills'].append(skill)

        return extracted

    def normalize_resume_data(self, resume_data: dict) -> dict:
        """
        自动识别新旧版本字段差异并静默映射转换，处理脏数据自愈，缺参默认兜底。
        """
        if not isinstance(resume_data, dict):
            resume_data = {}

        normalized = {
            'name': 'Unknown',
            'age': None,
            'experience_years': None,
            'skills': [],
            'education': 'Unknown',
            'text_content': ''
        }

        normalized['name'] = resume_data.get('name') or resume_data.get('candidate_name') or resume_data.get('姓名') or 'Unknown'

        # 提取或映射 Age
        age = resume_data.get('age') or resume_data.get('candidate_age') or resume_data.get('年龄')
        if age is not None:
            try:
                normalized['age'] = int(float(age))
            except (ValueError, TypeError):
                pass

        # 提取或映射 Experience
        exp = resume_data.get('experience_years') or resume_data.get('work_years') or resume_data.get('工龄') or resume_data.get('经验')
        if exp is not None:
            try:
                normalized['experience_years'] = int(float(exp))
            except (ValueError, TypeError):
                pass
        elif resume_data.get('is_fresh_graduate') or resume_data.get('应届生'):
            normalized['experience_years'] = 0

        # 提取或映射 Skills
        skills = resume_data.get('skills') or resume_data.get('tech_stack') or resume_data.get('技能')
        if isinstance(skills, list):
            normalized['skills'] = [str(s).lower() for s in skills if s]
        elif isinstance(skills, str):
            normalized['skills'] = [s.strip().lower() for s in re.split(r'[,;，；|/]', skills) if s.strip()]

        # 提取或映射 Education
        normalized['education'] = resume_data.get('education') or resume_data.get('degree') or resume_data.get('学历') or 'Unknown'

        # 提取文本内容以备回退
        text = resume_data.get('text_content') or resume_data.get('resume_text') or resume_data.get('简历正文') or resume_data.get('description') or ''
        normalized['text_content'] = str(text)

        # 如果核心字段缺失且有文本内容，则使用正则提取回退
        if normalized['text_content']:
            extracted = self._extract_from_text(normalized['text_content'])
            if normalized['age'] is None:
                normalized['age'] = extracted['age']
            if normalized['experience_years'] is None:
                normalized['experience_years'] = extracted['experience_years']

            # 合并技能并去重
            current_skills = set(normalized['skills'])
            current_skills.update(extracted['skills'])
            normalized['skills'] = list(current_skills)

        return normalized

    def score(self, resume_data: dict, project_requirements: dict) -> dict:
        """
        根据在招项目条件与简历匹配打分，实现跨系统数据契约无缝桥接。
        零配置容错，缺参自动设合理默认值。
        """
        if not isinstance(project_requirements, dict):
            project_requirements = {}

        # 缺参自动兜底
        min_age = project_requirements.get('min_age', 0)
        max_age = project_requirements.get('max_age', 100)
        min_exp = project_requirements.get('min_experience_years', 0)
        required_skills = project_requirements.get('required_skills', [])

        if isinstance(required_skills, str):
            required_skills = [s.strip().lower() for s in re.split(r'[,;，；|/]', required_skills) if s.strip()]
        elif isinstance(required_skills, list):
            required_skills = [str(s).lower() for s in required_skills if s]
        else:
            required_skills = []

        norm_resume = self.normalize_resume_data(resume_data)

        base_score = 100.0
        penalties = 0.0

        # 年龄校验
        age = norm_resume['age']
        if age is not None:
            if age < min_age or age > max_age:
                penalties += 20.0
        else:
            # 缺失年龄，小额惩罚
            penalties += 5.0

        # 工龄校验
        exp = norm_resume['experience_years']
        if exp is not None:
            if exp < min_exp:
                penalties += 30.0
        else:
            # 缺失工龄，小额惩罚
            penalties += 10.0

        # 技能校验
        matched_skills = []
        missing_skills = []

        text_content_lower = norm_resume['text_content'].lower()

        for req_skill in required_skills:
            if req_skill in norm_resume['skills']:
                matched_skills.append(req_skill)
            else:
                # 文本级深度匹配兜底
                escaped_req_skill = re.escape(req_skill)
                pattern = r'(?<![a-zA-Z0-9])' + escaped_req_skill + r'(?![a-zA-Z0-9])'
                if re.search(pattern, text_content_lower):
                    matched_skills.append(req_skill)
                else:
                    missing_skills.append(req_skill)

        if required_skills:
            # 技能缺失按比例扣分，最高扣 50 分
            skill_penalty_per_missing = 50.0 / len(required_skills)
            penalties += skill_penalty_per_missing * len(missing_skills)

        final_score = max(0.0, base_score - penalties)

        return {
            'score': round(final_score, 2),
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'is_qualified': final_score >= 60.0,
            'normalized_data': norm_resume
        }

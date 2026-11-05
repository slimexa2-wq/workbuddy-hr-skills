import re
import math

class ResumeFastScorerExportFormatter:
    @staticmethod
    def parse(text: str) -> dict:
        """
        Parses resume text with extreme self-healing for dirty/missing data.
        """
        if text is None or (isinstance(text, float) and math.isnan(text)):
            return {"age": 0, "experience": 0, "skills": []}

        if not isinstance(text, str):
            text = str(text)

        text = text.replace('\n', ' ').replace('\r', ' ')

        # Self-healing missing values defaults
        age = 0
        exp = 0
        skills = []

        age_match = re.search(r'(?:年龄|今年)[:：\s]*(\d{2})(?:\s*岁)?|(\d{2})\s*岁', text)
        if age_match:
            age_str = age_match.group(1) or age_match.group(2)
            if age_str:
                age = int(age_str)

        exp_match = re.search(r'(?:工龄|经验|工作)[:：\s]*(\d{1,2})(?:\s*年)?|(\d{1,2})\s*年(?:工作经验|经验|工龄)', text)
        if exp_match:
            exp_str = exp_match.group(1) or exp_match.group(2)
            if exp_str:
                exp = int(exp_str)

        skill_match = re.search(r'(?:技能|掌握|精通)[:：\s]*([a-zA-Z0-9,\+ \.\#、，]+)', text)
        if skill_match:
            raw_skills = skill_match.group(1)
            skills = [s.strip() for s in re.split(r'[,，、\s]+', raw_skills) if s.strip()]

        return {"age": age, "experience": exp, "skills": skills}

    @staticmethod
    def score(parsed_data: dict, requirements: dict = None) -> int:
        """
        Calculates match score with default fallback.
        """
        if not requirements:
            requirements = {}

        score = 100
        req_age = requirements.get('max_age')
        if req_age is not None and parsed_data['age'] > req_age:
            score -= (parsed_data['age'] - req_age) * 10

        req_exp = requirements.get('min_exp')
        if req_exp is not None and parsed_data['experience'] < req_exp:
            score -= (req_exp - parsed_data['experience']) * 15

        req_skills = requirements.get('required_skills')
        if req_skills:
            resume_skills_lower = [s.lower() for s in parsed_data['skills']]
            missing = sum(1 for s in req_skills if s.lower() not in resume_skills_lower)
            score -= missing * 20

        return max(0, score)

    @staticmethod
    def format_export(resume_text: str = None, project_requirements: dict = None) -> dict:
        """
        Main capability:
        1) 零批注纯净导出与微信/飞书一键复制汇报简报
        2) 导出数据comments=0、数值格无NaN/None
        3) 3行极简汇报文案
        """
        parsed = ResumeFastScorerExportFormatter.parse(resume_text)
        score = ResumeFastScorerExportFormatter.score(parsed, project_requirements)

        skills_str = "、".join(parsed["skills"]) if parsed["skills"] else "无明确技能"

        report = (
            f"【匹配度】综合打分：{score}分\n"
            f"【画像】年龄{parsed['age']}岁 | 工龄{parsed['experience']}年\n"
            f"【技能】{skills_str}"
        )

        # Clean export data logic
        export_data = {
            "age": parsed["age"] if parsed["age"] is not None and not (isinstance(parsed["age"], float) and math.isnan(parsed["age"])) else 0,
            "experience": parsed["experience"] if parsed["experience"] is not None and not (isinstance(parsed["experience"], float) and math.isnan(parsed["experience"])) else 0,
            "skills": skills_str if skills_str else "无明确技能",
            "match_score": score if score is not None else 0,
            "comments": 0
        }

        return {
            "export_data": export_data,
            "report": report
        }

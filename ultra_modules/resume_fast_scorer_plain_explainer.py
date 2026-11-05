import re
import json
from datetime import datetime

class PlainExplainer:
    """大白话结论卡包装器，提供 HTML/JSON/Markdown 极简导出"""
    def __init__(self, data: dict):
        self.data = data

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        d = self.data
        ext = d.get("extracted", {})

        age_str = f'{ext.get("age")} 岁' if ext.get("age") is not None else "未知"
        exp_str = f'{ext.get("experience_years")} 年' if ext.get("experience_years") is not None else "未知"
        skills_str = ", ".join(ext.get("skills", [])) if ext.get("skills") else "无"

        md = f"""# 简历匹配评估报告

## 结论摘要
**综合得分：** {d.get('score', 0)} 分
**一句话建议：** {d.get('verdict', '')}

## 候选人核心画像
- **年龄：** {age_str}
- **工作经验：** {exp_str}
- **命中的技能点：** {skills_str}

## 扣分详情说明
"""
        deductions = d.get("deductions", [])
        if not deductions:
            md += "- 满分匹配，无任何扣分项！\n"
        else:
            for item in deductions:
                md += f"- {item}\n"

        return md

    def to_html(self) -> str:
        d = self.data
        ext = d.get("extracted", {})
        score = d.get("score", 0)

        age_str = f'{ext.get("age")} 岁' if ext.get("age") is not None else "未知"
        exp_str = f'{ext.get("experience_years")} 年' if ext.get("experience_years") is not None else "未知"
        skills_str = ", ".join(ext.get("skills", [])) if ext.get("skills") else "无"

        deductions_html = ""
        deductions = d.get("deductions", [])
        if not deductions:
            deductions_html = "<li>满分匹配，无任何扣分项！</li>"
        else:
            for item in deductions:
                deductions_html += f"<li>{item}</li>"

        bg_color = "#e6f4ea" if score >= 80 else "#fef7e0" if score >= 60 else "#fce8e6"
        text_color = "#137333" if score >= 80 else "#b06000" if score >= 60 else "#c5221f"

        html = f"""<div class="resume-plain-card" style="max-width: 600px; border: 1px solid #eaeaea; padding: 24px; border-radius: 12px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
  <h2 style="color: #1a1a1a; margin-top: 0; font-size: 20px;">简历匹配评估报告</h2>
  <div style="background-color: {bg_color}; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
    <h3 style="margin: 0; color: {text_color}; font-size: 18px;">得分: {score} 分 —— {d.get('verdict', '')}</h3>
  </div>
  <h3 style="color: #333; font-size: 16px; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 12px;">👤 核心画像</h3>
  <ul style="list-style-type: none; padding-left: 0; margin-bottom: 24px; color: #4a4a4a;">
    <li style="margin-bottom: 8px;"><strong>年龄:</strong> {age_str}</li>
    <li style="margin-bottom: 8px;"><strong>经验:</strong> {exp_str}</li>
    <li style="margin-bottom: 8px;"><strong>技能:</strong> {skills_str}</li>
  </ul>
  <h3 style="color: #333; font-size: 16px; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 12px;">⚠️ 详情说明</h3>
  <ul style="color: #666; padding-left: 20px;">
    {deductions_html}
  </ul>
</div>"""
        return html


class ResumeFastScorer:
    """
    智联/BOSS简历文本秒级提取与打分器
    零配置容错、缺参自动设合理默认值，脏数据自愈
    """
    def __init__(self, default_requirements=None):
        if not isinstance(default_requirements, dict):
            default_requirements = {}
        self.default_requirements = default_requirements

    def _extract_info(self, text: str) -> dict:
        """从简历文本中提取年龄、经验。脏数据自愈处理。"""
        # 脏数据兜底
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        # 清洗特殊字符，换行等
        cleaned_text = text.replace('\r', ' ').replace('\n', ' ').strip()

        info = {
            "age": None,
            "experience_years": None,
            "skills": []
        }

        if not cleaned_text:
            return info, cleaned_text

        # 提取年龄：匹配 "25岁"、"25 岁"、"年龄25" 等
        age_match = re.search(r'(?:年龄\s*)?(\d{2})\s*岁', cleaned_text)
        if age_match:
            info["age"] = int(age_match.group(1))
        else:
            age_match = re.search(r'年龄[:：]?\s*(\d{2})', cleaned_text)
            if age_match:
                info["age"] = int(age_match.group(1))
            else:
                # 尝试匹配出生年份 "1995年"
                birth_year_match = re.search(r'(19\d{2}|20\d{2})\s*年(?:生|出生)?', cleaned_text)
                if birth_year_match:
                    current_year = datetime.now().year
                    info["age"] = current_year - int(birth_year_match.group(1))

        # 提取经验：匹配 "3年经验"、"3年工作经验"、"经验3年" 等
        exp_match = re.search(r'(\d{1,2})\s*年(?:的)?(?:工作)?经验', cleaned_text)
        if exp_match:
            info["experience_years"] = int(exp_match.group(1))
        else:
            exp_match = re.search(r'(?:工作)?经验[:：]?\s*(\d{1,2})\s*年', cleaned_text)
            if exp_match:
                info["experience_years"] = int(exp_match.group(1))
            else:
                # 应届生处理
                if re.search(r'应届(生|毕业生)|在校(生)|实习(生)', cleaned_text):
                    info["experience_years"] = 0

        return info, cleaned_text

    def score_and_explain(self, resume_text: str, requirements: dict = None) -> PlainExplainer:
        """
        进行匹配打分并返回大白话卡片对象
        """
        # 缺参默认兜底
        if not isinstance(requirements, dict):
            requirements = self.default_requirements

        min_age = requirements.get("min_age", 18)
        max_age = requirements.get("max_age", 65)
        min_exp = requirements.get("min_experience_years", 0)
        req_skills = requirements.get("required_skills", [])

        if not isinstance(req_skills, list):
            req_skills = [req_skills] if isinstance(req_skills, str) else []

        extracted, cleaned_text = self._extract_info(resume_text)

        score = 100
        deductions = []

        # 1. 评估年龄
        age = extracted["age"]
        if age is not None:
            if age < min_age:
                deduction = 20
                score -= deduction
                deductions.append(f"年龄 {age} 岁偏小，低于要求下限 {min_age} 岁 (扣{deduction}分)")
            elif age > max_age:
                deduction = 20
                score -= deduction
                deductions.append(f"年龄 {age} 岁偏大，超出要求上限 {max_age} 岁 (扣{deduction}分)")
        else:
            deduction = 10
            score -= deduction
            deductions.append(f"未能从简历中提取到年龄信息 (扣{deduction}分)")

        # 2. 评估经验
        exp = extracted["experience_years"]
        if exp is not None:
            if exp < min_exp:
                deduction = 30
                score -= deduction
                deductions.append(f"工龄 {exp} 年不足，低于要求的 {min_exp} 年 (扣{deduction}分)")
        else:
            deduction = 10
            score -= deduction
            deductions.append(f"未能从简历中提取到工作年限 (扣{deduction}分)")

        # 3. 评估技能
        found_skills = []
        missing_skills = []
        for skill in req_skills:
            if not isinstance(skill, str) or not skill.strip():
                continue
            # 严格遵守非破坏性正则匹配，忽略大小写
            if re.search(re.escape(skill.strip()), cleaned_text, re.IGNORECASE):
                found_skills.append(skill.strip())
            else:
                missing_skills.append(skill.strip())

        extracted["skills"] = found_skills
        valid_req_skills_count = len(found_skills) + len(missing_skills)

        if valid_req_skills_count > 0:
            skill_score = 40 * (len(found_skills) / valid_req_skills_count)
            deduction = int(40 - skill_score)
            if deduction > 0:
                score -= deduction
                missing_str = ", ".join(missing_skills)
                deductions.append(f"缺少岗位要求的关键技能：{missing_str} (扣{deduction}分)")

        # 分数兜底
        score = max(0, min(100, int(score)))

        # 结论评语
        if score >= 85:
            verdict = "极度匹配，建议HR或业务立即安排面试！"
        elif score >= 60:
            verdict = "基本匹配，可作为备选人才库。"
        else:
            verdict = "匹配度较低，建议直接淘汰。"

        result = {
            "score": score,
            "verdict": verdict,
            "extracted": extracted,
            "deductions": deductions,
            "requirements": {
                "min_age": min_age,
                "max_age": max_age,
                "min_experience_years": min_exp,
                "required_skills": req_skills
            }
        }

        return PlainExplainer(result)

def analyze_resume(resume_text: str, requirements: dict = None) -> PlainExplainer:
    """
    一键直达入口：直接传入简历和要求字典，返回可导出的分析报告。
    """
    scorer = ResumeFastScorer()
    return scorer.score_and_explain(resume_text, requirements)

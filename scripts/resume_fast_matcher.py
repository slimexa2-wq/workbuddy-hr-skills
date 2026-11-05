import re
import json
from typing import Dict, Any, List

class ResumeFastMatcher:
    def __init__(self):
        # Regex patterns for basic extraction
        self.phone_pattern = re.compile(r'1[3-9]\d{9}')
        self.email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
        self.edu_pattern = re.compile(r'(高中|中专|大专|本科|硕士|博士)')
        self.name_pattern = re.compile(r'姓名[：:]?\s*([\u4e00-\u9fa5]{2,4})')
        self.age_pattern = re.compile(r'(\d{2})\s*岁')
        self.exp_pattern = re.compile(r'(\d+)\s*年(?:工作)?经验')

    def extract_elements(self, text: str) -> Dict[str, Any]:
        """Extracts core elements from noisy resume text."""

        # Phone
        phone_match = self.phone_pattern.search(text)
        phone = phone_match.group(0) if phone_match else None

        # Email
        email_match = self.email_pattern.search(text)
        email = email_match.group(0) if email_match else None

        # Education
        # Find all education levels mentioned, keep the highest or just all
        edu_matches = self.edu_pattern.findall(text)
        # Simple hierarchy mapping to find the highest
        edu_hierarchy = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "中专": 2, "高中": 1}
        best_edu = None
        if edu_matches:
            best_edu = max(edu_matches, key=lambda e: edu_hierarchy.get(e, 0))

        # Name
        name_match = self.name_pattern.search(text)
        name = name_match.group(1) if name_match else None

        # Age
        age_match = self.age_pattern.search(text)
        age = int(age_match.group(1)) if age_match else None

        # Experience
        exp_match = self.exp_pattern.search(text)
        exp_years = int(exp_match.group(1)) if exp_match else None

        return {
            "name": name,
            "phone": phone,
            "email": email,
            "education": best_edu,
            "age": age,
            "experience_years": exp_years
        }

    def match_roles(self, text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Matches candidate against roles based on keywords and generates a recommendation."""

        # Keywords for matching
        blue_collar_keywords = ["流水线", "普工", "操作工", "装配", "包装", "搬运", "保安", "保洁", "车间"]
        manufacturing_keywords = ["数控", "机床", "冲压", "焊工", "钳工", "电工", "维修", "CNC", "制造", "工艺", "模具", "机械"]
        hr_keywords = ["招聘", "薪酬", "绩效", "培训", "员工关系", "HR", "人事", "行政", "人力资源"]

        blue_collar_score = sum(1 for kw in blue_collar_keywords if kw in text)
        manufacturing_score = sum(1 for kw in manufacturing_keywords if kw in text)
        hr_score = sum(1 for kw in hr_keywords if kw in text)

        scores = {
            "蓝领岗位": blue_collar_score,
            "制造岗位": manufacturing_score,
            "人事岗位": hr_score
        }

        best_match_role = max(scores, key=scores.get)
        best_score = scores[best_match_role]

        if best_score == 0:
            recommended_role = "通用岗位"
            recommendation_reason = "未提取到明显的专业技能关键词，建议根据实际需求进行通用岗位匹配。"
        else:
            recommended_role = best_match_role
            if best_match_role == "蓝领岗位":
                recommendation_reason = f"候选人简历中包含 {blue_collar_score} 个蓝领相关关键词，适合从事车间普工或基础操作类工作。"
            elif best_match_role == "制造岗位":
                recommendation_reason = f"候选人简历中包含 {manufacturing_score} 个制造/技能相关关键词，具备一定的专业制造或设备操作技能。"
            else:
                recommendation_reason = f"候选人简历中包含 {hr_score} 个人事相关关键词，适合从事人力资源、行政或相关管理支持类工作。"

        # Additional constraints logic for reasons
        if recommended_role != "通用岗位":
            if profile.get("experience_years") and profile["experience_years"] >= 5:
                recommendation_reason += " 候选人拥有丰富的经验，可考虑作为资深员工或组长。"
            if profile.get("education") in ["本科", "硕士", "博士"] and recommended_role == "人事岗位":
                recommendation_reason += " 候选人学历较高，符合该岗位的进阶要求。"

        return {
            "profile": profile,
            "scores": scores,
            "recommended_role": recommended_role,
            "recommendation_reason": recommendation_reason
        }

    def process_resume(self, text: str) -> Dict[str, Any]:
        """End-to-end processing of a noisy resume text."""
        profile = self.extract_elements(text)
        result = self.match_roles(text, profile)
        return result

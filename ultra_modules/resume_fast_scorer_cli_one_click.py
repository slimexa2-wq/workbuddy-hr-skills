import sys
import json
import argparse
import logging
import re
from datetime import datetime
try:
    import openpyxl
except ImportError:
    openpyxl = None

# Configure extremely simple default logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def get_default_requirements():
    return {
        "min_age": 18,
        "max_age": 40,
        "min_experience_years": 1,
        "required_skills": ["Python", "沟通能力"]
    }

def fallback_resume_text():
    return """
    候选人简历
    基本信息：
    年龄：25岁
    工作经验：3年
    技能：熟练掌握 Python，具备良好的沟通能力，熟悉数据分析。
    自我评价：
    热爱编程，能够独立完成模块开发。
    """

class ResumeFastScorerCli:
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
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        cleaned_text = text.replace('\r', ' ').replace('\n', ' ').strip()
        info = {"age": None, "experience_years": None, "skills": []}

        if not cleaned_text:
            return info, cleaned_text

        # 提取年龄
        age_match = re.search(r'(?:年龄\s*)?(\d{2})\s*岁', cleaned_text)
        if age_match:
            info["age"] = int(age_match.group(1))
        else:
            age_match = re.search(r'年龄[:：]?\s*(\d{2})', cleaned_text)
            if age_match:
                info["age"] = int(age_match.group(1))
            else:
                birth_year_match = re.search(r'(19\d{2}|20\d{2})\s*年(?:生|出生)?', cleaned_text)
                if birth_year_match:
                    current_year = datetime.now().year
                    info["age"] = current_year - int(birth_year_match.group(1))

        # 提取经验
        exp_match = re.search(r'(\d{1,2})\s*年(?:的)?(?:工作)?经验', cleaned_text)
        if exp_match:
            info["experience_years"] = int(exp_match.group(1))
        else:
            exp_match = re.search(r'(?:工作)?经验[:：]?\s*(\d{1,2})\s*年', cleaned_text)
            if exp_match:
                info["experience_years"] = int(exp_match.group(1))
            else:
                if re.search(r'应届(生|毕业生)|在校(生)|实习(生)', cleaned_text):
                    info["experience_years"] = 0

        return info, cleaned_text

    def score_and_explain(self, resume_text: str, requirements: dict = None) -> dict:
        """
        进行匹配打分并返回结果字典
        """
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

        score = max(0, min(100, int(score)))

        if score >= 85:
            verdict = "极度匹配，建议HR或业务立即安排面试！"
        elif score >= 60:
            verdict = "基本匹配，可作为备选人才库。"
        else:
            verdict = "匹配度较低，建议直接淘汰。"

        return {
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

def analyze_resume(resume_text: str, requirements: dict = None) -> dict:
    scorer = ResumeFastScorerCli(default_requirements=get_default_requirements())
    return scorer.score_and_explain(resume_text, requirements)

def run_one_click_scorer(resume_text=None, requirements=None, output_prefix="resume_score_result"):
    """
    一键直达入口，缺省参数自动兜底，脏数据自动治愈。
    """
    if not resume_text:
        resume_text = fallback_resume_text()
        logging.info("未提供简历文本，使用系统内置默认简历数据跑通全流程。")

    if not requirements:
        requirements = get_default_requirements()
        logging.info("未提供打分要求，使用系统默认基础要求进行匹配。")

    try:
        # 执行核心打分逻辑
        result_data = analyze_resume(resume_text, requirements)

        # 导出为 JSON
        json_output = f"{output_prefix}.json"
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        logging.info(f"JSON 报告已生成: {json_output}")

        # 导出为 Excel (如果环境中有 openpyxl)
        if openpyxl:
            excel_output = f"{output_prefix}.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "简历打分报告"

            # 写入表头
            headers = ["评估项", "评估结果/详情"]
            ws.append(headers)

            # 写入内容
            ws.append(["综合得分", result_data.get("score", 0)])
            ws.append(["一句话建议", result_data.get("verdict", "")])

            ext = result_data.get("extracted", {})
            ws.append(["提取年龄", ext.get("age", "未知")])
            ws.append(["提取经验(年)", ext.get("experience_years", "未知")])
            ws.append(["匹配技能", ", ".join(ext.get("skills", [])) if ext.get("skills") else "无"])

            deductions = result_data.get("deductions", [])
            deduction_str = "\n".join(deductions) if deductions else "满分匹配，无任何扣分项！"
            ws.append(["扣分详情", deduction_str])

            wb.save(excel_output)
            logging.info(f"Excel 报告已生成: {excel_output}")
        else:
            logging.warning("未检测到 openpyxl 库，跳过 Excel 导出。")

        return result_data

    except Exception as e:
        logging.error(f"打分流程异常中断 (已兜底处理): {e}")
        return {"error": str(e), "score": 0}

def main():
    parser = argparse.ArgumentParser(description="智联/BOSS简历文本秒级提取年龄/工龄/技能打分器（零参数一键版）")
    parser.add_argument("--resume", type=str, help="(可选) 简历文本内容", default=None)
    parser.add_argument("--prefix", type=str, help="(可选) 输出文件前缀", default="resume_score_result")
    args = parser.parse_args()

    run_one_click_scorer(resume_text=args.resume, output_prefix=args.prefix)

if __name__ == "__main__":
    main()

import re
import math
from typing import List, Dict, Any, Optional

class ResumeAnomalyRadar:
    def __init__(self, job_requirements: Optional[Dict[str, Any]] = None):
        """
        初始化打分与异常雷达。
        零配置容错，缺参自动设合理默认值，静默自愈。
        """
        self.job_requirements = job_requirements or {}

        self.min_age = self.job_requirements.get('min_age', 18)
        self.max_age = self.job_requirements.get('max_age', 65)
        self.min_experience = self.job_requirements.get('min_experience', 0)
        self.required_skills = [str(s).lower() for s in self.job_requirements.get('required_skills', [])]

    def _extract_age(self, text: str) -> int:
        if not isinstance(text, str):
            return 25
        match = re.search(r'(?:年龄\s*[:：]?\s*|\b)(\d{2})(?:\s*岁\b|\b)', text)
        if match:
            age = int(match.group(1))
            if 16 <= age <= 100:
                return age
        match_birth = re.search(r'(?:出生|生日)\s*[:：]?\s*(19\d{2}|20\d{2})', text)
        if match_birth:
            return 2024 - int(match_birth.group(1))
        return 25

    def _extract_experience(self, text: str) -> int:
        if not isinstance(text, str):
            return 0
        match = re.search(r'(?:工作经验|工龄|经验)\s*[:：]?\s*(\d+)\s*年', text)
        if match:
            return int(match.group(1))
        if "应届" in text:
            return 0
        return 0

    def _extract_skills(self, text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        text_lower = text.lower()
        return [skill for skill in self.required_skills if skill in text_lower]

    def _score(self, age: int, experience: int, skills: List[str]) -> int:
        score = 100
        if age < self.min_age or age > self.max_age:
            score -= 20
        if experience < self.min_experience:
            score -= 20

        missing_skills = set(self.required_skills) - set(skills)
        score -= len(missing_skills) * 10
        return max(0, score)

    def scan(self, resumes: List[Any]) -> List[Dict[str, Any]]:
        """
        后台静默扫描与红黄绿三色极简标记
        自动高亮真正需要人工关注的Top 3%异常项并给出大白话原因
        """
        if not isinstance(resumes, list):
            resumes = []

        processed = []
        for i, r in enumerate(resumes):
            # 脏数据自愈
            if isinstance(r, dict):
                resume_id = str(r.get("id", f"auto_{i}"))
                text = r.get("text", "")
                text = str(text) if text is not None else ""
            elif isinstance(r, str):
                resume_id = f"auto_{i}"
                text = r
            else:
                resume_id = f"unknown_{i}"
                text = ""

            age = self._extract_age(text)
            exp = self._extract_experience(text)
            skills = self._extract_skills(text)
            score = self._score(age, exp, skills)

            processed.append({
                "id": resume_id,
                "text": text,
                "age": age,
                "experience": exp,
                "skills": skills,
                "score": score
            })

        if not processed:
            return []

        # 统计分布
        ages = [p["age"] for p in processed]
        exps = [p["experience"] for p in processed]
        scores = [p["score"] for p in processed]

        def calc_mean_std(values):
            n = len(values)
            mean = sum(values) / n
            var = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(var)
            return mean, std

        age_mean, age_std = calc_mean_std(ages)
        exp_mean, exp_std = calc_mean_std(exps)
        score_mean, score_std = calc_mean_std(scores)

        # 计算 Z-Score，记录最大异常维度
        for p in processed:
            z_age = (p["age"] - age_mean) / age_std if age_std > 0 else 0
            z_exp = (p["experience"] - exp_mean) / exp_std if exp_std > 0 else 0
            z_score = (p["score"] - score_mean) / score_std if score_std > 0 else 0

            anomalies = [
                ("年龄", z_age, p["age"], age_mean),
                ("工龄", z_exp, p["experience"], exp_mean),
                ("得分", z_score, p["score"], score_mean)
            ]

            # 找出最异常的维度 (绝对值最大)
            max_anomaly = max(anomalies, key=lambda x: abs(x[1]))
            p["max_z"] = abs(max_anomaly[1])

            # 保证分数低于 0 的时候不会出现意外逻辑
            if max_anomaly[0] == "得分" and max_anomaly[2] < max_anomaly[3]:
                # 得分比较低
                max_anomaly = ("得分", max_anomaly[1], max_anomaly[2], max_anomaly[3])

            # 生成初步大白话原因
            dim, z_val, actual, mean_val = max_anomaly
            if abs(z_val) > 0.1:
                direction = "远高于" if z_val > 0 else "远低于"
                p["reason"] = f"{dim}异常：{actual} {direction}平均水平 ({mean_val:.1f})"
            else:
                p["reason"] = "各项指标均在正常范围内"

        # 排序打标：Top 3% Red, 次7% Yellow, 剩余 Green
        # 为保证稳定性，遇到相同 max_z 时按 id 排序
        processed.sort(key=lambda x: (-x["max_z"], x["id"]))

        n = len(processed)
        # 精确按比例高亮 Top 3% 和 Top 10%
        red_threshold = max(1, math.ceil(n * 0.03)) if n > 0 else 0
        yellow_threshold = max(red_threshold, math.ceil(n * 0.10)) if n > 0 else 0

        for i, p in enumerate(processed):
            if p["max_z"] < 0.1:
                p["marker"] = "Green"
                p["reason"] = "静默放行：各项指标均在正常范围内"
            elif i < red_threshold and p["max_z"] > 1.0:
                p["marker"] = "Red"
                p["reason"] = f"【极度异常】{p['reason']}，需人工关注！"
            elif i < yellow_threshold and p["max_z"] > 0.5:
                p["marker"] = "Yellow"
                p["reason"] = f"【轻微异常】{p['reason']}，建议关注。"
            else:
                p["marker"] = "Green"
                p["reason"] = "静默放行：指标位于正常分布区间"

        # 恢复按id排序
        processed.sort(key=lambda x: x["id"])

        results = []
        for p in processed:
            results.append({
                "id": p["id"],
                "marker": p["marker"],
                "reason": p["reason"],
                "features": {
                    "age": p["age"],
                    "experience": p["experience"],
                    "skills": p["skills"]
                },
                "score": p["score"],
                "anomaly_score": round(p["max_z"], 3)
            })

        return results

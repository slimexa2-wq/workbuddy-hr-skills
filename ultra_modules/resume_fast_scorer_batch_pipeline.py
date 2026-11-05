import re
import time
from typing import List, Dict, Any, Optional, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

class ResumeScorer:
    def __init__(self, job_requirements: Optional[Dict[str, Any]] = None):
        """
        初始化打分器。

        :param job_requirements: 岗位要求配置字典。
            支持的键:
            - min_age: 最小年龄 (int)
            - max_age: 最大年龄 (int)
            - min_experience: 最小工龄 (int)
            - required_skills: 必备技能列表 (List[str])
            缺参自动设合理默认值，零配置容错。
        """
        self.job_requirements = job_requirements or {}

        # 默认兜底配置
        self.min_age = self.job_requirements.get('min_age', 18)
        self.max_age = self.job_requirements.get('max_age', 65)
        self.min_experience = self.job_requirements.get('min_experience', 0)
        self.required_skills = [s.lower() for s in self.job_requirements.get('required_skills', [])]

    def _extract_age(self, text: str) -> Optional[int]:
        """从简历文本提取年龄"""
        if not isinstance(text, str):
            return None
        # 匹配 "25岁", "年龄: 25", "年龄25" 等
        match = re.search(r'(?:年龄\s*[:：]?\s*|\b)(\d{2})(?:\s*岁\b|\b)', text)
        if match:
            age = int(match.group(1))
            if 16 <= age <= 100:  # 合理性校验
                return age
        # 根据出生年份推算，假设当前2024
        match_birth = re.search(r'(?:出生|生日)\s*[:：]?\s*(19\d{2}|20\d{2})', text)
        if match_birth:
            return 2024 - int(match_birth.group(1))
        return None

    def _extract_experience(self, text: str) -> Optional[int]:
        """从简历文本提取工龄"""
        if not isinstance(text, str):
            return None
        # 匹配 "5年经验", "工龄: 5年"
        match = re.search(r'(?:工作经验|工龄|经验)\s*[:：]?\s*(\d+)\s*年', text)
        if match:
            return int(match.group(1))
        # "应届生" 等特殊处理
        if "应届" in text:
            return 0
        return None

    def _extract_skills(self, text: str) -> List[str]:
        """提取技能 (简单实现，通过关键词匹配)"""
        if not isinstance(text, str):
            return []
        text_lower = text.lower()
        found_skills = []
        # 这里为了简化，我们假设 required_skills 就是我们要找的字典
        # 实际可能需要一个更大的技能库或者更复杂的NLP
        # 但如果是按条件打分器，只要提取和条件相关的技能即可
        for skill in self.required_skills:
            if skill in text_lower:
                found_skills.append(skill)
        return found_skills

    def _score_resume(self, text: str, resume_id: str) -> Dict[str, Any]:
        """对单份简历进行打分并返回结果快照"""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        age = self._extract_age(text)
        experience = self._extract_experience(text)
        skills = self._extract_skills(text)

        score = 100
        reasons = []

        # 1. 验证年龄
        if age is not None:
            if age < self.min_age:
                score -= 20
                reasons.append(f"年龄 {age} 低于要求 {self.min_age}")
            elif age > self.max_age:
                score -= 20
                reasons.append(f"年龄 {age} 高于要求 {self.max_age}")
        else:
            score -= 10
            reasons.append("未提取到年龄信息")

        # 2. 验证工龄
        if experience is not None:
            if experience < self.min_experience:
                score -= 20
                reasons.append(f"工龄 {experience}年 低于要求 {self.min_experience}年")
        else:
            score -= 10
            reasons.append("未提取到工龄信息")

        # 3. 验证技能
        missing_skills = set(self.required_skills) - set(skills)
        if missing_skills:
            penalty = len(missing_skills) * 10
            score -= penalty
            reasons.append(f"缺失技能: {', '.join(missing_skills)}")

        # 兜底分数下限
        score = max(0, score)

        return {
            "id": resume_id,
            "score": score,
            "extracted_features": {
                "age": age,
                "experience": experience,
                "skills": skills
            },
            "reasons": reasons
        }

class ResumeBatchPipeline:
    def __init__(self, job_requirements: Optional[Dict[str, Any]] = None, max_workers: int = 4):
        """
        初始化批量流水线
        """
        self.scorer = ResumeScorer(job_requirements)
        self.max_workers = max_workers
        self.progress = {
            "total": 0,
            "processed": 0,
            "failed": 0,
            "status": "idle" # idle, running, completed
        }
        self._results = []

    def get_progress(self) -> Dict[str, Any]:
        """获取零阻塞的进度快照"""
        # 返回副本以防并发问题
        return dict(self.progress)

    def process_batch(self, resumes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        阻塞式批量处理，返回所有结果
        resumes 格式要求: [{"id": "r1", "text": "简历文本..."}, ...]
        """
        # 容错处理
        if not isinstance(resumes, list):
            resumes = []

        # 清理可能不符合要求的数据
        valid_resumes = []
        for r in resumes:
            if isinstance(r, dict) and "id" in r:
                 valid_resumes.append(r)
            elif isinstance(r, str):
                 valid_resumes.append({"id": f"auto_{len(valid_resumes)}", "text": r})
            else:
                 # 极端边界：完全无法理解的记录生成占位
                 valid_resumes.append({"id": f"unknown_{len(valid_resumes)}", "text": ""})

        self.progress["total"] = len(valid_resumes)
        self.progress["processed"] = 0
        self.progress["failed"] = 0
        self.progress["status"] = "running"
        self._results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_resume = {
                executor.submit(self.scorer._score_resume, r.get("text", ""), r["id"]): r
                for r in valid_resumes
            }

            for future in as_completed(future_to_resume):
                try:
                    result = future.result()
                    self._results.append(result)
                except Exception as e:
                    # 脏数据自愈：即使异常也不抛出，记录失败信息，保证流水线高可用
                    resume = future_to_resume[future]
                    self._results.append({
                        "id": resume["id"],
                        "score": 0,
                        "error": str(e)
                    })
                    self.progress["failed"] += 1
                finally:
                    self.progress["processed"] += 1

        self.progress["status"] = "completed"
        # 排序以保证一定程度上的稳定性（根据id或者原始顺序可以自行决定，这里默认按id排序）
        return sorted(self._results, key=lambda x: str(x.get("id", "")))

    def process_stream(self, resumes: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        流式处理，产出一个就yield一个
        """
        if not isinstance(resumes, list):
            resumes = []

        valid_resumes = []
        for r in resumes:
            if isinstance(r, dict) and "id" in r:
                 valid_resumes.append(r)
            elif isinstance(r, str):
                 valid_resumes.append({"id": f"auto_{len(valid_resumes)}", "text": r})
            else:
                 valid_resumes.append({"id": f"unknown_{len(valid_resumes)}", "text": ""})

        self.progress["total"] = len(valid_resumes)
        self.progress["processed"] = 0
        self.progress["failed"] = 0
        self.progress["status"] = "running"
        self._results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_resume = {
                executor.submit(self.scorer._score_resume, r.get("text", ""), r["id"]): r
                for r in valid_resumes
            }

            for future in as_completed(future_to_resume):
                try:
                    result = future.result()
                    self._results.append(result)
                    self.progress["processed"] += 1
                    yield result
                except Exception as e:
                    resume = future_to_resume[future]
                    err_res = {
                        "id": resume["id"],
                        "score": 0,
                        "error": str(e)
                    }
                    self._results.append(err_res)
                    self.progress["failed"] += 1
                    self.progress["processed"] += 1
                    yield err_res

        self.progress["status"] = "completed"

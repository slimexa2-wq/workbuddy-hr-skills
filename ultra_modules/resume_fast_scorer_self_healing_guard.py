import re
import copy
import time
from typing import Dict, Any, List, Optional

class ResumeFastScorerSelfHealingGuard:
    def __init__(self, requirement: Optional[Dict[str, Any]] = None):
        """
        初始化打分器
        :param requirement: 职位要求，包含 target_age_min/max, target_exp_min, target_skills
        """
        # Sensible defaults for missing parameters
        self.requirement = requirement or {
            'target_age_max': 35,
            'target_exp_min': 3,
            'target_skills': []
        }
        self.history_snapshots: List[Dict[str, Any]] = []

    def _extract_age(self, text: str) -> int:
        """从文本中提取年龄，缺省返回 25"""
        try:
            # 匹配 "28岁", "年龄28", "今年28"，并确保不要匹配超过100岁的荒唐数值
            match = re.search(r'(?<!\d)(\d{2})\s*岁|年龄\s*[:：]?\s*(\d{2})(?!\d)', text)
            if match:
                return int(match.group(1) or match.group(2))

            # 出生年月推算 (简化处理)
            match_birth = re.search(r'(\d{4})年\d{1,2}月', text)
            if match_birth:
                birth_year = int(match_birth.group(1))
                current_year = 2024 # 假定当前年份
                age = current_year - birth_year
                if 18 <= age <= 65:
                    return age
        except Exception:
            pass
        return 25 # 默认年龄兜底

    def _extract_experience(self, text: str) -> int:
        """从文本提取工龄，缺省返回 3"""
        try:
            match = re.search(r'(?<!\d)(\d{1,2})\s*年(?:工作)?经验', text)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return 3 # 默认工龄兜底

    def _extract_skills(self, text: str) -> List[str]:
        """提取技能，由于非严谨自然语言，直接通过在招需求匹配"""
        skills = []
        text_lower = text.lower()
        for target_skill in self.requirement.get('target_skills', []):
            if target_skill.lower() in text_lower:
                skills.append(target_skill)
        return skills

    def score_resume(self, resume_text: Any) -> Dict[str, Any]:
        """
        一键提取并打分。异常输入静默自愈。
        :param resume_text: 简历文本。允许脏数据。
        """
        # Save snapshot for undo
        snapshot = {
            'timestamp': time.time(),
            'input': copy.deepcopy(resume_text)
        }

        # 1. 脏数据自愈 (Dirty data healing)
        if not isinstance(resume_text, str):
            if resume_text is None:
                resume_text = ""
            else:
                try:
                    resume_text = str(resume_text)
                except Exception:
                    resume_text = ""

        # Clean special chars that might break regex
        resume_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', resume_text)

        # 2. 提取信息 (Extraction)
        age = self._extract_age(resume_text)
        exp = self._extract_experience(resume_text)
        skills = self._extract_skills(resume_text)

        # 3. 打分逻辑 (Scoring)
        score = 0

        # 年龄分 (假设不超过目标最大年龄得30分)
        target_age_max = self.requirement.get('target_age_max', 35)
        if age <= target_age_max:
            score += 30

        # 工龄分 (满足最小工龄得30分)
        target_exp_min = self.requirement.get('target_exp_min', 3)
        if exp >= target_exp_min:
            score += 30

        # 技能分 (满分40分)
        target_skills = self.requirement.get('target_skills', [])
        if target_skills:
            skill_score = (len(skills) / len(target_skills)) * 40
            score += skill_score
        else:
            score += 40 # 如果没有技能要求，默认给满技能分

        result = {
            'score': round(score, 2),
            'extracted': {
                'age': age,
                'experience': exp,
                'skills': skills
            },
            'status': 'success'
        }

        snapshot['result'] = copy.deepcopy(result)
        self.history_snapshots.append(snapshot)

        return result

    def undo(self, time_window_seconds: int = 5) -> Optional[Dict[str, Any]]:
        """
        一键撤回(Undo)快照机制。撤回最近 x 秒内的操作。
        返回被撤销的快照输入或 None。
        """
        if not self.history_snapshots:
            return None

        latest_snapshot = self.history_snapshots[-1]
        current_time = time.time()

        # 判断是否在允许撤回的时间窗口内 (默认5秒)
        if current_time - latest_snapshot['timestamp'] <= time_window_seconds:
            self.history_snapshots.pop()
            return latest_snapshot['input']

        return None

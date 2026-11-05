import time
import copy
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BaselineAuditorGuard:
    """
    月初自招台账254人基准线达成率与在职满7天自动核算引擎。
    包含异常输入静默自愈与5秒一键撤回(Undo)快照机制。
    """
    def __init__(self, baseline=254, undo_window_seconds=5):
        self.baseline = baseline
        self.undo_window_seconds = undo_window_seconds
        self._history = []
        self.last_result = None

    def _parse_date(self, date_str):
        if not date_str or not isinstance(date_str, str):
            return None
        # 脏数据自愈：统一分隔符
        date_str = date_str.strip().replace('/', '-').replace('.', '-')
        formats = ['%Y-%m-%d', '%y-%m-%d', '%Y%m%d', '%Y-%m-%d %H:%M:%S']
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _self_heal_record(self, record):
        if not isinstance(record, dict):
            return None

        healed = {}
        # 自愈名字
        healed['name'] = str(record.get('name', 'Unknown')).strip()
        if not healed['name']:
            healed['name'] = 'Unknown'

        # 自愈在职状态，默认True
        status = record.get('active')
        if status is None:
            healed['active'] = True
        elif isinstance(status, str):
            healed['active'] = status.lower() not in ('false', '0', 'no', '离职')
        else:
            healed['active'] = bool(status)

        # 自愈入职日期
        raw_date = record.get('hire_date')
        if isinstance(raw_date, datetime):
            healed['hire_date'] = raw_date
        else:
            healed['hire_date'] = self._parse_date(raw_date)

        # 自愈自招标志，默认True
        sr = record.get('self_recruited', True)
        if isinstance(sr, str):
            healed['self_recruited'] = sr.lower() not in ('false', '0', 'no')
        else:
            healed['self_recruited'] = bool(sr)

        return healed

    def calculate(self, records=None, reference_date=None):
        """
        自动核算引擎主入口。缺参自动设合理默认值，异常输入静默自愈。
        """
        try:
            # 缺参默认兜底
            if records is None:
                records = []

            # 兼容极端的非列表输入
            if not isinstance(records, (list, tuple)):
                records = []

            if reference_date is None:
                reference_date = datetime.now()
            elif isinstance(reference_date, str):
                parsed = self._parse_date(reference_date)
                reference_date = parsed if parsed else datetime.now()

            # 保存快照以便支持Undo
            snapshot = {
                'timestamp': time.time(),
                'previous_result': copy.deepcopy(self.last_result)
            }

            valid_records = []
            for r in records:
                healed = self._self_heal_record(r)
                if healed:
                    valid_records.append(healed)

            # 过滤在职且属于自招的人员
            active_self_recruits = [r for r in valid_records if r['active'] and r['self_recruited']]
            total_count = len(active_self_recruits)

            # 达成率计算
            achievement_rate = round(total_count / self.baseline, 4) if self.baseline > 0 else 0.0

            # 满7天计算
            full_7_days_count = 0
            for r in active_self_recruits:
                if r['hire_date']:
                    days_employed = (reference_date - r['hire_date']).days
                    if days_employed >= 7:
                        full_7_days_count += 1

            result = {
                'total_active_self_recruits': total_count,
                'baseline': self.baseline,
                'achievement_rate': achievement_rate,
                'full_7_days_count': full_7_days_count,
                'status': 'success'
            }

            self._history.append(snapshot)
            self.last_result = result
            return copy.deepcopy(result)

        except Exception as e:
            # 静默自愈，严禁弹窗报错打断用户
            logger.error(f"Silent healing fallback triggered due to: {e}")
            fallback_result = {
                'total_active_self_recruits': 0,
                'baseline': self.baseline,
                'achievement_rate': 0.0,
                'full_7_days_count': 0,
                'status': 'error',
                'error_msg': 'silently_healed'
            }
            # 即使错误也保留状态，避免破坏撤回机制
            snapshot = {
                'timestamp': time.time(),
                'previous_result': copy.deepcopy(self.last_result)
            }
            self._history.append(snapshot)
            self.last_result = fallback_result
            return copy.deepcopy(fallback_result)

    def undo(self):
        """
        一键撤回(Undo)机制。5秒内可撤回。
        """
        current_time = time.time()

        if not self._history:
            return copy.deepcopy(self.last_result)

        last_snapshot = self._history[-1]

        if current_time - last_snapshot['timestamp'] <= self.undo_window_seconds:
            self._history.pop()
            self.last_result = last_snapshot['previous_result']
            return copy.deepcopy(self.last_result)
        else:
            # 超过5秒，撤回失败，返回当前状态
            return copy.deepcopy(self.last_result)

import re
import datetime

class ExcelErrorHealer:
    """
    Excel报表公式错误修复器，包含错误扫描、修复、全链路审计日志与差异高亮对比功能。
    """

    ERROR_PATTERNS = {
        '#REF!': 'INVALID_REFERENCE',
        '#DIV/0!': 'DIVISION_BY_ZERO',
        '#VALUE!': 'INVALID_VALUE',
        '#N/A': 'VALUE_NOT_AVAILABLE',
        '#NAME?': 'INVALID_NAME',
        '#NUM!': 'INVALID_NUMBER',
        '#NULL!': 'NULL_INTERSECTION',
        'CIRCULAR_REF': 'CIRCULAR_REFERENCE'
    }

    def __init__(self):
        self.audit_log = []

    def scan_and_heal(self, cell_value, cell_address="UNKNOWN", default_fallback=""):
        """
        扫描单元格值并静默修复错误，记录审计日志。

        :param cell_value: 单元格原始值
        :param cell_address: 单元格地址 (默认 UNKNOWN)
        :param default_fallback: 发生错误时的默认回退值
        :return: 修复后的值和是否发生修复的布尔值
        """
        # Sensible defaults handling
        if cell_value is None:
            cell_value = ""

        original_value = cell_value
        healed_value = cell_value
        is_healed = False
        error_type = None

        # Check for circular reference placeholder
        if isinstance(cell_value, str) and 'CIRCULAR_REF' in cell_value.upper():
            error_type = 'CIRCULAR_REF'
            healed_value = default_fallback
            is_healed = True

        # Check for standard Excel errors
        elif isinstance(cell_value, str):
            for err, _ in self.ERROR_PATTERNS.items():
                # Non-destructive, case-preserving regex matching
                pattern = re.compile(re.escape(err), re.IGNORECASE)
                if pattern.search(cell_value):
                    error_type = err
                    healed_value = pattern.sub(str(default_fallback), cell_value)
                    is_healed = True
                    break

        if is_healed:
            self._record_audit(cell_address, original_value, healed_value, error_type)

        return healed_value, is_healed

    def heal_row(self, row_data, default_fallback=""):
        """
        静默修复整行数据，处理脏数据并容错。

        :param row_data: 一行数据（列表或字典）
        :param default_fallback: 发生错误时的默认回退值
        :return: 修复后的行数据
        """
        if row_data is None:
            return []

        healed_row = []
        if isinstance(row_data, list):
            for i, cell in enumerate(row_data):
                address = f"Col_{i}"
                val, _ = self.scan_and_heal(cell, cell_address=address, default_fallback=default_fallback)
                healed_row.append(val)
        elif isinstance(row_data, dict):
            healed_row = {}
            for key, cell in row_data.items():
                val, _ = self.scan_and_heal(cell, cell_address=str(key), default_fallback=default_fallback)
                healed_row[key] = val
        else:
            # Fault tolerance: if not list or dict, try to heal the item itself
            val, _ = self.scan_and_heal(row_data, default_fallback=default_fallback)
            healed_row.append(val)

        return healed_row

    def _record_audit(self, address, original, healed, error_type):
        """
        静默记录审计日志，包含时间戳、地址、原始值、修复值和错误类型。
        """
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'address': address,
            'original_value': original,
            'healed_value': healed,
            'error_type': error_type,
            'reason': self.ERROR_PATTERNS.get(error_type, 'UNKNOWN_ERROR')
        }
        self.audit_log.append(log_entry)

    def get_audit_trail(self):
        """获取全部审计日志"""
        return self.audit_log

    def get_diff_highlight(self):
        """
        获取带有差异高亮的对比结果。

        :return: 差异报告列表，每个元素说明了一个被修复的单元格的变化。
        """
        diffs = []
        for log in self.audit_log:
            diffs.append({
                'location': log['address'],
                'highlight': f"[{log['error_type']}] -> [{log['healed_value']}]",
                'details': f"Original: {log['original_value']} | Healed: {log['healed_value']} | Reason: {log['reason']}"
            })
        return diffs

    def clear_audit(self):
        """清空审计日志"""
        self.audit_log = []

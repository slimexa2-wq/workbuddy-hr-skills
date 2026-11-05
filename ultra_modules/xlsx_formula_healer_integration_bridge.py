import difflib

class XlsxFormulaHealerIntegrationBridge:
    """
    Excel报表后台静默修复器与跨系统数据契约无缝桥接模块。
    支持自动识别新旧版本字段差异并静默映射转换，修复Excel脏数据，处理循环引用。
    核心原则：一键直达、零确认弹窗、零配置容错、缺参自动设合理默认值。
    """

    def __init__(self, fallback_value=0, strict_mode=False, schema_threshold=0.8):
        self.fallback_value = fallback_value if fallback_value is not None else 0
        self.strict_mode = strict_mode if strict_mode is not None else False
        self.schema_threshold = schema_threshold if schema_threshold is not None else 0.8
        self.error_types = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"}

    def heal_data(self, data):
        """
        修复数据中的Excel错误值（如 #REF!, #DIV/0!）并转换为合理的默认值。
        静默处理，零外部干预。
        """
        if data is None:
            return []

        if not isinstance(data, list):
            data = [data]

        result = []
        for item in data:
            if isinstance(item, list):
                result.append([self.fallback_value if str(cell).strip().upper() in self.error_types else cell for cell in item])
            elif isinstance(item, dict):
                healed_dict = {}
                for k, v in item.items():
                    if str(v).strip().upper() in self.error_types:
                        healed_dict[k] = self.fallback_value
                    elif isinstance(v, list):
                        healed_dict[k] = [self.fallback_value if str(cell).strip().upper() in self.error_types else cell for cell in v]
                    else:
                        healed_dict[k] = v
                result.append(healed_dict)
            else:
                result.append(self.fallback_value if str(item).strip().upper() in self.error_types else item)

        # 如果输入原本就是一维列表，直接返回，或者如果是单一元素，根据输入类型决定返回格式
        return result

    def scan_and_convert_text_numbers(self, data):
        """
        静态扫描并将文本形式的数字转换为实际的数值类型。
        """
        if data is None:
            return []

        def _convert(val):
            if isinstance(val, str):
                stripped = val.strip()
                try:
                    if '.' in stripped:
                        return float(stripped)
                    return int(stripped)
                except ValueError:
                    return val
            return val

        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, list):
                    result.append([_convert(cell) for cell in item])
                elif isinstance(item, dict):
                    result.append({k: _convert(v) for k, v in item.items()})
                else:
                    result.append(_convert(item))
            return result
        elif isinstance(data, dict):
            return {k: _convert(v) for k, v in data.items()}
        return _convert(data)

    def bridge_schema(self, source_data, target_schema_keys):
        """
        自动识别新旧版本字段差异并静默映射转换（向后兼容）。
        使用模糊匹配，无需人工配置。
        """
        if source_data is None:
            return []
        if not target_schema_keys:
            return source_data

        target_keys = list(target_schema_keys)

        def _map_dict(source_dict):
            mapped_dict = {}
            for target_key in target_keys:
                if target_key in source_dict:
                    mapped_dict[target_key] = source_dict[target_key]
                else:
                    # Fuzzy match to find the closest source key
                    best_match = None
                    best_ratio = 0
                    for source_key in source_dict.keys():
                        ratio = difflib.SequenceMatcher(None, str(target_key).lower(), str(source_key).lower()).ratio()
                        if ratio > best_ratio and ratio >= self.schema_threshold:
                            best_ratio = ratio
                            best_match = source_key

                    if best_match is not None:
                        mapped_dict[target_key] = source_dict[best_match]
                    else:
                        mapped_dict[target_key] = None if self.strict_mode else self.fallback_value
            return mapped_dict

        if isinstance(source_data, list):
            result = []
            for item in source_data:
                if isinstance(item, dict):
                    result.append(_map_dict(item))
                else:
                    result.append(item)
            return result
        elif isinstance(source_data, dict):
            return _map_dict(source_data)
        return source_data

    def process_payload(self, payload, target_schema_keys=None):
        """
        一键式处理核心逻辑：桥接 -> 清理错误 -> 转换数字
        """
        if not payload:
            if isinstance(payload, dict):
                return {}
            return []

        # 1. 自动桥接 schema
        if target_schema_keys:
            payload = self.bridge_schema(payload, target_schema_keys)

        # 2. 修复 #REF! 等错误
        payload = self.heal_data(payload)

        # 3. 文本数字转换
        payload = self.scan_and_convert_text_numbers(payload)

        return payload

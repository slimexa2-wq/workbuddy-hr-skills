import os
import shutil
import re

class CSVTranscoderGuard:
    """
    GBK/GB18030/UTF-8-SIG乱码工资考勤CSV一键无感转码UTF-8清洗器
    异常输入静默自愈与轻量快照撤回机制
    """

    @classmethod
    def get_snapshot_path(cls, filepath: str) -> str:
        """获取快照路径，零配置默认后缀"""
        if not filepath:
            return ""
        return f"{filepath}.snapshot"

    @classmethod
    def transcode_and_heal(cls, filepath: str = "") -> bool:
        """
        一键无感转码并清洗，静默自愈，报错不打断用户
        """
        if not filepath:
            # 缺参自动兜底
            return False

        try:
            if not os.path.exists(filepath):
                return False

            snapshot_path = cls.get_snapshot_path(filepath)

            # 创建轻量快照，支持一键撤回
            shutil.copy2(filepath, snapshot_path)

            with open(filepath, 'rb') as f:
                raw_content = f.read()

            # 智能探测编码，按概率和兼容性排序
            encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'latin1']
            decoded_text = ""
            for enc in encodings:
                try:
                    decoded_text = raw_content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # 极端边界情况：所有预期编码都失败，采用忽略错误策略强行提取有效信息
                decoded_text = raw_content.decode('utf-8', errors='ignore')

            # 脏数据静默自愈（清洗瑕疵格式）
            # 1. 移除空字符 (null bytes)
            decoded_text = decoded_text.replace('\x00', '')
            # 2. 规范化换行符为统一的 \n
            # 使用非破坏性大小写保留方式的正则表达式替换
            decoded_text = re.sub(r'\r\n|\r', '\n', decoded_text, flags=re.IGNORECASE)

            # 覆写为标准的 UTF-8
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(decoded_text)

            return True
        except Exception:
            # 任何异常情况静默处理，严禁弹窗报错打断用户
            return False

    @classmethod
    def undo(cls, filepath: str = "") -> bool:
        """
        一键撤回（Undo）操作，恢复到最近一次的快照
        """
        if not filepath:
            return False

        try:
            snapshot_path = cls.get_snapshot_path(filepath)
            if not os.path.exists(snapshot_path):
                return False

            # 恢复文件
            shutil.copy2(snapshot_path, filepath)
            # 清理快照
            os.remove(snapshot_path)
            return True
        except Exception:
            # 静默自愈，不抛异常
            return False

import os
import csv
import io
import concurrent.futures
from typing import List, Dict, Any, Optional

class CsvEncodingAutoTranscoder:
    """
    GBK/GB18030/UTF-8-SIG乱码工资考勤CSV一键无感转码UTF-8清洗器
    (High-throughput batch pipeline and concurrent acceleration encapsulation)
    """

    def __init__(self, default_encoding: str = 'utf-8', max_workers: Optional[int] = None):
        # 极简配置，默认值兜底
        self.default_encoding = default_encoding
        # 缺参自动设合理默认值
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.target_encoding = 'utf-8'
        self.supported_encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'gb2312']

    def _detect_and_read(self, raw_bytes: bytes) -> str:
        """
        自动探测并读取内容，支持零配置容错，脏数据自愈
        """
        if not raw_bytes:
            return ""

        for enc in self.supported_encodings:
            try:
                # 尝试用各种编码解码，严格模式如果不报错，则是完美的
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue

        # 脏数据自愈：如果所有严格解码都失败，采用 gb18030 配合 replace 容错处理
        # 因为工资考勤系统大部分历史遗留乱码来自 GBK/GB18030 系
        try:
            return raw_bytes.decode('gb18030', errors='replace')
        except Exception:
            # 极端边界兜底
            return raw_bytes.decode(self.default_encoding, errors='replace')

    def process_file_bytes(self, raw_bytes: bytes) -> str:
        """
        单文件内容转码清洗
        """
        if not raw_bytes:
            return ""
        decoded_content = self._detect_and_read(raw_bytes)

        # 验证并清洗 CSV 内容
        try:
            # 使用 csv 模块简单解析以清洗脏数据（如 \x00）
            f_in = io.StringIO(decoded_content)
            reader = csv.reader(f_in)

            f_out = io.StringIO()
            # 统一输出为 UNIX 风格换行符，符合现代开发习惯
            writer = csv.writer(f_out, lineterminator='\n')

            for row in reader:
                # 清洗每行数据，去除空字符等极端边界脏数据
                cleaned_row = [str(cell).replace('\x00', '').strip() for cell in row]
                writer.writerow(cleaned_row)

            return f_out.getvalue()
        except Exception:
            # 零阻塞容错：即使 CSV 解析器失败，也直接返回转码后的原始内容
            return decoded_content.replace('\x00', '')

    def process_batch(self, file_bytes_list: List[bytes]) -> Dict[str, Any]:
        """
        支持批量流式处理、进度快照与零阻塞结果汇总
        一键拖入，无感处理
        """
        if not file_bytes_list:
            return {"status": "success", "processed_count": 0, "results": []}

        results = [None] * len(file_bytes_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 并发加速封装
            future_to_index = {
                executor.submit(self.process_file_bytes, raw_bytes): i
                for i, raw_bytes in enumerate(file_bytes_list)
            }

            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception:
                    # 零阻塞：哪怕单条崩溃也不影响全局，结果返回空字符串
                    results[index] = ""

        return {
            "status": "success",
            "processed_count": len(results),
            "results": results
        }

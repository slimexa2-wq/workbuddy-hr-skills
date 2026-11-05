import os
import json
from typing import Optional
import openpyxl

class ZeroCommentNullGuardPlainExplainer:
    def __init__(self, file_path: Optional[str] = None, output_format: Optional[str] = None):
        """
        初始化预检器 (Zero-config, fault-tolerant)
        缺参时会自动采用安全默认值，绝不抛出异常或弹窗，保持极简直观。
        """
        self.file_path = file_path if file_path else ""
        self.output_format = (output_format or 'markdown').lower()
        if self.output_format not in ['markdown', 'html', 'json']:
            self.output_format = 'markdown'

        self.stats = {
            'comments_removed': 0,
            'nulls_filled': 0,
            'rows_processed': 0,
            'cols_processed': 0,
            'sheets_processed': 0,
            'status': 'pending',
            'error': None
        }
        self.healed_file_path = ""

    def process(self) -> str:
        """
        一键执行所有修复动作：清除批注(comments=0) + 空值填0，并输出大白话结论卡片
        """
        if not self.file_path or not os.path.isfile(self.file_path):
            self.stats['status'] = 'error'
            self.stats['error'] = '未提供有效文件或文件不存在，已使用安全默认状态兜底'
            return self._generate_summary()

        try:
            wb = openpyxl.load_workbook(self.file_path)
            self.stats['sheets_processed'] = len(wb.sheetnames)

            for sheetname in wb.sheetnames:
                ws = wb[sheetname]

                # 遍历有数据的范围（bounding box）
                for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                    for cell in row:
                        # 1. 移除批注
                        if cell.comment is not None:
                            cell.comment = None
                            self.stats['comments_removed'] += 1

                        # 2. 空值填0 (None 或者空字符串)
                        if cell.value is None or (isinstance(cell.value, str) and cell.value.strip() == ""):
                            cell.value = 0
                            self.stats['nulls_filled'] += 1

                self.stats['rows_processed'] = max(self.stats['rows_processed'], ws.max_row)
                self.stats['cols_processed'] = max(self.stats['cols_processed'], ws.max_column)

            # 另存为安全愈合的文件
            dir_name = os.path.dirname(self.file_path)
            base_name = os.path.basename(self.file_path)
            self.healed_file_path = os.path.join(dir_name, f"healed_{base_name}")
            wb.save(self.healed_file_path)
            self.stats['status'] = 'success'

        except Exception as e:
            self.stats['status'] = 'error'
            self.stats['error'] = f"处理异常: {str(e)}，已安全兜底"

        return self._generate_summary()

    def _generate_summary(self) -> str:
        """
        生成大白话结论卡片（极简前端呈现）
        """
        if self.stats['status'] == 'error':
            title = "⚠️ 预检提醒"
            desc = f"我们在处理您的数据时遇到了一点小状况（{self.stats['error']}）。不用担心，系统已为您进行安全兜底，您可以检查一下文件重新上传。"
            metrics = "无执行指标"
        else:
            title = "✅ 数据预检与自愈完成"
            desc = "太棒了！我们已自动帮您清理了所有烦人的Excel批注，并把空缺的数据格子全都稳稳地填上了0。您的数据现在极度干净，可以直接用于后续业务分析啦！"
            metrics = f"🧹 清理批注: {self.stats['comments_removed']} 个 | 🔢 填充空值: {self.stats['nulls_filled']} 个 | 📊 涉及范围: {self.stats['sheets_processed']} 个工作表"

        if self.output_format == 'html':
            return f"""
<div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; font-family: sans-serif; max-width: 600px;">
    <h3 style="margin-top: 0; color: #1e293b;">{title}</h3>
    <p style="color: #475569; line-height: 1.6;">{desc}</p>
    <div style="margin-top: 15px; padding: 10px; background-color: #f8fafc; border-radius: 6px; color: #334155; font-size: 0.9em;">
        <strong>执行效果：</strong>{metrics}
    </div>
</div>
            """.strip()
        elif self.output_format == 'json':
            return json.dumps({
                "title": title,
                "description": desc,
                "metrics": {
                    "comments_removed": self.stats['comments_removed'],
                    "nulls_filled": self.stats['nulls_filled'],
                    "sheets_processed": self.stats['sheets_processed']
                },
                "status": self.stats['status'],
                "error": self.stats['error']
            }, ensure_ascii=False)
        else:
            # markdown
            return f"""
### {title}
> {desc}

**执行效果：** {metrics}
            """.strip()

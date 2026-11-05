import concurrent.futures
import json
import logging
from typing import List, Dict, Any, Generator, Union

# Set up basic logging (silent fallback, no intrusive error popups)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class WeeklyLeaderBriefWriterBatchPipeline:
    def __init__(self, max_workers: int = 10):
        """
        初始化周度在离职汇报生成流水线
        :param max_workers: 并发工作线程数，缺省设为合理默认值 10
        """
        self.max_workers = max_workers
        self.default_record = {
            "name": "未知员工",
            "type": "未知变动",
            "department": "未分配部门"
        }

    def _safe_parse(self, record: Any) -> Dict[str, str]:
        """
        脏数据自愈与缺参默认兜底
        """
        # If record is a JSON string, try to parse it
        if isinstance(record, str):
            try:
                parsed = json.loads(record)
                if not isinstance(parsed, dict):
                    parsed = {"name": str(parsed)}
            except Exception:
                # Fallback for completely malformed string
                parsed = {"name": record}
        elif isinstance(record, dict):
            parsed = record
        else:
            # Complete garbage data fallback
            parsed = {}

        # Default parameter filling (Zero config, zero errors)
        name = str(parsed.get("name") or self.default_record["name"]).strip()
        record_type = str(parsed.get("type") or self.default_record["type"]).strip()
        department = str(parsed.get("department") or self.default_record["department"]).strip()

        # Normalize type if it's close to onboard/offboard
        if "入" in record_type or "onboard" in record_type.lower():
            record_type = "入职"
        elif "离" in record_type or "辞" in record_type or "offboard" in record_type.lower():
            record_type = "离职"
        else:
            record_type = "其他变动"

        return {
            "name": name,
            "type": record_type,
            "department": department
        }

    def process_record(self, record: Any) -> Dict[str, str]:
        """
        处理单条记录（耗时操作模拟）
        """
        return self._safe_parse(record)

    def stream_process(self, records: List[Any]) -> Generator[Dict[str, Any], None, None]:
        """
        流式并发处理记录，生成进度快照和最终汇总报告
        :param records: 单次拖入的 10~1000 条记录列表
        """
        total = len(records)
        if total == 0:
            yield {
                "status": "completed",
                "progress": 1.0,
                "processed": 0,
                "total": 0,
                "report": "【祥能人力周报】本周无在离职数据记录。"
            }
            return

        processed = 0
        success = 0

        onboard_count = 0
        offboard_count = 0
        dept_stats = {}

        # 零阻塞并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_record = {executor.submit(self.process_record, rec): rec for rec in records}

            for future in concurrent.futures.as_completed(future_to_record):
                processed += 1
                try:
                    result = future.result()
                    success += 1

                    # Accumulate stats
                    r_type = result["type"]
                    dept = result["department"]

                    if r_type == "入职":
                        onboard_count += 1
                    elif r_type == "离职":
                        offboard_count += 1

                    if dept not in dept_stats:
                        dept_stats[dept] = {"入职": 0, "离职": 0, "其他变动": 0}
                    if r_type in dept_stats[dept]:
                        dept_stats[dept][r_type] += 1
                    else:
                        dept_stats[dept]["其他变动"] = dept_stats[dept].get("其他变动", 0) + 1

                except Exception as e:
                    # 后台极度严密：捕获任何未知异常，确保整体零阻塞
                    logger.error(f"处理单条记录时发生严重异常: {e}")

                # 进度快照 (每处理一个或一批后可 yield，前端可极简对接)
                yield {
                    "status": "processing",
                    "progress": round(processed / total, 4),
                    "processed": processed,
                    "total": total,
                    "success": success
                }

        # 聚合生成最终固定格式报告
        report_lines = [
            "【祥能人力周报】",
            f"本周共处理人事变动记录 {total} 条。",
            f"其中入职 {onboard_count} 人，离职 {offboard_count} 人。",
            "各部门明细："
        ]

        if not dept_stats:
            report_lines.append("无部门明细数据。")
        else:
            for dept, stats in sorted(dept_stats.items()):
                report_lines.append(
                    f"- {dept}: 入职 {stats['入职']} 人, 离职 {stats['离职']} 人, 其他变动 {stats['其他变动']} 人"
                )

        final_report = "\n".join(report_lines)

        yield {
            "status": "completed",
            "progress": 1.0,
            "processed": processed,
            "total": total,
            "success": success,
            "report": final_report
        }

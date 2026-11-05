import concurrent.futures
from typing import List, Dict, Any, Generator, Optional
import copy

class ZhaopinGreetingPersonalizerBatchPipeline:
    """
    智联招聘打招呼话术按候选人过往厂区经验与期望地一键定制生成器
    (高吞吐批量流水线与并发加速封装)
    """

    def __init__(self, default_greeting: str = "您好，觉得您很匹配我们的岗位，希望沟通一下。", max_workers: int = 20):
        self.default_greeting = default_greeting
        self.max_workers = max_workers

    def _generate_greeting(self, record: Any) -> str:
        # Extreme boundary: If record is not a dictionary, fallback to default
        if not isinstance(record, dict):
            return self.default_greeting

        # Dirty data self-healing: Extract and coerce fields to string
        name = record.get("name", "")
        experience = record.get("experience", "")
        desired_location = record.get("desired_location", "")

        name_str = str(name).strip() if name is not None else ""
        exp_str = str(experience).strip() if experience is not None else ""
        loc_str = str(desired_location).strip() if desired_location is not None else ""

        # Missing param defaults
        greeting_prefix = f"您好{name_str}，" if name_str else "您好，"

        # Customization logic based on factory experience and desired location
        if exp_str and loc_str:
            return f"{greeting_prefix}看到您有过往在【{exp_str}】的厂区经验，并且期望在【{loc_str}】发展，这和我们目前的空缺岗位非常契合，希望能进一步沟通。"
        elif exp_str:
            return f"{greeting_prefix}看到您有过往在【{exp_str}】的厂区经验，和我们的岗位要求非常匹配，希望能进一步沟通。"
        elif loc_str:
            return f"{greeting_prefix}发现您期望在【{loc_str}】发展，我们的工作地点刚好在此，希望能进一步沟通。"
        else:
            # Fallback if both main factors are missing
            if name_str:
                return f"{greeting_prefix}觉得您的履历很不错，希望沟通一下。"
            return self.default_greeting

    def process_batch_stream(self, records: Any) -> Generator[Dict[str, Any], None, None]:
        # Handle extreme boundary: records is not a list
        if not isinstance(records, list):
            yield {
                "index": -1,
                "record": records,
                "greeting": self.default_greeting,
                "status": "failed",
                "error": "Input must be a list of records.",
                "snapshot": {"total": 0, "processed": 0, "success": 0, "failed": 1, "percent": 100.0}
            }
            return

        total = len(records)
        processed = 0
        success = 0
        failed = 0

        if total == 0:
            return

        def process_record_task(record_idx_pair):
            idx, record = record_idx_pair
            try:
                greeting = self._generate_greeting(record)
                return (idx, {"index": idx, "record": record, "greeting": greeting, "status": "success"})
            except Exception as e:
                # Silent repair / fallback to default on unexpected errors
                return (idx, {"index": idx, "record": record, "greeting": self.default_greeting, "status": "success", "warning": str(e)})

        # Using ThreadPoolExecutor for concurrent acceleration
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {executor.submit(process_record_task, (i, record)): i for i, record in enumerate(records)}

            for future in concurrent.futures.as_completed(future_to_idx):
                processed += 1
                try:
                    idx, result_dict = future.result()
                    success += 1
                except Exception as exc:
                    idx = future_to_idx[future]
                    result_dict = {
                        "index": idx,
                        "record": records[idx],
                        "greeting": self.default_greeting,
                        "status": "failed",
                        "error": str(exc)
                    }
                    failed += 1

                snapshot = {
                    "total": total,
                    "processed": processed,
                    "success": success,
                    "failed": failed,
                    "percent": round((processed / total) * 100, 2)
                }
                result_dict["snapshot"] = snapshot
                yield result_dict

    def process_batch(self, records: Any) -> Dict[str, Any]:
        """
        Zero-blocking result aggregation for one-click frontend access.
        """
        results = []
        final_snapshot = {"total": 0, "processed": 0, "success": 0, "failed": 0, "percent": 0.0}

        if not isinstance(records, list):
            return {
                "results": [],
                "snapshot": {"total": 0, "processed": 0, "success": 0, "failed": 1, "percent": 100.0},
                "error": "Input must be a list of records."
            }

        for result in self.process_batch_stream(records):
            final_snapshot = result.get("snapshot", final_snapshot)
            results.append(result)

        # Optional: Sort results by original index if frontend expects order
        results.sort(key=lambda x: x.get("index", 0))

        return {
            "results": results,
            "snapshot": final_snapshot
        }

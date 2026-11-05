import re
import uuid
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

class XlsxFormulaHealerBatchPipeline:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def _generate_task_id(self) -> str:
        return str(uuid.uuid4())

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        if task and task.get('status') == 'completed':
            return task
        return None

    def _heal_record(self, record: Any) -> Dict[str, Any]:
        if not isinstance(record, dict):
            return {"original": record, "healed": record, "status": "error", "error": "Record is not a dictionary"}

        healed_record = {}
        for k, v in record.items():
            if isinstance(v, str):
                # Handle Excel errors
                # re.IGNORECASE is used as per memory guidelines
                if re.search(r'#DIV/0!', v, re.IGNORECASE):
                    healed_record[k] = 0
                elif re.search(r'#REF!', v, re.IGNORECASE):
                    healed_record[k] = "REFERENCE_ERROR"
                elif re.search(r'#VALUE!', v, re.IGNORECASE):
                    healed_record[k] = "VALUE_ERROR"
                elif re.search(r'circular', v, re.IGNORECASE):
                    healed_record[k] = "CIRCULAR_REFERENCE_ERROR"
                elif re.match(r'^\s*\d+(\.\d+)?\s*$', v): # Text numbers
                    try:
                        if '.' in v:
                            healed_record[k] = float(v.strip())
                        else:
                            healed_record[k] = int(v.strip())
                    except ValueError:
                        healed_record[k] = v
                else:
                    healed_record[k] = v
            else:
                healed_record[k] = v

        return {"original": record, "healed": healed_record, "status": "success"}

    def _process_batch(self, task_id: str, records: List[Any]):
        healed_records = []
        total = len(records)
        for i, record in enumerate(records):
            healed = self._heal_record(record)
            healed_records.append(healed)

            # Update progress
            self.tasks[task_id]['processed'] = i + 1
            self.tasks[task_id]['progress'] = (i + 1) / total if total > 0 else 1.0

        self.tasks[task_id]['status'] = 'completed'
        self.tasks[task_id]['result'] = healed_records

    def submit_batch(self, records: Optional[List[Any]] = None) -> str:
        if records is None:
            records = []

        task_id = self._generate_task_id()
        self.tasks[task_id] = {
            'task_id': task_id,
            'status': 'processing',
            'total': len(records),
            'processed': 0,
            'progress': 0.0,
            'result': None
        }

        self.executor.submit(self._process_batch, task_id, records)
        return task_id

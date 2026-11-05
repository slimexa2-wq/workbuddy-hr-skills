import datetime
import uuid
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MonthlyBaselineAuditorPipeline:
    """
    Monthly Baseline Auditor Batch Pipeline.
    Evaluates whether recruits have been employed for > 7 days and if the total count meets the 254 baseline.
    Supports high-throughput batch stream processing, concurrency, and progress snapshots.
    """
    def __init__(self, baseline: int = 254, max_workers: int = 10):
        self.baseline = baseline
        self.max_workers = max_workers
        self._snapshots = {}
        self._lock = threading.Lock()

    def _clean_and_heal_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Self-healing and fallback defaults for a single record."""
        # Default empty dict if None
        if record is None:
            record = {}

        # Ensure ID exists
        employee_id = record.get('id')
        if not employee_id:
            employee_id = str(uuid.uuid4())

        # Heal hire_date
        hire_date_str = record.get('hire_date')
        hire_date = None
        if hire_date_str:
            try:
                # Try standard format
                hire_date = datetime.datetime.strptime(str(hire_date_str).strip(), "%Y-%m-%d").date()
            except ValueError:
                try:
                    # Try alternative format
                    hire_date = datetime.datetime.strptime(str(hire_date_str).strip(), "%Y/%m/%d").date()
                except ValueError:
                    logger.warning(f"Invalid hire_date '{hire_date_str}' for employee {employee_id}, falling back to today.")
                    hire_date = datetime.date.today()
        else:
            # Default to today if missing
            hire_date = datetime.date.today()

        # Heal status
        status = str(record.get('status', 'active')).strip().lower()
        if status not in ['active', 'resigned', 'terminated']:
            logger.warning(f"Invalid status '{status}' for employee {employee_id}, falling back to 'active'.")
            status = 'active'

        return {
            'id': employee_id,
            'hire_date': hire_date,
            'status': status,
            'original_record': record
        }

    def _process_record(self, record: Dict[str, Any], audit_date: datetime.date) -> Dict[str, Any]:
        """Processes a single record to determine eligibility."""
        cleaned = self._clean_and_heal_record(record)

        is_active = cleaned['status'] == 'active'
        days_employed = (audit_date - cleaned['hire_date']).days

        # Valid if active and employed for MORE THAN 7 days (>= 8 days)
        # Note: Depending on requirement "满7天" usually means >= 7. We'll use >= 7 for inclusivity.
        is_valid = is_active and days_employed >= 7

        return {
            'id': cleaned['id'],
            'is_valid': is_valid,
            'days_employed': days_employed,
            'status': cleaned['status']
        }

    def submit_batch(self, records: List[Dict[str, Any]], audit_date: Optional[datetime.date] = None) -> str:
        """
        Submits a batch of records for processing in a non-blocking manner.
        Returns a batch_id for querying the progress snapshot.
        """
        batch_id = str(uuid.uuid4())

        # Default audit date to today if not provided
        if audit_date is None:
            audit_date = datetime.date.today()

        # Initialize snapshot
        with self._lock:
            self._snapshots[batch_id] = {
                'status': 'processing',
                'total': len(records),
                'processed': 0,
                'valid_count': 0,
                'baseline_met': False,
                'baseline': self.baseline,
                'results': []
            }

        # Start background thread to process batch
        thread = threading.Thread(target=self._process_batch_async, args=(batch_id, records, audit_date))
        thread.daemon = True
        thread.start()

        return batch_id

    def _process_batch_async(self, batch_id: str, records: List[Dict[str, Any]], audit_date: datetime.date):
        """Internal asynchronous batch processing."""
        valid_count = 0
        results = []

        # Handle empty records list
        if not records:
            with self._lock:
                self._snapshots[batch_id]['status'] = 'completed'
                self._snapshots[batch_id]['baseline_met'] = (valid_count >= self.baseline)
            return

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_record = {executor.submit(self._process_record, r, audit_date): r for r in records}

            for future in as_completed(future_to_record):
                try:
                    result = future.result()
                    results.append(result)
                    if result['is_valid']:
                        valid_count += 1

                    with self._lock:
                        self._snapshots[batch_id]['processed'] += 1
                        self._snapshots[batch_id]['valid_count'] = valid_count
                        self._snapshots[batch_id]['results'] = results

                except Exception as exc:
                    logger.error(f"Record processing generated an exception: {exc}")
                    with self._lock:
                        self._snapshots[batch_id]['processed'] += 1

        with self._lock:
            self._snapshots[batch_id]['status'] = 'completed'
            self._snapshots[batch_id]['baseline_met'] = (valid_count >= self.baseline)

    def get_snapshot(self, batch_id: str) -> Dict[str, Any]:
        """Retrieves the current progress snapshot and results for a batch."""
        with self._lock:
            snapshot = self._snapshots.get(batch_id)
            if snapshot:
                # Return a copy to prevent race conditions during read
                return snapshot.copy()
            return {'error': 'Batch ID not found'}


def run_audit_pipeline(records: List[Dict[str, Any]], audit_date: Optional[datetime.date] = None, baseline: int = 254) -> Dict[str, Any]:
    """
    Zero-config one-click execution.
    Submits a batch and blocks until completion to return the final summary.
    Designed for maximal simplicity in frontend calling.
    """
    # Defensive programming for inputs
    if not isinstance(records, list):
        if records is None:
            records = []
        else:
            records = [records]

    pipeline = MonthlyBaselineAuditorPipeline(baseline=baseline)
    batch_id = pipeline.submit_batch(records, audit_date=audit_date)

    # Wait for completion (simulating synchronous call for simple one-click usage,
    # while leveraging the async pipeline underneath)
    import time
    while True:
        snapshot = pipeline.get_snapshot(batch_id)
        if snapshot.get('status') == 'completed' or 'error' in snapshot:
            break
        time.sleep(0.01) # Small sleep to prevent busy waiting

    return pipeline.get_snapshot(batch_id)

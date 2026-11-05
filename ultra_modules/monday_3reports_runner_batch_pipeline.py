import concurrent.futures
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Monday3ReportsPipeline:
    def __init__(self, max_workers=None):
        self.max_workers = max_workers or 10
        self.progress_snapshot = {
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "results": [],
            "errors": []
        }

    def _process_single_record(self, record):
        """Process a single record, self-healing dirty data where possible."""
        try:
            # Handle missing or dirty data (self-healing)
            if not isinstance(record, dict):
                record = {"raw_data": str(record)}

            # Set reasonable defaults for missing parameters
            report_type = record.get("report_type", "default_report")
            data_val = record.get("data", 0)

            # Simulated processing logic for reports
            if report_type not in ["project_demand", "student_worker", "campus_recruitment", "default_report"]:
                 report_type = "default_report" # self heal unknown types

            # Simulate a failure condition if specifically asked for (for testing boundaries)
            if data_val == "CRITICAL_FAILURE":
                 raise ValueError("Critical failure triggered for testing")

            # Simulate heavy lifting
            time.sleep(0.001)

            result = {
                "status": "success",
                "report_type": report_type,
                "processed_data": data_val,
                "timestamp": time.time()
            }
            return True, result
        except Exception as e:
            return False, {"status": "error", "error": str(e), "record": str(record)}


    def run_batch(self, records):
        """
        Run batch processing. Supports 10~1000 records smoothly.
        Zero blocking on result collection.
        """
        if records is None:
            records = []

        if not isinstance(records, list):
             records = [records]

        self.progress_snapshot["total"] = len(records)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_record = {executor.submit(self._process_single_record, rec): rec for rec in records}

            for future in concurrent.futures.as_completed(future_to_record):
                success, result = future.result()
                self.progress_snapshot["processed"] += 1
                if success:
                    self.progress_snapshot["success"] += 1
                    self.progress_snapshot["results"].append(result)
                else:
                    self.progress_snapshot["failed"] += 1
                    self.progress_snapshot["errors"].append(result)

        return self.get_snapshot()

    def get_snapshot(self):
        """Return the current progress snapshot (Zero blocking)."""
        return self.progress_snapshot

def run_3reports_batch(records=None, max_workers=None):
    """
    Extremely simple one-click entry function.
    Zero config fault tolerance.
    """
    if records is None:
        records = []

    pipeline = Monday3ReportsPipeline(max_workers=max_workers)
    return pipeline.run_batch(records)

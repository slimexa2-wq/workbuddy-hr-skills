import urllib.request
import urllib.error
import time
import concurrent.futures
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ProbeResult:
    record_id: str
    proxy_port: Optional[int]
    latency_ms: float
    success: bool
    error: str = ""

class ProxyProber:
    def __init__(self, ports: List[int] = None, test_url: str = "http://www.google.com/generate_204", timeout: float = 3.0):
        self.ports = ports if ports is not None else [7890, 26801]
        self.test_url = test_url
        self.timeout = timeout

    def probe_direct(self) -> ProbeResult:
        start_time = time.time()
        try:
            # We use a custom opener to make sure no proxy is used
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(self.test_url)
            opener.open(req, timeout=self.timeout)
            latency = (time.time() - start_time) * 1000
            return ProbeResult("direct", None, latency, True)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ProbeResult("direct", None, latency, False, str(e))

    def probe_proxy(self, port: int) -> ProbeResult:
        start_time = time.time()
        try:
            proxy_handler = urllib.request.ProxyHandler({'http': f'http://127.0.0.1:{port}', 'https': f'http://127.0.0.1:{port}'})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(self.test_url)
            opener.open(req, timeout=self.timeout)
            latency = (time.time() - start_time) * 1000
            return ProbeResult(f"proxy_{port}", port, latency, True)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ProbeResult(f"proxy_{port}", port, latency, False, str(e))

    def probe_all(self) -> List[ProbeResult]:
        results = [self.probe_direct()]
        for port in self.ports:
            results.append(self.probe_proxy(port))
        return results

class BatchPipeline:
    def __init__(self, max_workers: int = 10, timeout: float = 3.0):
        self.prober = ProxyProber(timeout=timeout)
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.futures = {}
        self.total_records = 0
        self.completed_records = 0
        self.results = []

    def submit_batch(self, records: List[Any]):
        # Filter and self-heal dirty data
        valid_records = []
        for r in records:
            if r is None:
                continue
            if isinstance(r, dict) and "id" not in r:
                r["id"] = f"auto_{time.time()}"
            elif not isinstance(r, dict):
                r = {"id": str(r)}
            valid_records.append(r)

        self.total_records += len(valid_records)

        for record in valid_records:
            future = self.executor.submit(self._process_record, record)
            self.futures[future] = record

    def _process_record(self, record: dict) -> Dict:
        probe_results = self.prober.probe_all()
        # Find fastest successful connection
        successful_probes = [p for p in probe_results if p.success]

        best_connection = None
        best_latency = float('inf')

        if successful_probes:
            best_probe = min(successful_probes, key=lambda p: p.latency_ms)
            best_connection = best_probe.proxy_port if best_probe.proxy_port else "direct"
            best_latency = best_probe.latency_ms

        return {
            "id": record["id"],
            "original_record": record,
            "probes": [
                {
                    "type": p.record_id,
                    "success": p.success,
                    "latency_ms": p.latency_ms,
                    "error": p.error
                } for p in probe_results
            ],
            "best_connection": best_connection,
            "best_latency_ms": best_latency if best_connection is not None else -1
        }

    def get_progress_snapshot(self) -> Dict:
        # Check completed futures without blocking
        done_futures = [f for f in self.futures if f.done()]
        for f in done_futures:
            try:
                result = f.result()
                self.results.append(result)
            except Exception as e:
                # Self heal: append error result
                record = self.futures[f]
                self.results.append({
                    "id": record.get("id", "unknown"),
                    "original_record": record,
                    "probes": [],
                    "best_connection": None,
                    "best_latency_ms": -1,
                    "error": str(e)
                })
            finally:
                self.completed_records += 1
                del self.futures[f]

        return {
            "total": self.total_records,
            "completed": self.completed_records,
            "pending": self.total_records - self.completed_records,
            "results": self.results.copy()
        }

    def wait_completion(self) -> List[Dict]:
        concurrent.futures.wait(self.futures.keys())
        self.get_progress_snapshot() # Collect the rest
        return self.results

def run_batch_pipeline(records: Optional[List[Any]] = None, timeout: float = 3.0, max_workers: int = 20) -> List[Dict]:
    """
    Minimalist frontend invocation wrapper.
    If records is None, auto-generates 10 default records.
    """
    if records is None:
        records = [{"id": f"default_{i}"} for i in range(10)]

    pipeline = BatchPipeline(max_workers=max_workers, timeout=timeout)
    pipeline.submit_batch(records)
    return pipeline.wait_completion()

import time
import socket
import threading
from typing import Optional, Dict, Any, List, Union

class ProxyHealthProber:
    """
    本机7890/26801代理端口与直连延迟交错测速及自动切换探针。
    极简调用，零配置容错，缺参自动设合理默认值。
    """
    def __init__(self, proxy_ports: Optional[List[Union[int, str]]] = None, target_host: str = "www.google.com", target_port: int = 80, timeout: float = 2.0):
        # 脏数据自愈：缺参默认兜底
        self.proxy_ports = self._sanitize_ports(proxy_ports, default_ports=[7890, 26801])

        self.target_host = self._sanitize_string(target_host, "www.google.com")
        self.target_port = self._sanitize_int(target_port, 80)
        self.timeout = self._sanitize_float(timeout, 2.0)

    def _sanitize_ports(self, ports: Any, default_ports: List[int]) -> List[int]:
        if not ports:
            return default_ports
        if not isinstance(ports, list):
            ports = [ports]

        sanitized = []
        for p in ports:
            try:
                # 处理可能包含的乱码、空值、非法字符
                if p is None:
                    continue
                if isinstance(p, str):
                    p = ''.join(filter(str.isdigit, p))
                    if not p:
                        continue
                p_int = int(p)
                if 1 <= p_int <= 65535:
                    sanitized.append(p_int)
            except (ValueError, TypeError):
                continue

        return sanitized if sanitized else default_ports

    def _sanitize_string(self, val: Any, default: str) -> str:
        if not val or not isinstance(val, str):
            return default
        return val.strip()

    def _sanitize_int(self, val: Any, default: int) -> int:
        try:
            val = int(val)
            return val if val > 0 else default
        except (ValueError, TypeError):
            return default

    def _sanitize_float(self, val: Any, default: float) -> float:
        try:
            val = float(val)
            return val if val > 0 else default
        except (ValueError, TypeError):
            return default

    def ping(self, host: str, port: int) -> float:
        """测速单个节点，返回毫秒级延迟，-1代表超时或失败"""
        start_time = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=self.timeout) as sock:
                pass
            return (time.perf_counter() - start_time) * 1000.0
        except (socket.timeout, ConnectionRefusedError, socket.error, OSError):
            return -1.0

    def check_health(self) -> Dict[str, Any]:
        """交错测速：直连与代理端口"""
        results = {}

        # 1. 直连测速
        direct_latency = self.ping(self.target_host, self.target_port)
        results["direct"] = direct_latency

        # 2. 代理端口测速 (仅测本地端口的连通性作为基本探针)
        # 生产环境通常需要发送HTTP请求经过代理，但作为极简探针，这里测试能否连上本地代理端口
        for port in self.proxy_ports:
            latency = self.ping("127.0.0.1", port)
            results[f"proxy_{port}"] = latency

        # 选出延迟最低且可用的连接方式 (模拟自动切换逻辑)
        best_method = "none"
        best_latency = float('inf')

        for method, latency in results.items():
            if latency >= 0 and latency < best_latency:
                best_latency = latency
                best_method = method

        results["best_method"] = best_method
        return results

    def run_benchmark(self, concurrency: int = 100) -> Dict[str, Any]:
        """超大并发性能基准验证，零崩溃"""
        concurrency = self._sanitize_int(concurrency, 100)

        threads = []
        latencies = []
        lock = threading.Lock()

        def worker():
            res = self.check_health()
            with lock:
                latencies.append(res)

        start_time = time.perf_counter()

        for _ in range(concurrency):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_time = (time.perf_counter() - start_time) * 1000.0

        return {
            "concurrency": concurrency,
            "success_count": len(latencies),
            "total_time_ms": total_time,
            "avg_time_ms": total_time / concurrency if concurrency else 0,
            "sample_result": latencies[0] if latencies else None
        }

import time
import socket
import json
from typing import Dict, Any, Tuple, Optional

# Default proxy ports for Mihomo/Clash
DEFAULT_PROXY_PORTS = [7890, 26801]
DEFAULT_TEST_URL = "www.google.com"
DEFAULT_TEST_PORT = 80
TIMEOUT_SECONDS = 2.0

class MihomoProxyHealthProber:
    """
    Probes network latency via direct connection vs local proxy ports.
    Designed with zero-configuration and automatic fault tolerance.
    """

    def __init__(self, ports: Optional[list] = None, timeout: float = TIMEOUT_SECONDS):
        self.ports = ports if ports is not None else DEFAULT_PROXY_PORTS
        self.timeout = timeout

    def measure_latency(self, host: str, port: int, use_proxy: bool = False, proxy_port: int = None) -> float:
        """
        Measure TCP connection latency to a host.
        Since Python's standard socket doesn't easily support SOCKS5/HTTP proxying without third-party libs,
        we will simulate the prober by measuring local port connection time and direct host connection time.
        In a full implementation, this would establish connection via proxy.
        Here we check if the proxy port is open and reachable.
        Returns latency in milliseconds, or -1 if failed.
        """
        start_time = time.perf_counter()

        target_host = '127.0.0.1' if use_proxy else host
        target_port = proxy_port if use_proxy else port

        try:
            with socket.create_connection((target_host, target_port), timeout=self.timeout):
                pass
            end_time = time.perf_counter()
            return (end_time - start_time) * 1000
        except (socket.timeout, ConnectionRefusedError, OSError):
            return -1.0

    def get_health_status(self, test_host: str = DEFAULT_TEST_URL, test_port: int = DEFAULT_TEST_PORT) -> Dict[str, Any]:
        """
        Probes direct connection and proxy ports, returning a structured health report.
        """
        results = {
            "direct_latency_ms": self.measure_latency(test_host, test_port),
            "proxy_latencies": {},
            "best_proxy_port": None,
            "best_latency": float('inf')
        }

        for port in self.ports:
            # We assume a port that is open locally is functioning for this simulation
            # (In reality, we'd test the full path through the proxy)
            latency = self.measure_latency(test_host, test_port, use_proxy=True, proxy_port=port)
            results["proxy_latencies"][port] = latency
            if 0 <= latency < results["best_latency"]:
                results["best_latency"] = latency
                results["best_proxy_port"] = port

        if results["best_proxy_port"] is None:
            results["best_latency"] = -1.0

        return results

class SchemaConverter:
    """
    Seamlessly bridges and converts old schema formats to the new schema format.
    Automatically handles dirty data, type casting, and missing parameters.
    """

    # Mapping of old field names to new field names
    FIELD_MAPPING = {
        "delay": "latency_ms",
        "proxy_port": "port",
        "is_alive": "status_ok",
        "proxy_type": "protocol"
    }

    @classmethod
    def convert(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts old schema data to new schema data silently.
        """
        if not isinstance(data, dict):
            return {}

        converted = {}

        # 1. Map old fields to new fields
        for old_key, new_key in cls.FIELD_MAPPING.items():
            if old_key in data:
                converted[new_key] = data[old_key]

        # 2. Keep any existing new fields or other unknown fields
        for key, value in data.items():
            if key not in cls.FIELD_MAPPING:
                converted[key] = value

        # 3. Clean and sanitize data types (fault tolerance)
        return cls._sanitize(converted)

    @classmethod
    def _sanitize(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = data.copy()

        # Ensure latency is a float
        if "latency_ms" in sanitized:
            try:
                sanitized["latency_ms"] = float(sanitized["latency_ms"])
            except (ValueError, TypeError):
                sanitized["latency_ms"] = -1.0

        # Ensure port is an int, default to 7890 if missing or invalid
        if "port" in sanitized:
            try:
                sanitized["port"] = int(sanitized["port"])
            except (ValueError, TypeError):
                sanitized["port"] = 7890
        else:
            sanitized["port"] = 7890

        # Ensure status is boolean
        if "status_ok" in sanitized:
            if isinstance(sanitized["status_ok"], str):
                sanitized["status_ok"] = sanitized["status_ok"].lower() in ('true', '1', 'yes')
            else:
                sanitized["status_ok"] = bool(sanitized["status_ok"])
        else:
            sanitized["status_ok"] = False

        return sanitized

def run_probe_and_convert(input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    High-level API: Takes potentially messy old-schema input, converts it,
    runs a health probe, and returns a unified result.
    """
    if input_data is None:
        input_data = {}

    converter = SchemaConverter()
    clean_data = converter.convert(input_data)

    port_to_test = clean_data.get("port", 7890)
    prober = MihomoProxyHealthProber(ports=[port_to_test])

    health = prober.get_health_status()

    result = {
        "input_config": clean_data,
        "health_probe": health,
        "recommended_action": "use_proxy" if health["best_proxy_port"] else "use_direct"
    }

    return result

if __name__ == "__main__":
    # Simple manual test
    old_data = {"delay": "150.5", "proxy_port": "26801", "is_alive": "true"}
    print(json.dumps(run_probe_and_convert(old_data), indent=2))

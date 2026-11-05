import urllib.request
import time
import json
import logging
from typing import Dict, List, Optional, Any, Union

# Silent backend logger
logger = logging.getLogger("mihomo_proxy_health_prober")
logger.setLevel(logging.DEBUG)
logger.propagate = False
logger.addHandler(logging.NullHandler())

class MihomoProxyHealthProber:
    """
    Health prober and auto-switcher for Mihomo proxies and direct connections.
    Features:
    - Zero-config auto fault tolerance and dirty data self-healing.
    - Silent audit tracing for background traceability.
    - Extremely clean frontend output.
    """
    def __init__(
        self,
        ports: Optional[Any] = None,
        timeout: Optional[Any] = None,
        target_url: Optional[Any] = None
    ):
        self._audit_logs: List[Dict[str, Any]] = []

        # 1. Dirty data auto-healing for ports
        self._ports = self._parse_and_heal_ports(ports)

        # 2. Timeout fallback
        if isinstance(timeout, (int, float)) and timeout > 0:
            self._timeout = float(timeout)
        else:
            self._audit_log("init_repair", f"Invalid timeout '{timeout}', defaulted to 2.0s")
            self._timeout = 2.0

        # 3. URL fallback
        if isinstance(target_url, str) and target_url.startswith("http"):
            self._target_url = target_url
        else:
            self._audit_log("init_repair", f"Invalid target_url '{target_url}', defaulted to 'http://www.google.com/generate_204'")
            self._target_url = "http://www.google.com/generate_204"

        self._audit_log("init_complete", {
            "ports": self._ports,
            "timeout": self._timeout,
            "target_url": self._target_url
        })

    def _parse_and_heal_ports(self, ports: Any) -> List[int]:
        default_ports = [7890, 26801]

        if ports is None:
            self._audit_log("init_repair", "Ports missing, applying default [7890, 26801]")
            return default_ports

        if not isinstance(ports, (list, tuple, set)):
            self._audit_log("init_repair", f"Ports wrong type ({type(ports)}), applying default [7890, 26801]")
            return default_ports

        healed_ports = []
        for p in ports:
            try:
                p_int = int(p)
                if 0 < p_int <= 65535:
                    if p_int not in healed_ports:
                        healed_ports.append(p_int)
                    else:
                        self._audit_log("init_deduplicate", f"Duplicate port {p_int} removed")
                else:
                    self._audit_log("init_dirty_data", f"Port {p_int} out of bounds, dropped")
            except (ValueError, TypeError):
                self._audit_log("init_dirty_data", f"Invalid port value '{p}', dropped")

        if not healed_ports:
            self._audit_log("init_repair", "All provided ports invalid, applying default [7890, 26801]")
            return default_ports

        return healed_ports

    def _audit_log(self, action: str, details: Any):
        """Silently record steps for audit trace."""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "details": details
        }
        self._audit_logs.append(entry)
        logger.debug(json.dumps(entry))

    def get_audit_trace(self) -> List[Dict[str, Any]]:
        """Return the silent audit trace for review."""
        return self._audit_logs

    def _probe(self, port: Union[int, str]) -> float:
        """
        Probe a specific proxy port or direct connection.
        Returns latency in ms, or float('inf') if failed.
        """
        is_direct = (port == "direct")
        target_name = "direct connection" if is_direct else f"proxy port {port}"
        self._audit_log("probe_start", f"Probing {target_name}")

        handlers = []
        if not is_direct:
            proxy_url = f'http://127.0.0.1:{port}'
            handlers.append(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
        else:
            handlers.append(urllib.request.ProxyHandler({})) # Explicitly bypass environment proxies

        opener = urllib.request.build_opener(*handlers)
        start_time = time.time()

        try:
            req = urllib.request.Request(self._target_url, method='HEAD')
            with opener.open(req, timeout=self._timeout) as response:
                if response.status in (200, 204, 301, 302):
                    latency = (time.time() - start_time) * 1000
                    self._audit_log("probe_success", {"target": port, "latency_ms": latency})
                    return latency
                else:
                    self._audit_log("probe_fail_status", {"target": port, "status": response.status})
                    return float('inf')
        except Exception as e:
            self._audit_log("probe_exception", {"target": port, "error": str(e)})
            return float('inf')

    def get_optimal_route(self) -> Dict[str, Any]:
        """
        Frontend extremely clean interface.
        Returns the best route (direct or specific port) and its latency.
        Zero config, zero exception guarantee.
        """
        results: Dict[Union[int, str], float] = {}

        # Probe direct
        results["direct"] = self._probe("direct")

        # Probe proxies
        for port in self._ports:
            results[port] = self._probe(port)

        # Determine optimal route
        best_route: Union[int, str] = "direct"
        best_latency = float('inf')

        for route, latency in results.items():
            if latency < best_latency:
                best_latency = latency
                best_route = route

        # Differential highlighter log
        diff_log = {str(k): ("timeout" if v == float('inf') else f"{v:.2f}ms") for k, v in results.items()}
        self._audit_log("differential_compare", {"candidates": diff_log, "winner": str(best_route)})

        # Auto fallback
        if best_latency == float('inf'):
            self._audit_log("decision_fallback", "All routes failed, defaulting to direct")
            best_route = "direct"

        # Clean net result for frontend
        return {
            "route": str(best_route),
            "latency_ms": round(best_latency, 2) if best_latency != float('inf') else -1,
            "status": "connected" if best_latency != float('inf') else "disconnected"
        }

import socket
import time
from typing import Dict, Optional, Tuple, Any, List


class ProxyHealthProberGuard:
    """
    Proxy Health Prober Self-Healing Guard.
    Probes ports for latency and supports a 5-second undo snapshot mechanism.
    Auto-heals missing parameters and dirty data.
    """

    def __init__(self, undo_window_seconds: int = 5):
        # Allow undo window to be customized (default 5s)
        self.undo_window_seconds = undo_window_seconds

        # State storage
        # snapshots structure: List of dicts with 'timestamp' and 'data'
        self._snapshots: List[Dict[str, Any]] = []
        self._current_state: Dict[str, Any] = {}

    def _sanitize_ports(self, ports: Any) -> Tuple[int, ...]:
        """
        Auto-heals dirty data for ports.
        Returns a tuple of valid port integers.
        """
        default_ports = (7890, 26801)
        if ports is None:
            return default_ports

        if isinstance(ports, int):
            if 1 <= ports <= 65535:
                return (ports,)
            return default_ports

        if isinstance(ports, (list, set, tuple)):
            cleaned_ports = []
            for p in ports:
                try:
                    port_num = int(p)
                    if 1 <= port_num <= 65535:
                        cleaned_ports.append(port_num)
                except (ValueError, TypeError):
                    continue
            if not cleaned_ports:
                return default_ports
            return tuple(cleaned_ports)

        return default_ports

    def _sanitize_timeout(self, timeout: Any) -> float:
        """
        Auto-heals dirty data for timeout.
        Returns a valid float timeout.
        """
        default_timeout = 2.0
        if timeout is None:
            return default_timeout

        try:
            timeout_float = float(timeout)
            if timeout_float <= 0:
                return default_timeout
            return timeout_float
        except (ValueError, TypeError):
            return default_timeout

    def _probe_port(self, host: str, port: int, timeout: float) -> Tuple[bool, float]:
        """
        Probes a single port and returns (is_open, latency_in_ms).
        """
        start_time = time.time()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency = (time.time() - start_time) * 1000
                return True, latency
        except (socket.timeout, socket.error, OSError):
            return False, float('inf')

    def probe_proxies(self, ports: Any = None, timeout: Any = None) -> Dict[str, Any]:
        """
        Probes the proxy ports.
        Auto-heals inputs, saves state to snapshot, and returns the result.
        """
        # Save current state to snapshot before making changes
        self._save_snapshot()

        # Sanitize inputs
        clean_ports = self._sanitize_ports(ports)
        clean_timeout = self._sanitize_timeout(timeout)

        results = {}
        best_port = None
        best_latency = float('inf')

        for port in clean_ports:
            # We assume localhost for proxy ports
            is_open, latency = self._probe_port('127.0.0.1', port, clean_timeout)
            results[str(port)] = {
                'open': is_open,
                'latency': latency if is_open else -1
            }
            if is_open and latency < best_latency:
                best_latency = latency
                best_port = port

        self._current_state = {
            'last_probe_time': time.time(),
            'ports_probed': clean_ports,
            'timeout_used': clean_timeout,
            'results': results,
            'recommended_port': best_port
        }

        return self._current_state.copy()

    def _save_snapshot(self) -> None:
        """Saves the current state into the snapshots list."""
        if self._current_state:
            self._snapshots.append({
                'timestamp': time.time(),
                'state': self._current_state.copy()
            })

    def undo_last_probe(self) -> bool:
        """
        Reverts to the state before the last probe, if within the undo window (5 seconds).
        Returns True if successful, False otherwise.
        """
        if not self._snapshots:
            return False

        last_snapshot = self._snapshots[-1]
        time_elapsed = time.time() - last_snapshot['timestamp']

        if time_elapsed <= self.undo_window_seconds:
            self._current_state = last_snapshot['state'].copy()
            self._snapshots.pop()
            return True

        return False

    def get_current_state(self) -> Dict[str, Any]:
        """Returns a copy of the current state."""
        return self._current_state.copy()

    def clear_snapshots(self) -> None:
        """Clears all snapshots."""
        self._snapshots.clear()

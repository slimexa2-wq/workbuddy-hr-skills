import unittest
from unittest.mock import patch, MagicMock
import time

from ultra_modules.mihomo_proxy_health_prober_self_healing_guard import ProxyHealthProberGuard

class TestProxyHealthProberGuard(unittest.TestCase):

    def setUp(self):
        self.guard = ProxyHealthProberGuard(undo_window_seconds=5)

    @patch('ultra_modules.mihomo_proxy_health_prober_self_healing_guard.socket.create_connection')
    def test_normal_execution_and_defaults(self, mock_socket):
        # 1. Normal execution and default defaults fallback

        # We need to return a MagicMock so that it can be used as a context manager (with)
        def mock_create_connection(addr, timeout=None):
            if addr[1] == 26801:
                time.sleep(0.01) # Simulate slower connection
            m = MagicMock()
            m.__enter__.return_value = m
            m.__exit__.return_value = None
            return m

        mock_socket.side_effect = mock_create_connection

        state = self.guard.probe_proxies() # No params = fallback to defaults (7890, 26801) and 2.0s

        self.assertEqual(state['ports_probed'], (7890, 26801))
        self.assertEqual(state['timeout_used'], 2.0)
        self.assertTrue(state['results']['7890']['open'])
        self.assertTrue(state['results']['26801']['open'])

        # 7890 should be faster because we slept on 26801
        self.assertEqual(state['recommended_port'], 7890)

    @patch('ultra_modules.mihomo_proxy_health_prober_self_healing_guard.socket.create_connection')
    def test_dirty_data_auto_healing(self, mock_socket):
        m = MagicMock()
        m.__enter__.return_value = m
        m.__exit__.return_value = None
        mock_socket.return_value = m

        dirty_ports = ['invalid', 8080, -100, '3128', None, 65536]
        dirty_timeout = 'invalid_timeout'

        state = self.guard.probe_proxies(ports=dirty_ports, timeout=dirty_timeout)

        self.assertEqual(state['ports_probed'], (8080, 3128))
        self.assertEqual(state['timeout_used'], 2.0)

        state2 = self.guard.probe_proxies(ports=[], timeout=-10)
        self.assertEqual(state2['ports_probed'], (7890, 26801))
        self.assertEqual(state2['timeout_used'], 2.0)

        state3 = self.guard.probe_proxies(ports="abc", timeout="xyz")
        self.assertEqual(state3['ports_probed'], (7890, 26801))
        self.assertEqual(state3['timeout_used'], 2.0)

        # Test isinstance(ports, int) logic where it goes to default
        state_int1 = self.guard.probe_proxies(ports=7890)
        self.assertEqual(state_int1['ports_probed'], (7890,))

        state_int2 = self.guard.probe_proxies(ports=-5)
        self.assertEqual(state_int2['ports_probed'], (7890, 26801))

        # Branch 34: except (ValueError, TypeError) in _sanitize_ports
        # To hit ValueError: int("abc") -> ValueError
        state4 = self.guard.probe_proxies(ports=["abc"])
        self.assertEqual(state4['ports_probed'], (7890, 26801))

        # To hit TypeError: int(complex) -> TypeError
        state5 = self.guard.probe_proxies(ports=[1+1j])
        self.assertEqual(state5['ports_probed'], (7890, 26801))

    @patch('ultra_modules.mihomo_proxy_health_prober_self_healing_guard.socket.create_connection')
    def test_boundary_conditions_and_all_down(self, mock_socket):
        import socket

        def mock_fail(addr, timeout=None):
            raise socket.timeout("Timed out")

        mock_socket.side_effect = mock_fail

        state = self.guard.probe_proxies(ports=7890, timeout=1.0)
        self.assertEqual(state['ports_probed'], (7890,))
        self.assertFalse(state['results']['7890']['open'])
        self.assertEqual(state['results']['7890']['latency'], -1)
        self.assertIsNone(state['recommended_port'])

        state2 = self.guard.probe_proxies(ports=[7890.5])
        self.assertEqual(state2['ports_probed'], (7890,))

        # Test clear snapshots
        self.guard.clear_snapshots()
        self.assertEqual(len(self.guard._snapshots), 0)

        # Test saving snapshot when no current state
        guard2 = ProxyHealthProberGuard()
        guard2._save_snapshot()
        self.assertEqual(len(guard2._snapshots), 0)

        # Test sanitize timeout with None, handled by default fallback in actual logic
        state3 = self.guard.probe_proxies(ports=1000, timeout=None)
        self.assertEqual(state3['timeout_used'], 2.0)

        # Test sanitize timeout throwing TypeError (e.g. passing a list/dict)
        state4 = self.guard.probe_proxies(ports=1000, timeout=[])
        self.assertEqual(state4['timeout_used'], 2.0)

    @patch('ultra_modules.mihomo_proxy_health_prober_self_healing_guard.socket.create_connection')
    def test_undo_mechanism_success(self, mock_socket):
        m = MagicMock()
        m.__enter__.return_value = m
        m.__exit__.return_value = None
        mock_socket.return_value = m

        state1 = self.guard.probe_proxies(ports=1111)
        self.assertEqual(state1['ports_probed'], (1111,))

        state2 = self.guard.probe_proxies(ports=2222)
        self.assertEqual(state2['ports_probed'], (2222,))

        success = self.guard.undo_last_probe()
        self.assertTrue(success)

        current_state = self.guard.get_current_state()
        self.assertEqual(current_state['ports_probed'], (1111,))

    @patch('ultra_modules.mihomo_proxy_health_prober_self_healing_guard.socket.create_connection')
    def test_undo_mechanism_expiration_and_empty(self, mock_socket):
        m = MagicMock()
        m.__enter__.return_value = m
        m.__exit__.return_value = None
        mock_socket.return_value = m

        success = self.guard.undo_last_probe()
        self.assertFalse(success)

        fast_guard = ProxyHealthProberGuard(undo_window_seconds=0.1)
        fast_guard.probe_proxies(ports=3333)
        fast_guard.probe_proxies(ports=4444)

        time.sleep(0.15)

        success = fast_guard.undo_last_probe()
        self.assertFalse(success)

        current_state = fast_guard.get_current_state()
        self.assertEqual(current_state['ports_probed'], (4444,))

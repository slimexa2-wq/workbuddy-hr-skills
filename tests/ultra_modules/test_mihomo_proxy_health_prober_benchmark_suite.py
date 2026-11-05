import unittest
import threading
import socket
import time
from ultra_modules.mihomo_proxy_health_prober_benchmark_suite import ProxyHealthProber

def start_dummy_server(host, port, stop_event):
    """启动一个简单的 Dummy Server 以便能够正常连接"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        s.settimeout(0.5)
        while not stop_event.is_set():
            try:
                conn, addr = s.accept()
                with conn:
                    pass # 立即关闭即可
            except socket.timeout:
                continue
            except OSError:
                break

class TestProxyHealthProber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stop_event = threading.Event()

        # 启动 Dummy Servers 模拟 target 和 proxy 端口
        cls.target_port = 54321
        cls.proxy_port_1 = 54322
        cls.proxy_port_2 = 54323

        cls.t_target = threading.Thread(target=start_dummy_server, args=("127.0.0.1", cls.target_port, cls.stop_event))
        cls.t_proxy1 = threading.Thread(target=start_dummy_server, args=("127.0.0.1", cls.proxy_port_1, cls.stop_event))
        cls.t_proxy2 = threading.Thread(target=start_dummy_server, args=("127.0.0.1", cls.proxy_port_2, cls.stop_event))

        cls.t_target.start()
        cls.t_proxy1.start()
        cls.t_proxy2.start()

        # 确保服务器启动
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.stop_event.set()
        cls.t_target.join()
        cls.t_proxy1.join()
        cls.t_proxy2.join()

    def test_01_normal_execution(self):
        """测试 1: 正常执行 (使用真实可连接的本地端口)"""
        prober = ProxyHealthProber(
            proxy_ports=[self.proxy_port_1, self.proxy_port_2],
            target_host="127.0.0.1",
            target_port=self.target_port,
            timeout=1.0
        )
        res = prober.check_health()

        self.assertIn("direct", res)
        self.assertIn(f"proxy_{self.proxy_port_1}", res)
        self.assertIn(f"proxy_{self.proxy_port_2}", res)
        self.assertIn("best_method", res)

        # 因为本地端口都开启了，延迟应该大于等于0
        self.assertGreaterEqual(res["direct"], 0)
        self.assertGreaterEqual(res[f"proxy_{self.proxy_port_1}"], 0)
        self.assertGreaterEqual(res[f"proxy_{self.proxy_port_2}"], 0)
        self.assertNotEqual(res["best_method"], "none")

    def test_02_dirty_data_self_healing(self):
        """测试 2: 脏数据自愈 (混合乱码，非法字符等)"""
        dirty_ports = [self.proxy_port_1, f"{self.proxy_port_2}abcd", "---", None, "   ", 999999, -10]

        prober = ProxyHealthProber(
            proxy_ports=dirty_ports,
            target_host="127.0.0.1",
            target_port=self.target_port,
            timeout=1.0
        )

        # 验证提取出了正确的合法端口 (由于 abcd 被过滤，数字保留，非法范围被丢弃)
        self.assertIn(self.proxy_port_1, prober.proxy_ports)
        self.assertIn(self.proxy_port_2, prober.proxy_ports)

        res = prober.check_health()
        self.assertIn("direct", res)
        self.assertIn(f"proxy_{self.proxy_port_1}", res)
        self.assertIn(f"proxy_{self.proxy_port_2}", res)

    def test_03_missing_parameters_default_fallback(self):
        """测试 3: 缺参默认兜底"""
        prober = ProxyHealthProber(
            proxy_ports=None,
            target_host=None,
            target_port="invalid",
            timeout=None
        )
        # 默认 proxy_ports 是 [7890, 26801]
        self.assertEqual(prober.proxy_ports, [7890, 26801])
        # 默认 target_host 是 www.google.com
        self.assertEqual(prober.target_host, "www.google.com")
        # 默认 target_port 是 80
        self.assertEqual(prober.target_port, 80)
        # 默认 timeout 是 2.0
        self.assertEqual(prober.timeout, 2.0)

    def test_04_extreme_boundaries(self):
        """测试 4: 极端边界 (Synthetic Fixtures: 跨年跨月，或不合理的字典/对象作为端口等)"""
        synthetic_fixtures = [
            {"date": "2023-12-31"}, # dict (非法)
            ["nested_list"],        # list (非法)
            "2024-01-01",           # 会被过滤为 20240101 (超过 65535, 会被忽略)
            self.proxy_port_1       # 合法
        ]

        prober = ProxyHealthProber(
            proxy_ports=synthetic_fixtures,
            target_host="127.0.0.1",
            target_port=self.target_port,
            timeout=1.0
        )

        # 只保留了合法端口
        self.assertEqual(prober.proxy_ports, [self.proxy_port_1])

        res = prober.check_health()
        self.assertIn(f"proxy_{self.proxy_port_1}", res)
        self.assertGreaterEqual(res[f"proxy_{self.proxy_port_1}"], 0)

    def test_05_massive_concurrency_benchmark(self):
        """测试 5: 超大并发基准测试 (零崩溃与毫秒级响应)"""
        prober = ProxyHealthProber(
            proxy_ports=[self.proxy_port_1, self.proxy_port_2],
            target_host="127.0.0.1",
            target_port=self.target_port,
            timeout=1.0
        )

        benchmark_res = prober.run_benchmark(concurrency=200) # 超大并发

        self.assertEqual(benchmark_res["concurrency"], 200)
        self.assertEqual(benchmark_res["success_count"], 200)
        self.assertGreater(benchmark_res["total_time_ms"], 0)
        # 确保 sample_result 有完整结构
        self.assertIn("direct", benchmark_res["sample_result"])
        self.assertIn(f"proxy_{self.proxy_port_1}", benchmark_res["sample_result"])

if __name__ == '__main__':
    unittest.main()
